"""News classification evaluation CLI — evaluate classifiers and append to findings log.

Usage
-----
# Evaluate with defaults
python -m news_classification.run_eval

# Evaluate with param overrides
python -m news_classification.run_eval --params geo_threshold=2.0 crypto_weight=1.5

# Print current leaderboard without evaluating
python -m news_classification.run_eval --summary

# Dry run (evaluate but don't write to findings log)
python -m news_classification.run_eval --dry-run

# Show misclassifications
python -m news_classification.run_eval --errors

Autoresearch agent notes
------------------------
- findings.jsonl is the ground truth — read it to compare iterations
- Each --params run creates a new entry; best-per-classifier tracked in findings.py
- Mutation surface: weight multipliers + thresholds in classifier.py
- After proposing mutations, run this CLI, read the accuracy/F1, commit improvements
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_classification import findings
from news_classification.evaluate import evaluate
from news_classification.classifier import KeywordWeighted

CLASSIFIER_REGISTRY: dict = {
    "KeywordWeighted": KeywordWeighted,
}


def parse_params(param_strings: list[str]) -> dict:
    """Parse 'key=value' strings into a typed dict (int > float > str)."""
    result = {}
    for s in param_strings:
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip()
        for cast in (int, float):
            try:
                result[k] = cast(v)
                break
            except ValueError:
                pass
        else:
            result[k] = v
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="News classification evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--classifier", metavar="NAME",
                        choices=list(CLASSIFIER_REGISTRY),
                        help="Classifier to evaluate (default: KeywordWeighted)")
    parser.add_argument("--params", nargs="*", metavar="KEY=VALUE",
                        help="Classifier param overrides, e.g. geo_threshold=2.0")
    parser.add_argument("--summary", action="store_true",
                        help="Print leaderboard and exit")
    parser.add_argument("--errors", action="store_true",
                        help="Show misclassified headlines")
    parser.add_argument("--dry-run", action="store_true",
                        help="Evaluate but do not write to findings log")
    args = parser.parse_args()

    if args.summary:
        print(findings.summary())
        print(f"\nTotal entries in log: {findings.count()}")
        return

    targets = (
        {args.classifier: CLASSIFIER_REGISTRY[args.classifier]}
        if args.classifier
        else CLASSIFIER_REGISTRY
    )
    param_overrides = parse_params(args.params or [])

    for cls_name, ClsClass in targets.items():
        print(f"\nEvaluating {cls_name}...")
        if param_overrides:
            print(f"  Param overrides: {param_overrides}")

        classifier = ClsClass(**param_overrides)
        result = evaluate(classifier)

        # Print summary
        print(f"  Accuracy:    {result['accuracy'] * 100:.1f}%")
        print(f"  Weighted F1: {result['weighted_f1'] * 100:.1f}%")
        print(f"  Correct:     {result['correct']}/{result['total']}")
        print(f"  Errors:      {result['errors']}")

        # Per-category
        print(f"\n  Per-category:")
        for cat, m in sorted(result["per_category"].items()):
            if m["support"] > 0:
                print(f"    {cat:14s}: P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} (n={m['support']})")

        if args.errors and result["confusion"]:
            print(f"\n  Misclassified:")
            for c in result["confusion"]:
                print(f"    [{c['true']} → {c['predicted']}] {c['headline'][:80]}")

        if not args.dry_run:
            findings.append(result)
            print(f"\n  → Appended to findings log ({findings.count()} total entries)")
        else:
            print("\n  → Dry run, not written to findings log")

    print("\nDone.")


if __name__ == "__main__":
    main()
