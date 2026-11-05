"""
Specialization eval: does the few-shot prompt parse requests better than the plain one?

Scores parsers on the held-out 'test' split of data/parse_examples.json (the 'train'
split is what the few-shot prompt shows the model, so there is no overlap).

  python -m eval.parse_eval                 rule-based parser only (offline baseline)
  python -m eval.parse_eval --llm           rules vs. Gemini zero-shot vs. Gemini few-shot

A field counts as correct when it equals the label (null must stay null). Energy is
correct when both are null or the values are within 0.2 of each other.
Results are written to eval/results_parse.md.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List

from src.guardrails import validate_prefs
from src.knowledge import KnowledgeBase
from src.llm import make_client
from src.parser import load_examples, parse_with_llm, parse_with_rules
from src.recommender import load_songs

HERE = Path(__file__).resolve().parent
FIELDS = ["genre", "mood", "energy", "likes_acoustic", "activity"]
ENERGY_TOLERANCE = 0.2


def field_correct(field: str, predicted, expected) -> bool:
    if field == "energy":
        if predicted is None or expected is None:
            return predicted is None and expected is None
        return abs(float(predicted) - float(expected)) <= ENERGY_TOLERANCE
    return predicted == expected


def normalize(raw: Dict, kb: KnowledgeBase, catalog_genres, catalog_moods) -> Dict:
    """Run the same validation the agent uses, then fill missing keys with None."""
    prefs, _ = validate_prefs(raw or {}, catalog_genres, set(kb.genres), catalog_moods)
    return {f: prefs.get(f) for f in FIELDS}


def score(name: str, parse: Callable[[str], Dict], cases: List[Dict], kb, catalog_genres, catalog_moods):
    per_field = {f: 0 for f in FIELDS}
    exact = 0
    misses = []
    for case in cases:
        predicted = normalize(parse(case["request"]), kb, catalog_genres, catalog_moods)
        wrong = [f for f in FIELDS if not field_correct(f, predicted[f], case["expected"][f])]
        for f in FIELDS:
            per_field[f] += f not in wrong
        exact += not wrong
        if wrong:
            misses.append((case["request"], {f: (predicted[f], case["expected"][f]) for f in wrong}))
    n = len(cases)
    field_acc = sum(per_field.values()) / (n * len(FIELDS))
    return {"name": name, "per_field": {f: per_field[f] / n for f in FIELDS},
            "field_acc": field_acc, "exact": exact / n, "misses": misses}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also score Gemini zero-shot and few-shot")
    parser.add_argument("--show-misses", action="store_true", help="print every wrong field")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    kb = KnowledgeBase.load()
    songs = load_songs(str(HERE.parent / "data" / "songs.csv"), verbose=False)
    catalog_genres = {s["genre"] for s in songs}
    catalog_moods = {s["mood"] for s in songs}
    cases = load_examples("test")

    parsers = [("rules (baseline)", lambda text: parse_with_rules(text, kb))]
    if args.llm:
        from dotenv import load_dotenv
        load_dotenv(HERE.parent / ".env")
        client = make_client()
        if client is None:
            print("GEMINI_API_KEY not available; cannot run --llm.")
            return 2
        parsers += [
            ("gemini zero-shot", lambda t: parse_with_llm(t, kb, catalog_moods, client, few_shot=False)),
            ("gemini few-shot", lambda t: parse_with_llm(t, kb, catalog_moods, client, few_shot=True)),
        ]

    results = [score(name, fn, cases, kb, catalog_genres, catalog_moods) for name, fn in parsers]

    header = "| Parser | " + " | ".join(FIELDS) + " | Field accuracy | Exact match |"
    rows = [header, "|" + " --- |" * (len(FIELDS) + 3)]
    for r in results:
        rows.append(f"| {r['name']} | " + " | ".join(f"{r['per_field'][f]:.0%}" for f in FIELDS)
                    + f" | {r['field_acc']:.0%} | {r['exact']:.0%} |")
    print(f"Parse accuracy on {len(cases)} held-out requests\n")
    print("\n".join(rows))

    for r in results:
        if args.show_misses or len(results) == 1:
            print(f"\nMisses for {r['name']} (predicted, expected):")
            for request, wrong in r["misses"]:
                print(f"  - {request!r}: {wrong}")

    out = HERE / "results_parse.md"
    body = [f"# Parse accuracy ({len(cases)} held-out requests)", "", *rows, ""]
    for r in results:
        body.append(f"## Misses: {r['name']}")
        body += [f"- `{request}`: {wrong}" for request, wrong in r["misses"]] or ["- none"]
        body.append("")
    out.write_text("\n".join(body), encoding="utf-8")
    print(f"\nTable written to {out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
