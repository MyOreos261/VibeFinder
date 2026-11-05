"""
Guardrails: checks that run before and after the AI steps.

  check_request()      -> is the user's text safe and usable at all?
  validate_prefs()     -> are the parsed preferences inside the catalog's vocabulary?
  verify_explanation() -> did the LLM only talk about songs we actually retrieved?
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

MAX_REQUEST_CHARS = 500

# Phrases that try to take over the model instead of asking for music.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
    r"system prompt",
    r"you are now",
    r"disregard (the|your) (rules|instructions)",
    r"api[_ ]?key",
]


class GuardrailError(ValueError):
    """Raised when a request must be rejected before any AI step runs."""


def check_request(text: Optional[str]) -> str:
    """Return the cleaned request, or raise GuardrailError with a user-friendly reason."""
    if text is None or not text.strip():
        raise GuardrailError("Empty request. Describe the music you want, e.g. 'calm lofi for studying'.")
    cleaned = " ".join(text.split())
    if len(cleaned) > MAX_REQUEST_CHARS:
        raise GuardrailError(f"Request is {len(cleaned)} characters; the limit is {MAX_REQUEST_CHARS}.")
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            logger.warning("Blocked request matching injection pattern %r", pattern)
            raise GuardrailError("That looks like an instruction to the AI, not a music request, so it was blocked.")
    return cleaned


def validate_prefs(raw: Dict, catalog_genres: Set[str], known_genres: Set[str],
                   catalog_moods: Set[str]) -> Tuple[Dict, List[str]]:
    """
    Clean parsed preferences and return (prefs, warnings).

    - genre must be a catalog genre or a genre we have a knowledge note for
    - mood must be a mood that exists in the catalog
    - energy is converted to float and clamped to [0, 1]
    - likes_acoustic must be a real boolean
    Anything invalid is dropped (never guessed) and reported as a warning.
    """
    prefs: Dict = {}
    warnings: List[str] = []

    genre = (raw.get("genre") or "")
    genre = genre.strip().lower() if isinstance(genre, str) else ""
    if genre:
        if genre in known_genres:
            prefs["genre"] = genre
            if genre not in catalog_genres:
                warnings.append(f"'{genre}' has no songs in the catalog; using related genres from the notes.")
        else:
            warnings.append(f"Unknown genre '{genre}' was ignored.")

    mood = (raw.get("mood") or "")
    mood = mood.strip().lower() if isinstance(mood, str) else ""
    if mood:
        if mood in catalog_moods:
            prefs["mood"] = mood
        else:
            warnings.append(f"Unknown mood '{mood}' was ignored.")

    energy = raw.get("energy")
    if energy is not None and energy != "":
        try:
            value = float(energy)
            if 1 < value <= 100 and value.is_integer():   # "70" meaning 70%
                value = value / 100
            clamped = min(1.0, max(0.0, value))
            if clamped != value:
                warnings.append(f"Energy {value} was clamped to {clamped}.")
            prefs["energy"] = round(clamped, 2)
        except (TypeError, ValueError):
            warnings.append(f"Energy '{energy}' is not a number and was ignored.")

    acoustic = raw.get("likes_acoustic")
    if isinstance(acoustic, bool):
        prefs["likes_acoustic"] = acoustic
    elif acoustic not in (None, ""):
        warnings.append(f"likes_acoustic '{acoustic}' is not true/false and was ignored.")

    activity = raw.get("activity")
    if isinstance(activity, str) and activity.strip():
        prefs["activity"] = activity.strip().lower()

    return prefs, warnings


def verify_explanation(explanation: Optional[Dict], allowed_titles: List[str]) -> List[str]:
    """
    Check an LLM explanation against the retrieved songs. Returns a list of problems
    (empty list = passed). This is what stops the model from inventing songs.
    """
    if not isinstance(explanation, dict):
        return ["response was not a JSON object"]
    problems: List[str] = []
    if not isinstance(explanation.get("intro"), str) or not explanation["intro"].strip():
        problems.append("missing intro")
    picks = explanation.get("picks")
    if not isinstance(picks, list) or not picks:
        return problems + ["no picks"]

    allowed = {t.lower(): t for t in allowed_titles}
    seen: Set[str] = set()
    for pick in picks:
        title = str(pick.get("title", "")).strip() if isinstance(pick, dict) else ""
        if title.lower() not in allowed:
            problems.append(f"'{title}' was not in the retrieved songs")
        elif title.lower() in seen:
            problems.append(f"'{title}' listed twice")
        seen.add(title.lower())
        if not isinstance(pick, dict) or not str(pick.get("why", "")).strip():
            problems.append(f"no reason given for '{title}'")
    if allowed_titles and allowed_titles[0].lower() not in seen:
        problems.append(f"top-ranked song '{allowed_titles[0]}' was left out")
    return problems
