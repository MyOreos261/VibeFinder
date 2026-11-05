"""
VibeFinder agent: orchestrates one request from text to verified recommendations.

Steps (each one is recorded in the trace):
  1. guard     - reject empty / too long / prompt-injection requests
  2. parse     - LLM (or rule-based fallback) turns text into preferences
  3. validate  - drop values outside the catalog vocabulary
  4. retrieve  - pull genre + activity notes from the knowledge base (RAG)
  5. augment   - fill missing prefs from the activity note; collect related genres
  6. rank      - score every song, with partial credit for related genres
  7. confidence- score how sure the system is; low confidence => ask the human
  8. explain   - LLM writes the explanation from the retrieved songs + notes
  9. verify    - check the explanation only uses retrieved songs; retry once, then fall back
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.guardrails import GuardrailError, check_request, validate_prefs, verify_explanation
from src.knowledge import KnowledgeBase, Note
from src.parser import parse_with_llm, parse_with_rules
from src.recommender import DEFAULT_WEIGHTS, MOOD_FAMILIES, load_songs, score_song

logger = logging.getLogger(__name__)

SONGS_CSV = Path(__file__).resolve().parent.parent / "data" / "songs.csv"
CONFIDENCE_THRESHOLD = 0.5
RELATED_GENRE_SHARE = 0.5   # related genre earns half of the genre weight
RELATED_MOOD_SHARE = 0.5    # mood in the same family earns half of the mood weight


@dataclass
class AgentResult:
    request: str
    status: str = "ok"                        # ok | rejected | needs_clarification
    message: str = ""
    prefs: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    recommendations: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    explanation: Optional[Dict] = None
    explanation_source: str = ""              # llm | template
    parser_source: str = ""                   # llm | rules
    trace: List[Dict] = field(default_factory=list)


class VibeFinderAgent:
    def __init__(self, songs: Optional[List[Dict]] = None, kb: Optional[KnowledgeBase] = None,
                 client=None, use_rag: bool = True, k: int = 5):
        self.songs = songs if songs is not None else load_songs(str(SONGS_CSV), verbose=False)
        self.kb = kb or KnowledgeBase.load()
        self.client = client
        self.use_rag = use_rag
        self.k = k
        self.catalog_genres = {s["genre"] for s in self.songs}
        self.catalog_moods = {s["mood"] for s in self.songs}

    # ------------------------------------------------------------------ helpers
    def _log(self, result: AgentResult, step: str, **details) -> None:
        entry = {"step": step, **details}
        result.trace.append(entry)
        logger.info("[%s] %s", step, json.dumps(details, default=str))

    def _parse(self, request: str, result: AgentResult) -> Dict:
        if self.client is not None:
            raw = parse_with_llm(request, self.kb, self.catalog_moods, self.client)
            if raw is not None:
                result.parser_source = "llm"
                return raw
            result.warnings.append("LLM parsing failed; used the rule-based parser.")
        result.parser_source = "rules"
        return parse_with_rules(request, self.kb)

    def _augment(self, prefs: Dict, notes: List[Note]) -> Tuple[Dict, List[str], List[str]]:
        """Use retrieved notes to fill gaps and find related genres. Returns (prefs, related, filled)."""
        prefs = dict(prefs)
        related: List[str] = []
        filled: List[str] = []
        genre_note = self.kb.genres.get(prefs.get("genre", ""))
        if genre_note:
            related += genre_note.related
        activity_note = self.kb.activities.get(prefs.get("activity", ""))
        if activity_note:
            f = activity_note.fields
            if "mood" not in prefs and f.get("mood") in self.catalog_moods:
                prefs["mood"] = f["mood"]
                filled.append(f"mood={f['mood']}")
            if "energy" not in prefs and f.get("energy"):
                prefs["energy"] = float(f["energy"])
                filled.append(f"energy={f['energy']}")
            if "likes_acoustic" not in prefs and f.get("likes_acoustic") in ("yes", "no"):
                prefs["likes_acoustic"] = f["likes_acoustic"] == "yes"
                filled.append(f"likes_acoustic={prefs['likes_acoustic']}")
            # Activity genres only count when the user did not name a genre.
            if "genre" not in prefs:
                related += activity_note.related
        related = [g for g in dict.fromkeys(related) if g != prefs.get("genre")]
        return prefs, related, filled

    def _rank(self, prefs: Dict, related: List[str]) -> List[Dict]:
        w = DEFAULT_WEIGHTS
        scored = []
        for song in self.songs:
            score, reasons = score_song(prefs, song)
            if song["genre"] in related:
                bonus = w["genre"] * RELATED_GENRE_SHARE
                score += bonus
                reasons.append(f"related genre: {song['genre']} (from knowledge notes) (+{bonus:.2f})")
            target = prefs.get("mood")
            if (self.use_rag and target and song["mood"] != target
                    and any({song["mood"], target} <= fam for fam in MOOD_FAMILIES)):
                bonus = w["mood"] * RELATED_MOOD_SHARE
                score += bonus
                reasons.append(f"related mood: {song['mood']} ~ {target} (+{bonus:.2f})")
            scored.append({"song": song, "score": round(score, 2), "reasons": reasons})
        scored.sort(key=lambda r: (-r["score"], r["song"]["title"]))
        return scored[: self.k]

    def _confidence(self, prefs: Dict, recs: List[Dict]) -> float:
        """
        0.4 * coverage (how many of genre / mood / energy we know)
      + 0.6 * fit      (top score / best score possible for these prefs)
        """
        w = DEFAULT_WEIGHTS
        coverage = sum(1 for key in ("genre", "mood", "energy") if key in prefs) / 3
        max_score = ((w["genre"] if "genre" in prefs else 0) + (w["mood"] if "mood" in prefs else 0)
                     + (w["energy"] if "energy" in prefs else 0)
                     + (w["acoustic"] if "likes_acoustic" in prefs else 0))
        fit = min(1.0, recs[0]["score"] / max_score) if recs and max_score else 0.0
        return round(0.4 * coverage + 0.6 * fit, 2)

    def _template_explanation(self, request: str, recs: List[Dict]) -> Dict:
        picks = [{"title": r["song"]["title"],
                  "why": "; ".join(r["reasons"][:3]) or "closest overall match"} for r in recs]
        return {"intro": f"Top {len(recs)} matches for \"{request}\" from the catalog.", "picks": picks}

    def _explain_prompt(self, request: str, prefs: Dict, recs: List[Dict], notes: List[Note],
                        feedback: str = "") -> str:
        songs_block = "\n".join(
            f"{i}. \"{r['song']['title']}\" by {r['song']['artist']} | genre={r['song']['genre']} "
            f"mood={r['song']['mood']} energy={r['song']['energy']} acousticness={r['song']['acousticness']} "
            f"| score={r['score']} | scoring reasons: {'; '.join(r['reasons'])}"
            for i, r in enumerate(recs, start=1))
        notes_block = "\n".join(n.as_context() for n in notes) or "(no notes retrieved)"
        retry = f"\nYour previous answer was rejected because: {feedback}. Fix that.\n" if feedback else ""
        return f"""You are VibeFinder, a music recommender that explains its picks honestly.

User request: {json.dumps(request)}
Parsed preferences: {json.dumps(prefs)}

Retrieved songs (already ranked by the scoring system, best first):
{songs_block}

Retrieved knowledge notes:
{notes_block}
{retry}
Write a JSON object: {{"intro": "<one sentence>", "picks": [{{"title": "<exact title>", "why": "<one or two sentences>"}}]}}

Rules:
- Use ONLY the retrieved songs above, with their exact titles, in the same order. Include all of them.
- Each "why" must be based on the song's listed attributes, scoring reasons, or the notes. Do not invent facts.
- If a song is a weak fit, say so honestly.
"""

    # --------------------------------------------------------------------- main
    def run(self, request: str) -> AgentResult:
        start = time.perf_counter()
        result = AgentResult(request=request)

        # 1. guard
        try:
            request = check_request(request)
            result.request = request
            self._log(result, "guard", passed=True)
        except GuardrailError as exc:
            result.status, result.message = "rejected", str(exc)
            self._log(result, "guard", passed=False, reason=str(exc))
            return result

        # 2. parse
        raw = self._parse(request, result)
        self._log(result, "parse", source=result.parser_source, raw=raw)

        # 3. validate
        prefs, warnings = validate_prefs(raw, self.catalog_genres, set(self.kb.genres), self.catalog_moods)
        result.warnings += warnings
        self._log(result, "validate", prefs=prefs, warnings=warnings)

        # 4 + 5. retrieve and augment (skipped in baseline mode)
        notes: List[Note] = []
        related: List[str] = []
        if self.use_rag:
            notes = self.kb.retrieve(request, genre=prefs.get("genre"), activity=prefs.get("activity"))
            result.notes = [f"{n.source} > {n.name}" for n in notes]
            self._log(result, "retrieve", notes=result.notes)
            prefs, related, filled = self._augment(prefs, notes)
            self._log(result, "augment", filled_from_notes=filled, related_genres=related)
        result.prefs = prefs

        scoring_prefs = {k: v for k, v in prefs.items() if k in ("genre", "mood", "energy", "likes_acoustic")}
        if not scoring_prefs:
            result.status = "needs_clarification"
            result.message = ("I couldn't find a genre, mood, energy level, or activity in that request. "
                              "Try something like 'upbeat pop for a road trip'.")
            self._log(result, "clarify", reason="no usable preferences")
            return result

        # 6. rank
        recs = self._rank(scoring_prefs, related)
        result.recommendations = recs
        self._log(result, "rank", top=[(r["song"]["title"], r["score"]) for r in recs])

        # 7. confidence + human-in-the-loop flag
        result.confidence = self._confidence(scoring_prefs, recs)
        if result.confidence < CONFIDENCE_THRESHOLD:
            result.status = "needs_clarification"
            missing = [k for k in ("genre", "mood", "energy") if k not in scoring_prefs]
            result.message = (f"Low confidence ({result.confidence:.2f}). These are best guesses"
                              + (f"; telling me your {', '.join(missing)} would help." if missing else "."))
        self._log(result, "confidence", score=result.confidence, threshold=CONFIDENCE_THRESHOLD)

        # 8 + 9. explain and verify
        titles = [r["song"]["title"] for r in recs]
        explanation, source = None, "template"
        if self.client is not None:
            feedback = ""
            for attempt in (1, 2):
                candidate = self.client.generate_json(
                    self._explain_prompt(request, scoring_prefs, recs, notes, feedback), temperature=0.4)
                problems = verify_explanation(candidate, titles)
                self._log(result, "verify", attempt=attempt, passed=not problems, problems=problems)
                if not problems:
                    explanation, source = candidate, "llm"
                    break
                feedback = "; ".join(problems)
        if explanation is None:
            explanation = self._template_explanation(request, recs)
            if self.client is not None:
                result.warnings.append("LLM explanation failed verification twice; showing the scoring reasons instead.")
        result.explanation, result.explanation_source = explanation, source
        self._log(result, "explain", source=source,
                  elapsed_ms=round((time.perf_counter() - start) * 1000))
        return result
