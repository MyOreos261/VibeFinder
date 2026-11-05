"""
VibeFinder 2.0 web app (Streamlit).

    streamlit run app_web.py

Uses the same VibeFinderAgent as the CLI. Sidebar toggles switch Gemini and RAG on/off
so you can compare behavior live; thumbs up/down ratings are saved to logs/feedback.jsonl.
"""

import html
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from src.agent import CONFIDENCE_THRESHOLD, VibeFinderAgent
from src.app import LOG_DIR, save_trace, setup_logging
from src.knowledge import KnowledgeBase
from src.llm import make_client
from src.recommender import load_songs

ROOT = Path(__file__).resolve().parent

EXAMPLES = {
    "🚗 Road trip pop": "upbeat pop for a road trip",
    "😴 Music for sleeping": "music for sleeping",
    "💔 Heartbreak acoustic": "heartbroken, need some sad acoustic songs",
    "🏋️ Gym rock": "intense rock for the gym",
    "🪗 Polka party": "polka for a happy party",
}

MOOD_COLORS = {
    "happy": "#f5b942", "euphoric": "#ff7ab6", "confident": "#ff9f43", "intense": "#ff5c5c",
    "angry": "#e03e3e", "chill": "#4fd1c5", "relaxed": "#63b3ed", "focused": "#7f9cf5",
    "sad": "#8c9bb5", "melancholy": "#9f7aea", "moody": "#b794f4", "nostalgic": "#d6a26b",
    "romantic": "#f687b3",
}

CSS = """
<style>
.vf-hero {background: linear-gradient(120deg, #7b2ff7 0%, #2bb5a8 100%); border-radius: 18px;
          padding: 26px 28px; margin-bottom: 18px; color: #fff;}
.vf-hero h1 {margin: 0; font-size: 2.1rem; color: #fff;}
.vf-hero p {margin: 6px 0 0; opacity: .9;}
.vf-banner {border-radius: 12px; padding: 12px 16px; margin: 10px 0 16px; font-weight: 600;}
.vf-high {background: rgba(56,178,112,.18); border: 1px solid #38b270;}
.vf-mid {background: rgba(245,185,66,.18); border: 1px solid #f5b942;}
.vf-low {background: rgba(229,62,62,.18); border: 1px solid #e53e3e;}
.vf-card {border: 1px solid rgba(150,150,170,.35); border-radius: 14px; padding: 14px 16px;
          min-height: 360px; margin-bottom: 8px; background: rgba(127,127,160,.07);}
.vf-rank {font-size: .8rem; opacity: .7;}
.vf-title {font-size: 1.1rem; font-weight: 700; margin: 2px 0 0;}
.vf-artist {opacity: .75; font-size: .9rem; margin-bottom: 8px;}
.vf-tag {display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: .75rem;
         margin: 0 4px 4px 0; color: #111; font-weight: 600;}
.vf-bar {height: 6px; border-radius: 3px; background: rgba(150,150,170,.25); margin: 2px 0 6px;}
.vf-bar > div {height: 6px; border-radius: 3px;}
.vf-small {font-size: .75rem; opacity: .75;}
.vf-why {font-size: .88rem; margin-top: 8px;}
.vf-why b {color: #2bb5a8;}
.vf-rag {font-size: .78rem; margin-top: 6px; color: #2bb5a8;}
</style>
"""


@st.cache_resource
def load_data():
    setup_logging()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    return load_songs(str(ROOT / "data" / "songs.csv"), verbose=False), KnowledgeBase.load()


@st.cache_resource
def get_client():
    return make_client()


def save_feedback(request: str, title: str, rating: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "request": request, "title": title, "rating": rating}
    with open(LOG_DIR / "feedback.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def bar(value: float, color: str) -> str:
    return f'<div class="vf-bar"><div style="width:{value * 100:.0f}%;background:{color}"></div></div>'


def song_card(rank: int, rec: dict, why: str) -> str:
    song = rec["song"]
    esc = html.escape
    mood_color = MOOD_COLORS.get(song["mood"], "#a0aec0")
    rag_reasons = [r for r in rec["reasons"]
                   if ("knowledge notes" in r or "related mood" in r) and r not in why]
    rag_html = "".join(f'<div class="vf-rag">🔍 {esc(r)}</div>' for r in rag_reasons)
    return f"""
<div class="vf-card">
  <div class="vf-rank">#{rank} · score {rec['score']:.2f}</div>
  <div class="vf-title">{esc(song['title'])}</div>
  <div class="vf-artist">{esc(song['artist'])}</div>
  <span class="vf-tag" style="background:#cbd5e0">{esc(song['genre'])}</span>
  <span class="vf-tag" style="background:{mood_color}">{esc(song['mood'])}</span>
  <div class="vf-small">Energy {song['energy']:.2f}</div>{bar(song['energy'], '#ff7a59')}
  <div class="vf-small">Acoustic {song['acousticness']:.2f}</div>{bar(song['acousticness'], '#4fd1c5')}
  <div class="vf-why">{esc(why)}</div>
  {rag_html}
</div>"""


def set_request(text: str) -> None:
    st.session_state.request = text
    st.session_state.submitted = text
    st.session_state.clarify = ""


def submit() -> None:
    st.session_state.submitted = st.session_state.request
    st.session_state.clarify = ""


def add_details() -> None:
    extra = st.session_state.clarify.strip()
    if extra:
        st.session_state.request = f"{st.session_state.submitted} {extra}"
        st.session_state.submitted = st.session_state.request
    st.session_state.clarify = ""


def main() -> None:
    st.set_page_config(page_title="VibeFinder", page_icon="🎧", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    for key in ("request", "submitted", "clarify"):
        st.session_state.setdefault(key, "")

    songs, kb = load_data()
    client = get_client()

    # ---------------------------------------------------------------- sidebar
    with st.sidebar:
        st.header("Settings")
        use_llm = st.toggle("Use Gemini", value=client is not None, disabled=client is None,
                            help="Parse requests and write explanations with Gemini.")
        if client is None:
            st.caption("No GEMINI_API_KEY found, so the rule-based parser and template explanations are used.")
        few_shot = st.toggle("Few-shot parsing", value=True, disabled=not use_llm,
                             help="Show Gemini 8 labeled examples (data/parse_examples.json) when parsing. "
                                  "Turn off for the plain zero-shot prompt.")
        use_rag = st.toggle("Use RAG (knowledge notes)", value=True,
                            help="Turn off to see the baseline recommender without retrieval.")
        k = st.slider("Number of songs", 3, 8, 5)
        st.divider()
        st.caption(f"Catalog: {len(songs)} songs · Knowledge: {len(kb.genres)} genre notes, "
                   f"{len(kb.activities)} activity notes")

    # ---------------------------------------------------------------- header + input
    st.markdown('<div class="vf-hero"><h1>🎧 VibeFinder</h1>'
                '<p>Describe what you want to hear. I retrieve what I know, rank the catalog, '
                'check my own work, and tell you how sure I am.</p></div>', unsafe_allow_html=True)

    col_input, col_button = st.columns([5, 1])
    with col_input:
        st.text_input("What do you want to hear?", key="request", on_change=submit,
                      placeholder="e.g. calm acoustic music for studying", label_visibility="collapsed")
    with col_button:
        st.button("Find songs", type="primary", on_click=submit, use_container_width=True)

    chip_cols = st.columns(len(EXAMPLES))
    for col, (label, text) in zip(chip_cols, EXAMPLES.items()):
        col.button(label, on_click=set_request, args=(text,), use_container_width=True)

    request = st.session_state.submitted
    if not request:
        st.info("Type a request or pick an example above.")
        return

    agent = VibeFinderAgent(songs=songs, kb=kb, client=client if use_llm else None, use_rag=use_rag, k=k,
                            few_shot=few_shot)
    with st.spinner("Finding your vibe..."):
        result = agent.run(request)
    save_trace(result)

    # ---------------------------------------------------------------- status banner
    if result.status == "rejected":
        st.markdown(f'<div class="vf-banner vf-low">⛔ Blocked by guardrail: {html.escape(result.message)}</div>',
                    unsafe_allow_html=True)
        return

    for warning in result.warnings:
        st.warning(warning, icon="⚠️")

    if result.status == "needs_clarification":
        st.markdown(f'<div class="vf-banner vf-low">🤔 Needs clarification: {html.escape(result.message)}</div>',
                    unsafe_allow_html=True)
        st.text_input("Add details (mood, energy, activity...)", key="clarify", on_change=add_details,
                      placeholder="e.g. something happy for a party")
    elif result.confidence >= 0.75:
        st.markdown(f'<div class="vf-banner vf-high">✅ High confidence: {result.confidence:.2f}</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="vf-banner vf-mid">🟡 Medium confidence: {result.confidence:.2f} '
                    f'(threshold {CONFIDENCE_THRESHOLD})</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------------- song cards
    if result.recommendations:
        st.subheader(result.explanation["intro"])
        st.caption(f"Explanation written by: {'Gemini (verified)' if result.explanation_source == 'llm' else 'scoring reasons (template)'}"
                   f" · Request parsed by: {'Gemini (' + result.parser_source[4:] + ')' if result.parser_source.startswith('llm') else 'rules'}")
        whys = {p["title"].lower(): p["why"] for p in result.explanation["picks"]}
        per_row = 4 if k > 5 else k
        recs = result.recommendations
        for start in range(0, len(recs), per_row):
            cols = st.columns(per_row)
            for offset, (col, rec) in enumerate(zip(cols, recs[start:start + per_row])):
                rank = start + offset + 1
                title = rec["song"]["title"]
                with col:
                    st.markdown(song_card(rank, rec, whys.get(title.lower(), "")), unsafe_allow_html=True)
                    up, down = st.columns(2)
                    if up.button("👍", key=f"up-{request}-{title}", use_container_width=True):
                        save_feedback(request, title, "up")
                        st.toast(f"Thanks! Saved 👍 for {title}")
                    if down.button("👎", key=f"down-{request}-{title}", use_container_width=True):
                        save_feedback(request, title, "down")
                        st.toast(f"Thanks! Saved 👎 for {title}")

    # ---------------------------------------------------------------- how I decided
    with st.expander("🧠 How I decided", expanded=False):
        left, right = st.columns(2)
        with left:
            st.markdown("**Parsed preferences**")
            st.json(result.prefs)
            augment = next((s for s in result.trace if s["step"] == "augment"), None)
            if augment and augment["filled_from_notes"]:
                st.markdown("**Filled in from notes:** " + ", ".join(augment["filled_from_notes"]))
        with right:
            st.markdown("**Retrieved notes**")
            if not result.notes:
                st.caption("None" + (" (RAG is off)" if not use_rag else ""))
            notes = kb.retrieve(request, genre=result.prefs.get("genre"),
                                activity=result.prefs.get("activity")) if use_rag else []
            for note in notes:
                st.markdown(f"- **{note.source} › {note.name}**: {note.text}")
            if use_rag:
                ref = kb.find_song_reference(request)
                if ref is not None:
                    st.markdown(f"- **{ref.source} › {ref.name}** (song you named): {ref.text}")
                for name, terms in kb.sound_matches(request).items():
                    st.markdown(f"- **song_guide.pdf › {name}**: sound match for *{', '.join(terms)}*: "
                                f"{kb.songs[name].fields.get('sound', '')}")
        st.markdown("**Agent trace**")
        for i, step in enumerate(result.trace, start=1):
            details = {k: v for k, v in step.items() if k != "step"}
            ok = details.get("passed", True)
            icon = "✅" if ok else "❌"
            st.markdown(f"{icon} **{i}. {step['step']}**  `{json.dumps(details, default=str)}`")


if __name__ == "__main__":
    main()
