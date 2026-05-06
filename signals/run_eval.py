"""Signal evaluation CLI — evaluate strategies and append to findings log.

Usage
-----
# Evaluate all registered strategies
python -m signals.run_eval

# Evaluate a specific strategy
python -m signals.run_eval --strategy RiskOffComposite

# Evaluate with param overrides
python -m signals.run_eval --strategy RiskOffComposite --params vix_threshold=25 hold_days=10

# Print current leaderboard without evaluating
python -m signals.run_eval --summary

# Dry run (evaluate but don't write to findings log)
python -m signals.run_eval --dry-run

Autoresearch agent notes
------------------------
- findings.jsonl is the ground truth — read it to compare iterations
- Each --params run creates a new entry; best-per-strategy is tracked in findings.py
- Mutation surface: see docstring in each strategy file
- After proposing mutations, run this CLI, read the sharpe/cagr, commit improvements
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signals import findings
from signals.evaluate import evaluate
from signals.strategies.risk_off import RiskOffComposite
from signals.strategies.vix_term import VIXTermStructure
from signals.strategies.momentum_crossover import MomentumCrossover
from signals.strategies.mean_reversion import MeanReversion
from signals.strategies.gold_copper_momentum import GoldCopperMomentum

STRATEGY_REGISTRY: dict = {
    "RiskOffComposite": RiskOffComposite,
    "VIXTermStructure": VIXTermStructure,
    "MomentumCrossover": MomentumCrossover,
    "MeanReversion": MeanReversion,
    "GoldCopperMomentum": GoldCopperMomentum,
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
        description="Market dashboard signal evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--strategy", metavar="NAME",
                        choices=list(STRATEGY_REGISTRY), help="Strategy to evaluate")
    parser.add_argument("--params", nargs="*", metavar="KEY=VALUE",
                        help="Strategy param overrides, e.g. vix_threshold=25")
    parser.add_argument("--start", default="2010-01-01", metavar="YYYY-MM-DD",
                        help="Backtest start date (default: 2010-01-01)")
    parser.add_argument("--end", metavar="YYYY-MM-DD",
                        help="Backtest end date (default: latest in parquet)")
    parser.add_argument("--summary", action="store_true",
                        help="Print leaderboard and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Evaluate but do not write to findings log")
    args = parser.parse_args()

    if args.summary:
        print(findings.summary())
        print(f"\nTotal entries in log: {findings.count()}")
        return

    targets = (
        {args.strategy: STRATEGY_REGISTRY[args.strategy]}
        if args.strategy
        else STRATEGY_REGISTRY
    )
    param_overrides = parse_params(args.params or [])

    for strat_name, StratClass in targets.items():
        print(f"\nEvaluating {strat_name}...")
        if param_overrides:
            print(f"  Param overrides: {param_overrides}")

        strategy = StratClass(**param_overrides)
        result = evaluate(strategy, start=args.start, end=args.end)

        print(json.dumps(result, indent=2, default=str))

        if not args.dry_run:
            findings.append(result)
            print(f"  → Appended to findings log ({findings.count()} total entries)")
        else:
            print("  → Dry run, not written to findings log")

    print("\nDone.")


if __name__ == "__main__":
    main()
