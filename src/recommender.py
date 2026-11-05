import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

# Algorithm Recipe: points awarded for each kind of match.
# Max possible score = 2.0 + 1.0 + 1.5 + 0.5 = 5.0
DEFAULT_WEIGHTS = {
    "genre": 2.0,     # exact genre match
    "mood": 1.0,      # exact mood match
    "energy": 1.5,    # scaled by how close the song's energy is to the target
    "acoustic": 0.5,  # scaled by acousticness (or lack of it) if the user has a preference
}

# Experiment (Phase 4): double energy, halve genre.
EXPERIMENT_WEIGHTS = {**DEFAULT_WEIGHTS, "genre": 1.0, "energy": 3.0}

NUMERIC_FIELDS = {
    "id": int,
    "energy": float,
    "tempo_bpm": float,
    "valence": float,
    "danceability": float,
    "acousticness": float,
}

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

    def to_prefs(self) -> Dict:
        """Convert this profile to the dict format used by score_song."""
        return {
            "genre": self.favorite_genre,
            "mood": self.favorite_mood,
            "energy": self.target_energy,
            "likes_acoustic": self.likes_acoustic,
        }

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k Song objects for this user, best first."""
        prefs = user.to_prefs()
        ranked = sorted(self.songs, key=lambda s: score_song(prefs, asdict(s))[0], reverse=True)
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a readable sentence listing why this song scored the way it did."""
        score, reasons = score_song(user.to_prefs(), asdict(song))
        return f"Score {score:.2f}: " + "; ".join(reasons)

def load_songs(csv_path: str, verbose: bool = True) -> List[Dict]:
    """Read the songs CSV into a list of dicts, converting numeric columns to numbers."""
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for field, cast in NUMERIC_FIELDS.items():
                row[field] = cast(row[field])
            songs.append(row)
    if verbose:
        print(f"Loaded songs: {len(songs)}")
    return songs

def score_song(user_prefs: Dict, song: Dict, weights: Optional[Dict] = None) -> Tuple[float, List[str]]:
    """Score one song against the user's preferences and return (score, reasons)."""
    w = weights or DEFAULT_WEIGHTS
    score = 0.0
    reasons = []

    if song["genre"] == user_prefs.get("genre"):
        score += w["genre"]
        reasons.append(f"genre match: {song['genre']} (+{w['genre']:.2f})")

    if song["mood"] == user_prefs.get("mood"):
        score += w["mood"]
        reasons.append(f"mood match: {song['mood']} (+{w['mood']:.2f})")

    # Closeness, not "higher is better": a perfect match earns full points,
    # and points shrink linearly as the gap grows (gap of 1.0 earns 0).
    if "energy" in user_prefs:
        gap = abs(song["energy"] - user_prefs["energy"])
        points = w["energy"] * (1 - gap)
        score += points
        reasons.append(f"energy {song['energy']:.2f} vs target {user_prefs['energy']:.2f} (+{points:.2f})")

    likes_acoustic = user_prefs.get("likes_acoustic")
    if likes_acoustic is not None:
        fit = song["acousticness"] if likes_acoustic else 1 - song["acousticness"]
        points = w["acoustic"] * fit
        score += points
        label = "acoustic" if likes_acoustic else "produced/electronic"
        reasons.append(f"{label} sound fit (+{points:.2f})")

    return round(score, 2), reasons

# --- Scoring modes (Strategy pattern) ---------------------------------------
# Each strategy exposes the same score(user_prefs, song) method, so
# recommend_songs can swap ranking behavior without any if/else on the mode.

# Moods that feel alike; MoodFirst gives half credit for a mood in the same family.
MOOD_FAMILIES = [
    {"chill", "relaxed", "focused"},
    {"happy", "euphoric", "confident"},
    {"intense", "angry"},
    {"sad", "melancholy", "moody", "nostalgic"},
]

class ScoringStrategy:
    """Base strategy: score songs with a fixed set of weights."""
    name = "base"
    description = ""
    weights = DEFAULT_WEIGHTS

    def score(self, user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
        """Return (score, reasons) for one song under this strategy."""
        return score_song(user_prefs, song, self.weights)

class GenreFirst(ScoringStrategy):
    """Original recipe: genre is the strongest signal."""
    name = "genre-first"
    description = "genre +2.0, mood +1.0, energy up to +1.5, acoustic up to +0.5"

class MoodFirst(ScoringStrategy):
    """Mood outweighs genre, with half credit for related moods."""
    name = "mood-first"
    description = "mood +2.0 (related mood +1.0), genre +1.0, energy up to +1.5, acoustic up to +0.5"
    weights = {**DEFAULT_WEIGHTS, "genre": 1.0, "mood": 2.0}

    def score(self, user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
        """Score with the base rules, then add partial credit for a related mood."""
        score, reasons = super().score(user_prefs, song)
        target = user_prefs.get("mood")
        if song["mood"] != target and any({song["mood"], target} <= family for family in MOOD_FAMILIES):
            bonus = self.weights["mood"] / 2
            score += bonus
            reasons.insert(0, f"related mood: {song['mood']} ~ {target} (+{bonus:.2f})")
        return round(score, 2), reasons

class EnergyFocused(ScoringStrategy):
    """Energy closeness dominates; labels are tie-breakers."""
    name = "energy-focused"
    description = "energy up to +3.0, genre +0.5, mood +0.5, acoustic up to +0.5"
    weights = {**DEFAULT_WEIGHTS, "genre": 0.5, "mood": 0.5, "energy": 3.0}

STRATEGIES = {s.name: s for s in (GenreFirst(), MoodFirst(), EnergyFocused())}

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5, weights: Optional[Dict] = None,
                    strategy: Optional[ScoringStrategy] = None) -> List[Tuple[Dict, float, str]]:
    """Score every song, sort highest first, and return the top k as (song, score, explanation)."""
    scored = []
    for song in songs:
        if strategy:
            score, reasons = strategy.score(user_prefs, song)
        else:
            score, reasons = score_song(user_prefs, song, weights)
        scored.append((song, score, "; ".join(reasons)))
    # sorted() returns a new list and leaves `songs` untouched; ties break by title for stable output.
    return sorted(scored, key=lambda item: (-item[1], item[0]["title"]))[:k]
