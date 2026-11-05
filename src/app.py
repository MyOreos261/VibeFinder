"""
VibeFinder 2.0 command-line app.

  python -m src.app "calm lofi for studying"      one request
  python -m src.app                               interactive mode (human-in-the-loop)
  python -m src.app --offline "..."               no LLM: rule parser + template explanation
  python -m src.app --no-rag "..."                baseline: skip the knowledge notes (for comparison)
  python -m src.app --trace "..."                 also print the agent's step-by-step trace

Every run is logged to logs/vibefinder.log and each request's trace is appended
to logs/traces.jsonl.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.agent import AgentResult, VibeFinderAgent
from src.llm import make_client

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_DIR / "vibefinder.log", encoding="utf-8")],
    )


def save_trace(result: AgentResult) -> None:
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "request": result.request, "status": result.status, "confidence": result.confidence,
              "parser": result.parser_source, "explanation": result.explanation_source,
              "trace": result.trace}
    with open(LOG_DIR / "traces.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def render(result: AgentResult, show_trace: bool = False) -> str:
    lines = [f"Request: {result.request}"]
    if result.status == "rejected":
        lines.append(f"[REJECTED] {result.message}")
        return "\n".join(lines)
    shown = {k: v for k, v in result.prefs.items()}
    lines.append(f"Parsed ({result.parser_source}): " + (", ".join(f"{k}={v}" for k, v in shown.items()) or "nothing"))
    if result.notes:
        lines.append("Retrieved notes: " + ", ".join(result.notes))
    for warning in result.warnings:
        lines.append(f"[warning] {warning}")
    if result.recommendations:
        lines.append(f"Confidence: {result.confidence:.2f}")
    if result.status == "needs_clarification":
        lines.append(f"[NEEDS CLARIFICATION] {result.message}")
    if result.explanation:
        lines.append("")
        lines.append(f"{result.explanation['intro']}  (explanation: {result.explanation_source})")
        whys = {p["title"].lower(): p["why"] for p in result.explanation["picks"]}
        for rank, rec in enumerate(result.recommendations, start=1):
            song = rec["song"]
            lines.append(f"{rank}. {song['title']} by {song['artist']}  [{song['genre']}/{song['mood']}, "
                         f"energy {song['energy']:.2f}]  score {rec['score']:.2f}")
            lines.append(f"   {whys.get(song['title'].lower(), '')}")
    if show_trace:
        lines.append("")
        lines.append("Agent trace:")
        for step in result.trace:
            details = {k: v for k, v in step.items() if k != "step"}
            lines.append(f"  - {step['step']}: {json.dumps(details, default=str)}")
    return "\n".join(lines)


def interactive(agent: VibeFinderAgent, show_trace: bool) -> None:
    """Loop that keeps a human in the loop: low-confidence answers ask for more detail."""
    print("VibeFinder 2.0. Describe what you want to hear (blank line to quit).")
    while True:
        try:
            request = input("\n> ").strip()
        except EOFError:
            break
        if not request:
            break
        result = agent.run(request)
        save_trace(result)
        print(render(result, show_trace))
        if result.status == "needs_clarification":
            extra = input("Add details (or press Enter to keep these results): ").strip()
            if extra:
                result = agent.run(f"{request} {extra}")
                save_trace(result)
                print(render(result, show_trace))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="VibeFinder 2.0: natural-language music recommender")
    parser.add_argument("request", nargs="*", help="what you want to listen to")
    parser.add_argument("--offline", action="store_true", help="do not call the LLM")
    parser.add_argument("--no-rag", action="store_true", help="baseline: skip knowledge retrieval")
    parser.add_argument("--trace", action="store_true", help="print the agent trace")
    parser.add_argument("-k", type=int, default=5, help="number of songs to return")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = make_client(offline=args.offline)
    if client is None and not args.offline:
        print("(LLM unavailable: running with the rule-based parser and template explanations. "
              "Set GEMINI_API_KEY in .env to enable Gemini.)\n")
    agent = VibeFinderAgent(client=client, use_rag=not args.no_rag, k=args.k)

    if not args.request:
        interactive(agent, args.trace)
        return 0
    result = agent.run(" ".join(args.request))
    save_trace(result)
    print(render(result, args.trace))
    return 1 if result.status == "rejected" else 0


if __name__ == "__main__":
    sys.exit(main())
