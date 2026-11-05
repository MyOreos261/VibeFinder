"""
Build the VibeFinder song guide: an in-depth song knowledge document for RAG.

    python -m tools.make_song_guide

Writes the same content in four formats to data/knowledge/:
  song_guide.pdf   read by VibeFinder's retriever (src/knowledge.py)
  song_guide.txt   plain text; the retriever's fallback if the PDF can't be read
  song_guide.md    Markdown, readable on GitHub
  song_guide.rtf   Rich Text, opens in Word / WordPad / TextEdit

Sources:
  - data/songs.csv            feature values (never re-typed by hand)
  - data/song_details.json    hand-written sound, structure, lyric themes, tips
  - data/knowledge/*.md       genre and activity notes
  - VibeFinderAgent (offline) the activity playlists, so the PDF matches what the app recommends

Chunking contract (used by src/knowledge.py): each song section starts with a line
"Song: <title>" and ends with a line "End of song: <title>". Inside, every field is a
line that starts with a fixed label such as "Sound:" or "Vocals:". All songs and artists
are fictional.
"""

import json
from pathlib import Path
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from src.agent import VibeFinderAgent
from src.knowledge import KnowledgeBase
from src.recommender import MOOD_FAMILIES, load_songs

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "knowledge"
DETAILS = ROOT / "data" / "song_details.json"
MAX_BYTES = 25 * 1024 * 1024

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

GLOSSARY = [
    ("Energy", "How intense and active a song feels, from 0.0 (very calm) to 1.0 (very intense). VibeFinder "
               "rewards closeness to the energy you want, not 'higher is better'."),
    ("Valence", "How positive a song sounds, from 0.0 (sad, dark) to 1.0 (happy, bright)."),
    ("Danceability", "How suitable the rhythm is for dancing, from 0.0 to 1.0."),
    ("Acousticness", "How acoustic (real instruments, unplugged) versus electronic or produced a song sounds, "
                     "from 0.0 to 1.0."),
    ("Tempo (BPM)", "Beats per minute. Around 60-80 BPM feels slow, 90-120 moderate, 125+ fast."),
    ("Instrumental", "A song with no sung or rapped vocals. Marked in this guide as 'Vocals: none (instrumental)'."),
    ("Related genre", "A genre that fans of another genre usually also enjoy, taken from the VibeFinder genre "
                      "notes. Related genres earn half of the genre points when ranking."),
    ("Mood family", "Groups of moods that feel alike: chill/relaxed/focused, happy/euphoric/confident, "
                    "intense/angry, and sad/melancholy/moody/nostalgic."),
    ("Confidence", "VibeFinder's own estimate of how well it understood and matched a request (0 to 1). Below "
                   "0.5 it asks the listener for more detail."),
]


def level(value: float) -> str:
    """Describe a 0-1 feature in words so text search can match it."""
    for limit, word in ((0.2, "very low"), (0.4, "low"), (0.6, "medium"), (0.8, "high")):
        if value < limit:
            return word
    return "very high"


def tempo_word(bpm: float) -> str:
    return "slow" if bpm < 85 else "moderate" if bpm < 120 else "fast"


def same_family(a: str, b: str) -> bool:
    return a == b or any({a, b} <= family for family in MOOD_FAMILIES)


def activity_fit(song: Dict, note) -> bool:
    """A song fits an activity if its genre or mood family matches and its energy is within 0.25."""
    energy = float(note.fields.get("energy", 0.5))
    style = song["genre"] in note.related or same_family(song["mood"], note.fields.get("mood", ""))
    return style and abs(song["energy"] - energy) <= 0.25


def similar_songs(song: Dict, songs: List[Dict], kb: KnowledgeBase, n: int = 3) -> List[Dict]:
    """Closest songs by energy and acousticness, with a bonus for related genre or mood family."""
    related = set(kb.genres[song["genre"]].related) if song["genre"] in kb.genres else set()

    def distance(other: Dict) -> float:
        d = abs(song["energy"] - other["energy"]) + 0.5 * abs(song["acousticness"] - other["acousticness"])
        if other["genre"] == song["genre"] or other["genre"] in related:
            d -= 0.3
        if same_family(song["mood"], other["mood"]):
            d -= 0.2
        return d

    return sorted((o for o in songs if o["id"] != song["id"]), key=lambda o: (distance(o), o["title"]))[:n]


def compare(a: Dict, b: Dict) -> str:
    """One-sentence factual comparison of two songs."""
    parts = []
    diff = b["energy"] - a["energy"]
    if abs(diff) < 0.05:
        parts.append("about the same energy")
    else:
        parts.append(f"{'more' if diff > 0 else 'less'} energetic ({b['energy']:.2f} vs {a['energy']:.2f})")
    diff = b["acousticness"] - a["acousticness"]
    if abs(diff) >= 0.15:
        parts.append(f"{'more' if diff > 0 else 'less'} acoustic")
    if b["mood"] != a["mood"]:
        parts.append(f"{b['mood']} instead of {a['mood']}")
    if b["genre"] != a["genre"]:
        parts.append(f"{b['genre']} instead of {a['genre']}")
    return f"Compared with {a['title']}, {b['title']} is " + ", ".join(parts) + "."


def qa_lines(song: Dict, details: Dict, kb: KnowledgeBase) -> List[str]:
    """Question/answer pairs that retrieval can match directly."""
    lines = []
    for name in ("studying", "workout", "party", "sleep"):
        note = kb.activities[name]
        fits = activity_fit(song, note)
        reason = (f"its {song['mood']} mood and {level(song['energy'])} energy ({song['energy']:.2f}) "
                  f"{'fit' if fits else 'do not fit'} the {name} target of {note.fields.get('mood')} mood "
                  f"and energy around {note.fields.get('energy')}")
        lines.append(f"Q: Is {song['title']} good for {name}? A: {'Yes' if fits else 'Not really'}; {reason}.")
    instrumental = details["vocals"].startswith("none")
    lines.append(f"Q: Does {song['title']} have vocals? A: "
                 + ("No, it is instrumental." if instrumental else f"Yes: {details['vocals']}."))
    lines.append(f"Q: Is {song['title']} acoustic? A: "
                 + ("Yes, mostly acoustic" if song["acousticness"] >= 0.6 else
                    "Partly" if song["acousticness"] >= 0.3 else "No, it is mostly electronic or produced")
                 + f" (acousticness {song['acousticness']:.2f}).")
    return lines


# ---------------------------------------------------------------------------------------------
# Content is built once as a list of simple blocks, then rendered to each format:
#   ("title"|"subtitle"|"h1"|"h2"|"h3"|"p"|"small"|"end", text)   text may contain <b>...</b>
#   ("table", rows, widths_in_inches)    ("group", [blocks])    ("pagebreak",)    ("space",)
# ---------------------------------------------------------------------------------------------

def build_blocks() -> List[tuple]:
    songs = load_songs(str(ROOT / "data" / "songs.csv"), verbose=False)
    kb = KnowledgeBase.load(include_song_guide=False)
    details = {k: v for k, v in json.loads(DETAILS.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    missing = [s["title"] for s in songs if s["title"] not in DESCRIPTIONS or s["title"] not in details]
    if missing:
        raise SystemExit(f"Missing description or details for: {', '.join(missing)}")

    B: List[tuple] = [
        ("title", "VibeFinder Song Guide"),
        ("subtitle", "An in-depth knowledge document for retrieval-augmented music recommendations"),
        ("subtitle", f"{len(songs)} songs - {len(kb.genres)} genre notes - {len(kb.activities)} activity guides"),
        ("h1", "About this document"),
        ("p", "This guide describes every song in the VibeFinder catalog (data/songs.csv) in depth: its sound, "
              "vocals, structure, lyric themes, when to play it and when to skip it, how it compares with similar "
              "songs, and direct answers to common questions. All songs and artists are fictional and were "
              "created for a classroom project. Feature values come directly from the catalog; activity "
              "playlists were produced by running the VibeFinder recommender itself, so this guide never "
              "contradicts the app."),
        ("p", "How VibeFinder uses it: the retriever extracts the text and splits it into one chunk per song, "
              "from the line 'Song: <title>' to the line 'End of song: <title>'. When a request names a song "
              "('songs like Storm Runner'), the agent copies that song's genre, mood and energy. When a request "
              "names a sound ('piano', 'fiddle', 'no vocals'), songs whose Sound or Vocals lines mention it get "
              "a bonus, and the matching sections are passed to the language model as evidence."),
        ("p", "Contents: 1. Catalog at a glance - 2. Songs in depth - 3. Activity playlists - "
              "4. Genre guide - 5. Mood map - 6. Glossary"),
        ("pagebreak",),
        ("h1", "Chapter 1: Catalog at a glance"),
    ]
    rows = [["#", "Title", "Artist", "Genre", "Mood", "Energy", "BPM", "Acoustic", "Vocals"]]
    for s in songs:
        rows.append([str(s["id"]), s["title"], s["artist"], s["genre"], s["mood"], f"{s['energy']:.2f}",
                     f"{s['tempo_bpm']:.0f}", f"{s['acousticness']:.2f}",
                     "none" if details[s["title"]]["vocals"].startswith("none") else "yes"])
    B += [("table", rows, [0.3, 1.5, 1.1, 0.8, 0.85, 0.55, 0.4, 0.6, 0.5]), ("pagebreak",),
          ("h1", "Chapter 2: Songs in depth")]

    for s in songs:
        d = details[s["title"]]
        good = [n.name for n in kb.activities.values() if activity_fit(s, n)] or ["general listening"]
        sims = similar_songs(s, songs, kb)
        sim_text = ", ".join("%s (%s)" % (o["title"], o["genre"]) for o in sims)
        fields = [
            f"<b>Artist:</b> {s['artist']}",
            f"<b>Genre:</b> {s['genre']} | <b>Mood:</b> {s['mood']}",
            f"<b>Energy:</b> {s['energy']:.2f} ({level(s['energy'])}) | <b>Tempo:</b> {s['tempo_bpm']:.0f} BPM "
            f"({tempo_word(s['tempo_bpm'])}) | <b>Valence:</b> {s['valence']:.2f} ({level(s['valence'])}) | "
            f"<b>Danceability:</b> {s['danceability']:.2f} ({level(s['danceability'])}) | "
            f"<b>Acousticness:</b> {s['acousticness']:.2f} ({level(s['acousticness'])})",
            f"<b>Description:</b> {DESCRIPTIONS[s['title']]}",
            f"<b>Sound:</b> {d['sound']}",
            f"<b>Vocals:</b> {d['vocals']}",
            f"<b>Structure:</b> {d['structure']}",
            f"<b>Lyric themes:</b> {d['lyrics']}",
            f"<b>Listen when:</b> {d['listen_when']}",
            f"<b>Skip when:</b> {d['skip_when']}",
            f"<b>Good for:</b> {', '.join(good)}",
            f"<b>Similar songs:</b> {sim_text}",
            f"<b>Comparisons:</b> {' '.join(compare(s, o) for o in sims[:2])}",
            f"<b>Listening tip:</b> {d['tip']}",
            "<b>Questions and answers:</b>",
        ] + qa_lines(s, d, kb)
        # Cover art sits OUTSIDE the Song:/End of song: markers, so it never enters a retrieval chunk.
        B.append(("artbreak",))
        B.append(("group", [("image", s),
                            ("caption", f"Cover art for {s['title']}: generated from its mood ({s['mood']}), "
                                        f"energy ({s['energy']:.2f}) and acousticness ({s['acousticness']:.2f}).")]))
        B.append(("group", [("h2", f"Song: {s['title']}")] + [("small", f) for f in fields]
                  + [("end", f"End of song: {s['title']}")]))

    B += [("pagebreak",), ("h1", "Chapter 3: Activity playlists"),
          ("p", "Each playlist below is the top 5 that VibeFinder returns (offline mode, with retrieval) "
                "for the request 'music for <activity>'.")]
    agent = VibeFinderAgent(songs=songs, kb=kb, use_rag=True, k=5)
    for note in kb.activities.values():
        result = agent.run(f"music for {note.name}")
        rows = [["#", "Song", "Genre / mood", "Energy", "Score"]]
        for i, rec in enumerate(result.recommendations, start=1):
            song = rec["song"]
            rows.append([str(i), song["title"], f"{song['genre']} / {song['mood']}", f"{song['energy']:.2f}",
                         f"{rec['score']:.2f}"])
        B.append(("group", [
            ("h3", f"Playlist: {note.name}"),
            ("small", f"Target: {note.fields.get('mood')} mood, energy about {note.fields.get('energy')}, "
                      f"acoustic preference {note.fields.get('likes_acoustic')}. {note.text}"),
            ("table", rows, [0.3, 2.0, 1.8, 0.7, 0.6]),
        ]))

    B += [("pagebreak",), ("h1", "Chapter 4: Genre guide")]
    for note in kb.genres.values():
        in_catalog = [s for s in songs if s["genre"] == note.name]
        related_songs = [s for s in songs if s["genre"] in note.related]
        B.append(("group", [
            ("h3", f"Genre: {note.name}"),
            ("small", note.text),
            ("small", f"<b>Also called:</b> {', '.join(note.aliases[1:]) or 'none'} | "
                      f"<b>Related genres:</b> {', '.join(note.related) or 'none'}"),
            ("small", "<b>Catalog songs:</b> " + (", ".join(s["title"] for s in in_catalog) or
                      "none in the catalog; VibeFinder uses the related genres instead")),
            ("small", "<b>Songs in related genres:</b> " + (", ".join(f"{s['title']} ({s['genre']})"
                      for s in related_songs) or "none")),
        ]))

    B += [("pagebreak",), ("h1", "Chapter 5: Mood map"),
          ("p", "Songs grouped by mood family, sorted from lowest to highest energy.")]
    for family in MOOD_FAMILIES:
        members = sorted((s for s in songs if s["mood"] in family), key=lambda s: s["energy"])
        B += [("h3", f"Mood family: {' / '.join(sorted(family))}"),
              ("small", ", ".join(f"{s['title']} ({s['mood']}, energy {s['energy']:.2f})" for s in members)
               or "none")]
    other = sorted((s for s in songs if not any(s["mood"] in f for f in MOOD_FAMILIES)), key=lambda s: s["energy"])
    if other:
        B += [("h3", "Moods outside the families"),
              ("small", ", ".join(f"{s['title']} ({s['mood']}, energy {s['energy']:.2f})" for s in other))]

    B += [("space",), ("h1", "Chapter 6: Glossary")]
    B += [("small", f"<b>{term}:</b> {text}") for term, text in GLOSSARY]
    return B


def strip_tags(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")


def flatten(blocks: List[tuple]) -> List[tuple]:
    out: List[tuple] = []
    for block in blocks:
        out += flatten(block[1]) if block[0] == "group" else [block]
    return out


# ------------------------------------------------------------------------------------- cover art
MOOD_RGB = {
    "happy": (245, 185, 66), "euphoric": (255, 122, 182), "confident": (255, 159, 67), "intense": (255, 92, 92),
    "angry": (200, 40, 40), "chill": (79, 209, 197), "relaxed": (99, 179, 237), "focused": (127, 156, 245),
    "sad": (110, 125, 160), "melancholy": (120, 90, 190), "moody": (150, 110, 220), "nostalgic": (214, 162, 107),
    "romantic": (246, 135, 179),
}


def cover_art(song: Dict, px: int) -> bytes:
    """
    Square JPEG artwork generated from the song's features: mood sets the palette, energy sets how
    many rings and how tight they are, acousticness adds a soft film grain. Seeded by the song id,
    so the same catalog always produces the same images.
    """
    import io
    import math
    import random

    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(1000 + song["id"])
    r, g, b = MOOD_RGB.get(song["mood"], (160, 160, 180))
    dark = (r // 5, g // 5, b // 5)
    img = Image.new("RGB", (px, px))
    draw = ImageDraw.Draw(img)
    for y in range(px):                                     # vertical gradient
        t = y / px
        draw.line([(0, y), (px, y)], fill=tuple(int(c * (1 - t) + d * t) for c, d in zip((r, g, b), dark)))
    cx, cy = px * (0.3 + 0.4 * rng.random()), px * (0.3 + 0.4 * rng.random())
    rings = 6 + int(song["energy"] * 30)                    # more energy -> more, tighter rings
    for i in range(rings, 0, -1):
        radius = px * 0.9 * i / rings
        wobble = 1 + 0.08 * song["energy"] * math.sin(i * 1.7)
        shade = 0.35 + 0.65 * (i % 2)
        color = tuple(min(255, int(c * shade + 40 * (1 - shade))) for c in (r, g, b))
        draw.ellipse([cx - radius * wobble, cy - radius, cx + radius * wobble, cy + radius],
                     outline=color, width=max(2, px // 300))
    img = img.filter(ImageFilter.GaussianBlur(radius=px / 900))
    grain = Image.frombytes("L", (px, px), rng.randbytes(px * px)).convert("RGB")
    img = Image.blend(img, grain, 0.06 + 0.12 * song["acousticness"])   # acoustic songs get more grain
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


# ------------------------------------------------------------------------------------- PDF
def render_pdf(blocks: List[tuple], path: Path, art_px: int = 0) -> None:
    import io

    from reportlab.platypus import Image as RLImage
    from xml.sax.saxutils import escape

    styles = getSampleStyleSheet()
    purple, teal = colors.HexColor("#4b1fa8"), colors.HexColor("#1f7a72")
    st = {
        "title": ParagraphStyle("T", parent=styles["Title"], textColor=purple, fontSize=26, leading=32,
                                spaceBefore=80),
        "subtitle": ParagraphStyle("Sub", parent=styles["BodyText"], alignment=TA_CENTER,
                                   textColor=colors.HexColor("#555555"), spaceAfter=10),
        "h1": ParagraphStyle("H1", parent=styles["Heading1"], textColor=purple),
        "h2": ParagraphStyle("H2", parent=styles["Heading2"], textColor=teal, spaceBefore=8, spaceAfter=3),
        "h3": ParagraphStyle("H3", parent=styles["Heading3"], textColor=purple, spaceBefore=6, spaceAfter=2),
        "p": ParagraphStyle("B", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6),
        "small": ParagraphStyle("Sm", parent=styles["BodyText"], fontSize=9, leading=12.5,
                                textColor=colors.HexColor("#222222")),
        "end": ParagraphStyle("E", parent=styles["BodyText"], fontSize=7, textColor=colors.HexColor("#999999"),
                              spaceAfter=8),
        "caption": ParagraphStyle("Cap", parent=styles["BodyText"], fontSize=8, alignment=TA_CENTER,
                                  textColor=colors.HexColor("#666666"), spaceAfter=10),
    }

    def para(kind: str, text: str) -> Paragraph:
        safe = escape(text).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        return Paragraph(safe, st[kind])

    def flow(block: tuple) -> list:
        kind = block[0]
        if kind == "pagebreak" or (kind == "artbreak" and art_px):
            return [PageBreak()]
        if kind == "artbreak":
            return []
        if kind == "space":
            return [Spacer(1, 0.2 * inch)]
        if kind == "group":
            return [KeepTogether([f for b in block[1] for f in flow(b)])]
        if kind == "image":
            if not art_px:
                return []
            side = 4.6 * inch
            return [Spacer(1, 0.3 * inch),
                    RLImage(io.BytesIO(cover_art(block[1], art_px)), width=side, height=side)]
        if kind == "table":
            t = Table(block[1], repeatRows=1, colWidths=[w * inch for w in block[2]])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), purple), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1ecfb")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            return [Spacer(1, 3), t, Spacer(1, 6)]
        return [para(kind, block[1])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(inch, 0.5 * inch, "VibeFinder Song Guide - fictional catalog for a classroom project")
        canvas.drawRightString(letter[0] - inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=letter, title="VibeFinder Song Guide", author="VibeFinder",
                            subject="Song knowledge base for RAG", leftMargin=inch, rightMargin=inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    doc.build([f for b in blocks for f in flow(b)], onFirstPage=footer, onLaterPages=footer)


# ------------------------------------------------------------------------------------- TXT
def render_txt(blocks: List[tuple], path: Path) -> None:
    lines: List[str] = []
    for block in flatten(blocks):
        kind = block[0]
        if kind == "title":
            lines += ["=" * 72, block[1].upper(), "=" * 72]
        elif kind == "subtitle":
            lines.append(block[1])
        elif kind == "h1":
            lines += ["", "", block[1].upper(), "=" * len(block[1])]
        elif kind in ("h2", "h3"):
            lines += ["", block[1], "-" * len(block[1])]
        elif kind in ("p", "small"):
            lines.append(strip_tags(block[1]))
        elif kind == "end":
            lines += [block[1], ""]
        elif kind == "table":
            rows = block[1]
            widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]

            def fmt(row):
                return "  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip()

            lines += ["", fmt(rows[0]), "  ".join("-" * w for w in widths)] + [fmt(r) for r in rows[1:]] + [""]
        elif kind in ("pagebreak", "space"):
            lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------- Markdown
def render_md(blocks: List[tuple], path: Path) -> None:
    def md(text: str) -> str:
        text = text.replace("<title>", "`<title>`").replace("<activity>", "`<activity>`")
        return text.replace("<b>", "**").replace("</b>", "**")

    lines: List[str] = []
    for block in flatten(blocks):
        kind = block[0]
        if kind == "title":
            lines += [f"# {block[1]}", ""]
        elif kind == "subtitle":
            lines += [f"*{block[1]}*", ""]
        elif kind in ("h1", "h2", "h3"):
            lines += ["", "#" * {"h1": 2, "h2": 3, "h3": 4}[kind] + " " + block[1], ""]
        elif kind == "p":
            lines += [md(block[1]), ""]
        elif kind == "small":
            lines += [md(block[1]), ""]
        elif kind == "end":
            lines += [f"<sub>{block[1]}</sub>", ""]
        elif kind == "table":
            rows = block[1]
            lines += ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * len(rows[0])]
            lines += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows[1:]] + [""]
        elif kind == "pagebreak":
            lines += ["---", ""]
        elif kind == "space":
            lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------- RTF
def render_rtf(blocks: List[tuple], path: Path) -> None:
    def esc(text: str) -> str:
        out = []
        for ch in text:
            if ch in "\\{}":
                out.append("\\" + ch)
            elif ord(ch) > 127:
                out.append(f"\\u{ord(ch)}?")
            else:
                out.append(ch)
        return "".join(out).replace("<b>", "{\\b ").replace("</b>", "}")

    parts = ["{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0\\fswiss Helvetica;}}",
             "{\\colortbl;\\red75\\green31\\blue168;\\red31\\green122\\blue114;\\red120\\green120\\blue120;}",
             "\\f0\\fs20"]
    styles = {"title": ("\\qc\\b\\fs48\\cf1 ", 0), "subtitle": ("\\qc\\i\\fs20\\cf3 ", 0),
              "h1": ("\\b\\fs32\\cf1 ", 240), "h2": ("\\b\\fs26\\cf2 ", 200), "h3": ("\\b\\fs22\\cf1 ", 160),
              "p": ("\\fs20 ", 0), "small": ("\\fs18 ", 0), "end": ("\\fs14\\cf3 ", 0)}
    tabs = "".join(f"\\tx{t}" for t in range(500, 9500, 1100))
    for block in flatten(blocks):
        kind = block[0]
        if kind in styles:
            fmt, before = styles[kind]
            parts.append(f"{{\\pard\\sb{before}\\sa80 {fmt}{esc(block[1])}\\par}}")
        elif kind == "table":
            for i, row in enumerate(block[1]):
                cells = "\\tab ".join(esc(str(c)) for c in row)
                if i == 0:  # bold header row
                    cells = "{\\b " + cells + "}"
                parts.append("{\\pard\\fs16" + tabs + " " + cells + "\\par}")
        elif kind == "pagebreak":
            parts.append("\\page")
        elif kind == "space":
            parts.append("{\\pard\\par}")
    parts.append("}")
    path.write_text("\n".join(parts), encoding="ascii")


MIN_PDF_BYTES = 20 * 1024 * 1024     # the PDF must be at least 20 MB ...
MAX_PDF_BYTES = 25 * 1000 * 1000     # ... and under 25 MB


def build_pdf_in_size_window(blocks: List[tuple], path: Path) -> int:
    """
    Render the PDF, sizing the cover art so the file lands between 20 and 25 MB.
    JPEG size grows roughly with pixel count, so each retry rescales by the square root of the ratio.
    Returns the art resolution used.
    """
    target = (MIN_PDF_BYTES + MAX_PDF_BYTES) / 2
    render_pdf(blocks, path, art_px=0)
    text_bytes = path.stat().st_size
    songs = [b[1][0][1] for b in blocks if b[0] == "group" and b[1] and b[1][0][0] == "image"]
    sample = len(cover_art(songs[0], 1000))
    px = int(1000 * ((target - text_bytes) / (sample * len(songs))) ** 0.5)
    for _ in range(4):
        render_pdf(blocks, path, art_px=px)
        size = path.stat().st_size
        if MIN_PDF_BYTES <= size <= MAX_PDF_BYTES:
            return px
        px = int(px * ((target - text_bytes) / (size - text_bytes)) ** 0.5)
    raise SystemExit(f"Could not fit {path.name} between 20 and 25 MB (last size {size / 1e6:.1f} MB)")


def build() -> Dict[str, Path]:
    blocks = build_blocks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {}
    pdf_path = OUT_DIR / "song_guide.pdf"
    px = build_pdf_in_size_window(blocks, pdf_path)
    print(f"Cover art rendered at {px}x{px} px")
    outputs["pdf"] = pdf_path
    for ext, render in (("txt", render_txt), ("md", render_md), ("rtf", render_rtf)):
        path = OUT_DIR / f"song_guide.{ext}"
        render(blocks, path)
        if path.stat().st_size > MAX_BYTES:
            raise SystemExit(f"{path.name} is over the 25 MB limit")
        outputs[ext] = path
    return outputs


if __name__ == "__main__":
    for ext, out in build().items():
        print(f"Wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.2f} MB)")
