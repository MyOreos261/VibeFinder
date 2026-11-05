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
from typing import Dict, List, Optional

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


class KnowledgeBase:
    """Holds all notes and answers retrieval queries."""

    def __init__(self, notes: List[Note]):
        self.notes = notes
        self.genres = {n.name: n for n in notes if n.kind == "genre"}
        self.activities = {n.name: n for n in notes if n.kind == "activity"}

    @classmethod
    def load(cls, directory: Path = KNOWLEDGE_DIR) -> "KnowledgeBase":
        """Read genres.md and activities.md from the knowledge folder."""
        notes: List[Note] = []
        for filename, kind in (("genres.md", "genre"), ("activities.md", "activity")):
            path = Path(directory) / filename
            notes.extend(parse_notes(path.read_text(encoding="utf-8"), kind, filename))
        logger.info("Knowledge base loaded: %d genre notes, %d activity notes",
                    sum(n.kind == "genre" for n in notes), sum(n.kind == "activity" for n in notes))
        return cls(notes)

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
