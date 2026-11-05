"""
Knowledge base + retriever (the "R" in RAG).

Loads the markdown notes in data/knowledge/ into small Note objects and retrieves
the ones relevant to a request. Retrieved notes change what the system does:
  - genre notes give partial credit to related genres when ranking songs,
  - activity notes fill in a missing mood / energy / acoustic preference,
  - the note text is passed to the LLM as grounding context for its explanation.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

FIELD_LINE = re.compile(r"^([a-z_]+):\s*(.*)$")


@dataclass
class Note:
    """One retrievable entry, e.g. the 'lofi' genre note or the 'studying' activity note."""
    name: str
    kind: str                      # "genre" or "activity"
    source: str                    # file it came from, for citations
    fields: Dict[str, str] = field(default_factory=dict)
    text: str = ""

    @property
    def aliases(self) -> List[str]:
        """The note's name plus every alias, lowercased."""
        extra = [a.strip().lower() for a in self.fields.get("aliases", "").split(",") if a.strip()]
        return [self.name] + extra

    @property
    def related(self) -> List[str]:
        """Related genres listed by this note."""
        return [g.strip().lower() for g in self.fields.get("related", "").split(",") if g.strip()]

    def as_context(self) -> str:
        """Short text block handed to the LLM."""
        return f"[{self.source} > {self.name}] {self.text}"


def parse_notes(markdown: str, kind: str, source: str) -> List[Note]:
    """Split a notes file on '## name' headers into Note objects."""
    notes: List[Note] = []
    current: Optional[Note] = None
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = Note(name=line[3:].strip().lower(), kind=kind, source=source)
            notes.append(current)
            continue
        if current is None or not line:
            continue
        match = FIELD_LINE.match(line)
        if match and not current.text:
            current.fields[match.group(1)] = match.group(2).strip()
        else:
            current.text = f"{current.text} {line}".strip()
    return notes


SONG_GUIDE = "song_guide.pdf"
SONG_CHUNK = re.compile(r"Song: (.+?)\n(.*?)End of song: \1", re.DOTALL)
SONG_LABELS = ["Artist", "Genre", "Mood", "Energy", "Tempo", "Valence", "Danceability", "Acousticness",
               "Description", "Sound", "Vocals", "Structure", "Lyric themes", "Listen when", "Skip when",
               "Good for", "Similar songs", "Comparisons", "Listening tip", "Questions and answers", "Q"]
LABEL_LINE = re.compile(rf"^({'|'.join(re.escape(label) for label in SONG_LABELS)}):\s*(.*)$")

# Words a listener might use -> the term searched for in a song's Sound and Vocals lines.
# INSTRUMENTAL is special: it matches songs whose Vocals line says "none (instrumental)".
INSTRUMENTAL = "<instrumental>"
SOUND_TERMS = {
    "piano": "piano", "keys": "piano", "acoustic guitar": "acoustic guitar", "guitar": "guitar",
    "guitars": "guitar", "electric guitar": "electric", "fiddle": "fiddle", "violin": "fiddle",
    "cello": "cello", "strings": "string", "synth": "synth", "synths": "synth", "synthesizer": "synth",
    "rain": "rain", "rain sounds": "rain", "vinyl": "vinyl", "harmonica": "harmonica", "organ": "organ",
    "808": "808", "808s": "808", "bass drop": "drop", "drop": "drop", "dance break": "dance-break",
    "handclaps": "handclaps", "claps": "handclaps", "melodica": "melodica", "scratches": "scratches",
    "scratching": "scratches", "rap": "rap", "rapping": "rap", "female vocals": "female",
    "female vocalist": "female", "male vocals": "male", "growl": "growl", "screaming": "scream",
    "instrumental": INSTRUMENTAL, "no vocals": INSTRUMENTAL, "no lyrics": INSTRUMENTAL,
    "without vocals": INSTRUMENTAL, "no singing": INSTRUMENTAL, "without lyrics": INSTRUMENTAL,
}


def _wb(phrase: str) -> str:
    return rf"(?<![\w-]){re.escape(phrase)}(?![\w-])"


def parse_song_guide(text: str) -> List[Note]:
    """Split the extracted PDF text into one Note per song (between 'Song:' and 'End of song:')."""
    notes = []
    for title, chunk in SONG_CHUNK.findall(text):
        fields: Dict[str, str] = {}
        current = None
        for raw in chunk.splitlines():
            line = raw.strip()
            if not line:
                continue
            # A line like "Genre: pop | Mood: happy" holds several labeled fields.
            parts = [p.strip() for p in line.split(" | ")] if LABEL_LINE.match(line) else [line]
            for part in parts:
                match = LABEL_LINE.match(part)
                if match:
                    label = match.group(1).lower()
                    if label == "q":
                        label = "questions and answers"
                        value = part
                    else:
                        value = match.group(2)
                    current = label
                    fields[label] = f"{fields[label]} {value}".strip() if label in fields else value
                elif current:  # wrapped continuation of the previous field
                    fields[current] = f"{fields[current]} {part}".strip()
        fields = {k: v.rstrip(" |") for k, v in fields.items()}
        title = title.strip()
        summary = (f"{title} by {fields.get('artist', '?')}: {fields.get('description', '')} "
                   f"Sound: {fields.get('sound', '')}. Vocals: {fields.get('vocals', '')}.")
        notes.append(Note(name=title.lower(), kind="song", source=SONG_GUIDE, fields=fields, text=summary))
    return notes


_GUIDE_CACHE: Dict[Tuple[str, float], List[Note]] = {}


def load_song_guide(path: Path) -> List[Note]:
    """
    Extract and parse the song guide PDF (cached per file version). If the PDF can't be read,
    fall back to the plain-text export next to it; if neither works, return [] with a warning.
    """
    for candidate in (path, path.with_suffix(".txt")):
        if not candidate.exists():
            continue
        key = (str(candidate), candidate.stat().st_mtime)
        if key in _GUIDE_CACHE:
            return _GUIDE_CACHE[key]
        try:
            if candidate.suffix == ".pdf":
                from pypdf import PdfReader
                text = "\n".join(page.extract_text() or "" for page in PdfReader(str(candidate)).pages)
            else:
                text = candidate.read_text(encoding="utf-8")
        except Exception as exc:  # missing package, corrupt file...
            logger.warning("Could not read %s (%s)", candidate.name, exc)
            continue
        notes = parse_song_guide(text)
        _GUIDE_CACHE[key] = notes
        logger.info("Song guide loaded from %s: %d song chunks", candidate.name, len(notes))
        return notes
    logger.warning("No readable song guide found; song-level retrieval disabled")
    return []


class KnowledgeBase:
    """Holds all notes and answers retrieval queries."""

    def __init__(self, notes: List[Note], songs: Optional[List[Note]] = None):
        self.notes = notes
        self.genres = {n.name: n for n in notes if n.kind == "genre"}
        self.activities = {n.name: n for n in notes if n.kind == "activity"}
        # Song chunks are kept apart from self.notes so titles don't flood retrieve().
        self.songs = {n.name: n for n in (songs or [])}

    @classmethod
    def load(cls, directory: Path = KNOWLEDGE_DIR, include_song_guide: bool = True) -> "KnowledgeBase":
        """Read genres.md, activities.md and (optionally) song_guide.pdf from the knowledge folder."""
        notes: List[Note] = []
        for filename, kind in (("genres.md", "genre"), ("activities.md", "activity")):
            path = Path(directory) / filename
            notes.extend(parse_notes(path.read_text(encoding="utf-8"), kind, filename))
        songs = load_song_guide(Path(directory) / SONG_GUIDE) if include_song_guide else []
        logger.info("Knowledge base loaded: %d genre notes, %d activity notes, %d song notes",
                    sum(n.kind == "genre" for n in notes), sum(n.kind == "activity" for n in notes), len(songs))
        return cls(notes, songs)

    def find_song_reference(self, text: str) -> Optional[Note]:
        """Return the song whose title appears in the request ('songs like Storm Runner'), if any."""
        lowered = text.lower()
        found = [note for name, note in self.songs.items() if re.search(_wb(name), lowered)]
        return max(found, key=lambda n: len(n.name)) if found else None

    def sound_matches(self, text: str) -> Dict[str, List[str]]:
        """
        Map song name -> listener words that its Sound/Vocals lines match, e.g.
        'instrumental piano' -> {'moonlit sonata redux': ['piano', 'instrumental'], ...}.
        """
        lowered = text.lower()
        # Ignore words that are part of a named song title ("more like Library Rain" is not a rain request).
        for name in self.songs:
            lowered = re.sub(_wb(name), " ", lowered)
        asked = {}
        for phrase, term in sorted(SOUND_TERMS.items(), key=lambda kv: -len(kv[0])):
            if re.search(_wb(phrase), lowered) and term not in asked.values():
                # Skip a shorter phrase inside a longer one already found ("guitar" in "acoustic guitar").
                if not any(phrase in longer for longer in asked):
                    asked[phrase] = term
        matches: Dict[str, List[str]] = {}
        for name, note in self.songs.items():
            sound = f"{note.fields.get('sound', '')} | {note.fields.get('vocals', '')}".lower()
            for phrase, term in asked.items():
                if term == INSTRUMENTAL:
                    hit = note.fields.get("vocals", "").lower().startswith("none")
                else:
                    hit = re.search(rf"(?<![\w-]){re.escape(term)}", sound) is not None
                if hit:
                    matches.setdefault(name, []).append(phrase)
        return matches

    def genre_alias_map(self) -> Dict[str, str]:
        """alias -> canonical genre name, for the rule-based parser."""
        return {alias: note.name for note in self.genres.values() for alias in note.aliases}

    def find_activity(self, text: str) -> Optional[Note]:
        """Return the activity note whose longest alias appears in the text, if any."""
        best, best_len = None, 0
        lowered = text.lower()
        for note in self.activities.values():
            for alias in note.aliases:
                if len(alias) > best_len and re.search(rf"\b{re.escape(alias)}\b", lowered):
                    best, best_len = note, len(alias)
        return best

    def retrieve(self, request: str, genre: Optional[str] = None, activity: Optional[str] = None,
                 k: int = 3) -> List[Note]:
        """
        Return up to k notes relevant to the request.

        A note scores 3 if it is the parsed genre or activity, plus 1 for every alias
        that appears in the request text. Ties keep file order so results are stable.
        """
        lowered = request.lower()
        scored = []
        for index, note in enumerate(self.notes):
            score = 0
            if note.name in (genre, activity):
                score += 3
            score += sum(1 for alias in note.aliases if re.search(rf"\b{re.escape(alias)}\b", lowered))
            if score:
                scored.append((score, index, note))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [note for _, _, note in scored[:k]]
