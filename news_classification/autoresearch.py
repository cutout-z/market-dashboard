"""Autoresearch loop — automated parameter mutation and evaluation for news classifiers.

Implements Karpathy's autoresearch pattern: read findings, propose mutations,
evaluate, log results, report winners. Designed to be run by Claude Code
agent or manually from CLI.

Usage
-----
# Full sweep — 10 mutations (default)
python -m news_classification.autoresearch

# More mutations
python -m news_classification.autoresearch --mutations 20

# Report: analyse findings log and suggest next mutations
python -m news_classification.autoresearch --report

# Dry run — evaluate but don't log
python -m news_classification.autoresearch --dry-run

Mutation strategies
-------------------
1. Perturbation — ±10-30% of current best value, 1 param at a time
2. Boundary — try edges of the defined mutation range
3. Random uniform — sample within the full range
4. Combo — mutate 2 params simultaneously (perturbation on both)

Each mutation is evaluated against the labeled dataset.
Winners (accuracy > current best) are flagged in the output.
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_classification import findings
from news_classification.evaluate import evaluate
from news_classification.classifier import KeywordWeighted

CLASSIFIER_REGISTRY: dict = {
    "KeywordWeighted": KeywordWeighted,
}

# Mutation ranges for each classifier's params.
# Format: {classifier_name: {param_name: (min, max, type)}}
MUTATION_RANGES: dict = {
    "KeywordWeighted": {
        # Weight multipliers
        "geo_weight": (0.3, 3.0, float),
        "macro_weight": (0.3, 3.0, float),
        "trade_weight": (0.3, 3.0, float),
        "earnings_weight": (0.3, 3.0, float),
        "tech_weight": (0.3, 3.0, float),
        "energy_weight": (0.3, 3.0, float),
        "crypto_weight": (0.3, 3.0, float),
        # Thresholds
        "geo_threshold": (0.5, 4.0, float),
        "macro_threshold": (0.5, 4.0, float),
        "trade_threshold": (0.5, 4.0, float),
        "earnings_threshold": (0.5, 4.0, float),
        "tech_threshold": (0.5, 4.0, float),
        "energy_threshold": (0.5, 4.0, float),
        "crypto_threshold": (0.5, 4.0, float),
    },
}


def _get_best_params(classifier_name: str, ClsClass) -> dict:
    """Get the best known params for a classifier from findings, or defaults."""
    bests = findings.best_by_classifier()
    if classifier_name in bests:
        return bests[classifier_name].get("metadata", {}).get("params", ClsClass.default_params)
    return dict(ClsClass.default_params)


def _clamp(value, lo, hi):
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def _perturb_param(value, lo, hi, param_type, magnitude=0.2):
    """Perturb a single param by ±magnitude fraction within [lo, hi]."""
    if param_type == int:
        delta = max(1, int(abs(value) * magnitude))
        new_val = value + random.choice([-1, 1]) * random.randint(1, delta)
        return _clamp(int(new_val), int(lo), int(hi))
    else:
        span = abs(value) * magnitude if value != 0 else (hi - lo) * 0.1
        new_val = value + random.uniform(-span, span)
        return _clamp(round(new_val, 4), lo, hi)


def _random_param(lo, hi, param_type):
    """Sample uniformly from [lo, hi]."""
    if param_type == int:
        return random.randint(int(lo), int(hi))
    else:
        return round(random.uniform(lo, hi), 4)


def generate_mutations(
    classifier_name: str,
    base_params: dict,
    n_mutations: int,
) -> list[dict]:
    """Generate n_mutations param sets using mixed mutation strategies."""
    ranges = MUTATION_RANGES.get(classifier_name, {})
    if not ranges:
        return []

    param_names = list(ranges.keys())
    mutations = []

    for i in range(n_mutations):
        new_params = dict(base_params)
        strategy_type = i % 4  # rotate through mutation types

        if strategy_type == 0:
            # Perturbation — mutate 1 param
            key = random.choice(param_names)
            lo, hi, ptype = ranges[key]
            new_params[key] = _perturb_param(base_params[key], lo, hi, ptype)

        elif strategy_type == 1:
            # Boundary — try an edge value for 1 param
            key = random.choice(param_names)
            lo, hi, ptype = ranges[key]
            edge = random.choice([lo, hi])
            new_params[key] = int(edge) if ptype == int else edge

        elif strategy_type == 2:
            # Random uniform — 1 param from full range
            key = random.choice(param_names)
            lo, hi, ptype = ranges[key]
            new_params[key] = _random_param(lo, hi, ptype)

        elif strategy_type == 3:
            # Combo — perturb 2 params simultaneously
            keys = random.sample(param_names, min(2, len(param_names)))
            for key in keys:
                lo, hi, ptype = ranges[key]
                new_params[key] = _perturb_param(base_params[key], lo, hi, ptype)

        # Skip if identical to base
        if new_params != base_params:
            mutations.append(new_params)

    return mutations


def run_sweep(
    classifier_name: str | None = None,
    n_mutations: int = 10,
    dry_run: bool = False,
) -> list[dict]:
    """Run autoresearch sweep: baseline + mutations for each classifier.

    Returns list of all results (including whether each is a new best).
    """
    targets = (
        {classifier_name: CLASSIFIER_REGISTRY[classifier_name]}
        if classifier_name
        else CLASSIFIER_REGISTRY
    )

    bests = findings.best_by_classifier()
    all_results = []

    for cls_name, ClsClass in targets.items():
        best_acc = bests.get(cls_name, {}).get("accuracy", 0.0)
        best_params = _get_best_params(cls_name, ClsClass)

        print(f"\n{'='*60}")
        print(f"  {cls_name} — current best accuracy: {best_acc * 100:.1f}%")
        print(f"  Base params: {best_params}")
        print(f"{'='*60}")

        # If no prior findings, run baseline first
        if cls_name not in bests:
            print(f"\n  [baseline] Running with defaults...")
            classifier = ClsClass()
            result = evaluate(classifier)
            result["_mutation"] = "baseline"
            best_acc = result["accuracy"]

            if not dry_run:
                findings.append(result)

            _print_result(result, best_acc, is_baseline=True)
            all_results.append(result)
            best_params = dict(ClsClass.default_params)

        # Generate and evaluate mutations
        mutations = generate_mutations(cls_name, best_params, n_mutations)
        print(f"\n  Generated {len(mutations)} mutations")

        winners = 0
        for j, params in enumerate(mutations):
            # Find which params changed
            changed = {k: v for k, v in params.items() if v != best_params.get(k)}
            print(f"\n  [{j+1}/{len(mutations)}] Δ {changed}")

            classifier = ClsClass(**params)
            result = evaluate(classifier)
            result["_mutation"] = changed

            if not dry_run:
                findings.append(result)

            is_winner = result["accuracy"] > best_acc
            if is_winner:
                winners += 1
                best_acc = result["accuracy"]
                best_params = dict(params)

            _print_result(result, best_acc, is_winner=is_winner)
            all_results.append(result)

        print(f"\n  {cls_name} sweep complete: {winners} winners from {len(mutations)} mutations")
        if winners > 0:
            print(f"  New best accuracy: {best_acc * 100:.1f}%")
            print(f"  New best params: {best_params}")

    return all_results


def _print_result(result: dict, best_acc: float, is_baseline: bool = False, is_winner: bool = False):
    """Print a single evaluation result."""
    marker = "★ NEW BEST" if is_winner else ("◆ BASELINE" if is_baseline else "  ")
    acc = result["accuracy"] * 100
    f1 = result.get("weighted_f1", 0) * 100
    total = result["total"]
    correct = result["correct"]
    errors = result["errors"]
    print(f"  {marker} Acc {acc:.1f}% | W-F1 {f1:.1f}% | {correct}/{total} correct | {errors} errors")


def report():
    """Analyse the findings log and print insights."""
    all_entries = findings.read_all()
    bests = findings.best_by_classifier()

    if not all_entries:
        print("No findings yet. Run: python -m news_classification.autoresearch")
        return

    print(f"\n{'='*60}")
    print(f"  NEWS CLASSIFICATION AUTORESEARCH REPORT")
    print(f"  Total evaluations: {len(all_entries)}")
    print(f"  Classifiers tested: {len(bests)}")
    print(f"{'='*60}")

    print(f"\n{findings.summary()}")

    # Per-classifier analysis
    for cls_name, best in sorted(bests.items(), key=lambda x: x[1].get("accuracy", 0), reverse=True):
        cls_entries = [e for e in all_entries if e.get("metadata", {}).get("classifier") == cls_name]
        accs = [e["accuracy"] for e in cls_entries]

        print(f"\n--- {cls_name} ({len(cls_entries)} runs) ---")
        print(f"  Best accuracy:  {max(accs) * 100:.1f}%")
        print(f"  Worst accuracy: {min(accs) * 100:.1f}%")
        print(f"  Mean accuracy:  {sum(accs)/len(accs) * 100:.1f}%")
        print(f"  Best params:    {best.get('metadata', {}).get('params', {})}")

        # Per-category breakdown from best result
        per_cat = best.get("per_category", {})
        if per_cat:
            print(f"  Per-category (best run):")
            for cat, metrics in sorted(per_cat.items()):
                if metrics.get("support", 0) > 0:
                    print(f"    {cat:14s}: P={metrics['precision']:.2f} R={metrics['recall']:.2f} F1={metrics['f1']:.2f} (n={metrics['support']})")

        # Coverage analysis
        ranges = MUTATION_RANGES.get(cls_name, {})
        if ranges:
            print(f"  Param coverage:")
            for param, (lo, hi, ptype) in ranges.items():
                values = [e.get("metadata", {}).get("params", {}).get(param) for e in cls_entries]
                values = [v for v in values if v is not None]
                if values:
                    print(f"    {param}: tested [{min(values):.2f}, {max(values):.2f}] of range [{lo}, {hi}]")
                else:
                    print(f"    {param}: UNTESTED (range [{lo}, {hi}])")

        # Top confusion patterns
        all_confusion = []
        for e in cls_entries:
            all_confusion.extend(e.get("confusion", []))
        if all_confusion:
            pattern_counts: dict[tuple, int] = {}
            for c in all_confusion:
                key = (c["true"], c["predicted"])
                pattern_counts[key] = pattern_counts.get(key, 0) + 1
            top = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"  Top confusion patterns:")
            for (true, pred), cnt in top:
                print(f"    {true} → {pred}: {cnt} times")


def main():
    parser = argparse.ArgumentParser(
        description="Autoresearch loop — automated news classification mutation and evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--classifier", metavar="NAME",
                        choices=list(CLASSIFIER_REGISTRY),
                        help="Classifier to sweep (default: all)")
    parser.add_argument("--mutations", type=int, default=10, metavar="N",
                        help="Number of mutations per classifier (default: 10)")
    parser.add_argument("--report", action="store_true",
                        help="Print findings analysis and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Evaluate but don't write to findings log")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible mutations")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if args.report:
        report()
        return

    results = run_sweep(
        classifier_name=args.classifier,
        n_mutations=args.mutations,
        dry_run=args.dry_run,
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"  SWEEP COMPLETE")
    print(f"  Total evaluations: {len(results)}")
    print(f"{'='*60}")

    if not args.dry_run:
        print(f"\nUpdated leaderboard:")
        print(findings.summary())
        print(f"\nTotal entries in log: {findings.count()}")
    else:
        print("\n(dry run — nothing written to findings log)")


if __name__ == "__main__":
    main()
