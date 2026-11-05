"""
Build data/knowledge/song_guide.pdf: a song-by-song knowledge document for RAG.

    python -m tools.make_song_guide

The numbers (energy, tempo, ...) come straight from data/songs.csv, and "Good for" /
"Similar songs" are computed from the same knowledge notes and features the recommender
uses, so the PDF never contradicts the catalog. Only the descriptions are hand-written.
All songs and artists are fictional.

Chunking: every song section starts with a line "Song: <title>" and contains the same
labeled lines (Artist:, Genre:, ...), so a retriever can split the extracted text on "Song:".
"""

from pathlib import Path
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from src.knowledge import KnowledgeBase
from src.recommender import MOOD_FAMILIES, load_songs

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "knowledge" / "song_guide.pdf"

DESCRIPTIONS: Dict[str, str] = {
    "Sunrise City": "A bright, sun-soaked pop anthem built on glossy synths, a bouncing bassline and a big "
                    "sing-along chorus about leaving the city at dawn. It feels like windows-down optimism.",
    "Midnight Coding": "A mellow lofi loop with dusty drums, muted electric-piano chords and soft rain samples. "
                       "Steady and unobtrusive, it is made to sit quietly behind late-night work.",
    "Storm Runner": "Fast, distorted guitar rock with pounding live drums and a shouted chorus. The energy is "
                    "relentless from the first bar; it is built for adrenaline.",
    "Library Rain": "Quiet lofi with plucked acoustic guitar, a brushed snare and the sound of rain on a window. "
                    "Very calm, warm and cozy.",
    "Gym Hero": "A pumped-up pop track with stadium drums, chanted vocals and a hard-hitting drop. It is "
                "aggressive for pop: more 'push through the last rep' than 'feel good'.",
    "Spacewalk Thoughts": "A slow, floating ambient piece of soft synth pads and distant piano with no real beat. "
                          "Spacious, weightless and calm.",
    "Coffee Shop Stories": "An easygoing jazz trio of upright bass, brushed drums and gentle piano. It sounds like "
                           "a quiet afternoon in a cafe and stays pleasantly in the background.",
    "Night Drive Loop": "Retro synthwave with pulsing arpeggios, gated drums and a dark, cinematic melody. It "
                        "evokes empty highways and city lights after midnight.",
    "Focus Flow": "Minimal lofi with a steady head-nod beat, soft keys and no vocals. It is repetitive on purpose "
                  "so it fades into the background while you concentrate.",
    "Rooftop Lights": "Jangly indie pop with chiming guitars, handclaps and a warm, slightly lo-fi vocal. "
                      "Summer-evening joy with a handmade feel.",
    "Concrete Crown": "Swaggering hip-hop over a heavy boom-bap beat and deep 808 bass, with confident verses "
                      "and a chantable hook.",
    "Moonlit Sonata Redux": "A slow solo-piano piece with long sustained notes and a wistful, minor-key melody. "
                            "Very quiet, acoustic and introspective.",
    "Iron Tempest": "Heavy metal with blast-beat drums, down-tuned riffs and growled vocals. It is the most "
                    "aggressive and highest-energy track in the catalog.",
    "Dusty Porch Swing": "Acoustic country with fiddle, slide guitar and a story about summers at a grandparent's "
                         "farmhouse. Warm, unhurried and nostalgic.",
    "Velvet Hours": "Smooth, slow-burning R&B with silky vocals, soft electric piano and a laid-back groove. "
                    "An intimate, late-evening mood.",
    "Laser Bloom": "Festival EDM with a long build, a huge euphoric drop and sparkling synth leads. Pure "
                   "peak-time dance-floor energy; almost nothing acoustic.",
    "Island Postcard": "Sunny roots reggae with an off-beat guitar skank, warm bass and easygoing vocals about a "
                       "beach town. Relaxed and bright.",
    "Paper Boats": "Sparse acoustic folk: fingerpicked guitar and a fragile voice singing about letting someone "
                   "go. Quiet and heartbreaking.",
    "Crossroads Blue": "Slow electric blues with a crying lead guitar and weary vocals. Soulful sadness at a "
                       "walking pace.",
    "Starlight Sprint": "High-gloss K-pop with rapid-fire verses, a soaring chorus and a dance break. Bright, "
                        "fast and relentlessly upbeat.",
}


def level(value: float) -> str:
    """Describe a 0-1 feature in words so text search can match it."""
    for limit, word in ((0.2, "very low"), (0.4, "low"), (0.6, "medium"), (0.8, "high")):
        if value < limit:
            return word
    return "very high"


def same_family(a: str, b: str) -> bool:
    return a == b or any({a, b} <= family for family in MOOD_FAMILIES)


def good_for(song: Dict, kb: KnowledgeBase) -> List[str]:
    """Activities whose note fits this song: matching genre or mood family, and energy within 0.25."""
    matches = []
    for note in kb.activities.values():
        energy = float(note.fields.get("energy", 0.5))
        fits_style = song["genre"] in note.related or same_family(song["mood"], note.fields.get("mood", ""))
        if fits_style and abs(song["energy"] - energy) <= 0.25:
            matches.append(note.name)
    return matches or ["general listening"]


def similar_songs(song: Dict, songs: List[Dict], kb: KnowledgeBase, n: int = 3) -> List[str]:
    """Closest songs by energy and acousticness, with a bonus for related genre or mood family."""
    related = set(kb.genres[song["genre"]].related) if song["genre"] in kb.genres else set()

    def distance(other: Dict) -> float:
        d = abs(song["energy"] - other["energy"]) + 0.5 * abs(song["acousticness"] - other["acousticness"])
        if other["genre"] == song["genre"] or other["genre"] in related:
            d -= 0.3
        if same_family(song["mood"], other["mood"]):
            d -= 0.2
        return d

    others = sorted((o for o in songs if o["id"] != song["id"]), key=lambda o: (distance(o), o["title"]))
    return [f"{o['title']} ({o['genre']})" for o in others[:n]]


def build() -> Path:
    songs = load_songs(str(ROOT / "data" / "songs.csv"), verbose=False)
    kb = KnowledgeBase.load()
    missing = [s["title"] for s in songs if s["title"] not in DESCRIPTIONS]
    if missing:
        raise SystemExit(f"No description for: {', '.join(missing)}")

    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Title"], textColor=colors.HexColor("#4b1fa8"))
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=colors.HexColor("#4b1fa8"))
    song_h = ParagraphStyle("S", parent=styles["Heading2"], textColor=colors.HexColor("#1f7a72"),
                            spaceBefore=6, spaceAfter=2)
    body = ParagraphStyle("B", parent=styles["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("Sm", parent=body, fontSize=9, leading=12, textColor=colors.HexColor("#333333"))
    center = ParagraphStyle("C", parent=body, alignment=TA_CENTER, textColor=colors.HexColor("#555555"))

    story = [
        Paragraph("VibeFinder Song Guide", title),
        Paragraph("A song-by-song knowledge document for retrieval-augmented recommendations", center),
        Spacer(1, 0.25 * inch),
        Paragraph("About this document", h1),
        Paragraph(
            f"This guide describes all {len(songs)} songs in the VibeFinder catalog (data/songs.csv). "
            "All songs and artists are fictional and were created for a classroom project. "
            "The feature values come directly from the catalog; energy, valence, danceability and "
            "acousticness range from 0.0 to 1.0. 'Good for' lists the activities from the VibeFinder "
            "activity notes whose mood or genres match the song and whose target energy is within 0.25 "
            "of the song's energy. 'Similar songs' are the closest catalog songs by energy and acousticness, "
            "favoring related genres and moods.", body),
        Spacer(1, 0.1 * inch),
        Paragraph(
            "How to use it for RAG: extract the text and split it into chunks on lines that start with "
            "'Song:'. Each chunk then holds exactly one song, with the labeled fields Artist, Genre, Mood, "
            "Energy, Tempo, Valence, Danceability, Acousticness, Description, Good for and Similar songs.",
            body),
        Spacer(1, 0.2 * inch),
        Paragraph("Catalog at a glance", h1),
    ]

    table_rows = [["#", "Title", "Artist", "Genre", "Mood", "Energy", "BPM"]]
    for s in songs:
        table_rows.append([str(s["id"]), s["title"], s["artist"], s["genre"], s["mood"],
                           f"{s['energy']:.2f}", f"{s['tempo_bpm']:.0f}"])
    table = Table(table_rows, repeatRows=1,
                  colWidths=[0.35 * inch, 1.75 * inch, 1.3 * inch, 0.9 * inch, 0.95 * inch, 0.6 * inch, 0.5 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b1fa8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1ecfb")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [table, PageBreak(), Paragraph("Songs", h1)]

    for s in songs:
        fields = [
            f"<b>Artist:</b> {s['artist']}",
            f"<b>Genre:</b> {s['genre']} | <b>Mood:</b> {s['mood']}",
            f"<b>Energy:</b> {s['energy']:.2f} ({level(s['energy'])}) | <b>Tempo:</b> {s['tempo_bpm']:.0f} BPM | "
            f"<b>Valence:</b> {s['valence']:.2f} ({level(s['valence'])}) | "
            f"<b>Danceability:</b> {s['danceability']:.2f} ({level(s['danceability'])}) | "
            f"<b>Acousticness:</b> {s['acousticness']:.2f} ({level(s['acousticness'])})",
            f"<b>Description:</b> {DESCRIPTIONS[s['title']]}",
            f"<b>Good for:</b> {', '.join(good_for(s, kb))}",
            f"<b>Similar songs:</b> {', '.join(similar_songs(s, songs, kb))}",
        ]
        block = [Paragraph(f"Song: {s['title']}", song_h)] + [Paragraph(f, small) for f in fields]
        story.append(KeepTogether(block + [Spacer(1, 0.12 * inch)]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(inch, 0.5 * inch, "VibeFinder Song Guide - fictional catalog for a classroom project")
        canvas.drawRightString(letter[0] - inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=letter, title="VibeFinder Song Guide",
                            author="VibeFinder", subject="Song knowledge base for RAG",
                            leftMargin=inch, rightMargin=inch, topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path.relative_to(ROOT)}")
