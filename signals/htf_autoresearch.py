"""Higher-timeframe autoresearch runner.

This is the slower, robustness-first companion to signals.autoresearch. It is
designed for monthly/weekly strategies where parameter stability and drawdown
control matter more than repeatedly poking the same daily backtest.

Usage
-----
python -m signals.htf_autoresearch
python -m signals.htf_autoresearch --mutations 30
python -m signals.htf_autoresearch --report
python -m signals.htf_autoresearch --dry-run
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signals import findings
from signals.robustness import evaluate_augmented
from signals.strategies.monthly_trend import (
    CopperMonthlyTrend,
    CrudeMonthlyTrend,
    GoldMonthlyTrend,
    MonthlyTrendRegime,
)


STRATEGY_REGISTRY: dict = {
    "MonthlyTrendRegime": MonthlyTrendRegime,
    "GoldMonthlyTrend": GoldMonthlyTrend,
    "CrudeMonthlyTrend": CrudeMonthlyTrend,
    "CopperMonthlyTrend": CopperMonthlyTrend,
}

MONTHLY_TREND_RANGES = {
    "ma_months": (6, 15, int),
    "confirm_months": (1, 3, int),
    "defensive_buffer": (-0.03, 0.05, float),
    "hold_months": (1, 4, int),
}

MUTATION_RANGES: dict = {
    name: dict(MONTHLY_TREND_RANGES) for name in STRATEGY_REGISTRY
}


def best_by_objective() -> dict[str, dict]:
    """Return the highest-objective result for each higher-timeframe strategy."""
    best: dict[str, dict] = {}
    for entry in findings.read_all():
        name = entry.get("metadata", {}).get("strategy", "unknown")
        if name not in STRATEGY_REGISTRY:
            continue
        objective = entry.get("objective", float("-inf"))
        if name not in best or objective > best[name].get("objective", float("-inf")):
            best[name] = entry
    return best


def _get_best_params(strategy_name: str, StratClass) -> dict:
    bests = best_by_objective()
    if strategy_name in bests:
        return bests[strategy_name].get("metadata", {}).get("params", StratClass.default_params)
    return dict(StratClass.default_params)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _perturb_param(value, lo, hi, param_type, magnitude=0.2):
    if param_type == int:
        delta = max(1, int(abs(value) * magnitude))
        new_val = value + random.choice([-1, 1]) * random.randint(1, delta)
        return _clamp(int(new_val), int(lo), int(hi))
    span = abs(value) * magnitude if value != 0 else (hi - lo) * 0.1
    new_val = value + random.uniform(-span, span)
    return _clamp(round(new_val, 4), lo, hi)


def _random_param(lo, hi, param_type):
    if param_type == int:
        return random.randint(int(lo), int(hi))
    return round(random.uniform(lo, hi), 4)


def generate_mutations(strategy_name: str, base_params: dict, n_mutations: int) -> list[dict]:
    ranges = MUTATION_RANGES.get(strategy_name, {})
    param_names = list(ranges.keys())
    mutations = []

    for i in range(n_mutations):
        new_params = dict(base_params)
        mutation_type = i % 4

        if mutation_type == 0:
            key = random.choice(param_names)
            lo, hi, ptype = ranges[key]
            new_params[key] = _perturb_param(base_params[key], lo, hi, ptype)
        elif mutation_type == 1:
            key = random.choice(param_names)
            lo, hi, ptype = ranges[key]
            edge = random.choice([lo, hi])
            new_params[key] = int(edge) if ptype == int else edge
        elif mutation_type == 2:
            key = random.choice(param_names)
            lo, hi, ptype = ranges[key]
            new_params[key] = _random_param(lo, hi, ptype)
        else:
            keys = random.sample(param_names, min(2, len(param_names)))
            for key in keys:
                lo, hi, ptype = ranges[key]
                new_params[key] = _perturb_param(base_params[key], lo, hi, ptype)

        if new_params != base_params:
            mutations.append(new_params)

    return mutations


def run_sweep(
    strategy_name: str | None = None,
    n_mutations: int = 10,
    dry_run: bool = False,
    start: str = "2000-01-01",
    end: str | None = None,
) -> list[dict]:
    targets = (
        {strategy_name: STRATEGY_REGISTRY[strategy_name]}
        if strategy_name
        else STRATEGY_REGISTRY
    )
    bests = best_by_objective()
    all_results = []

    for strat_name, StratClass in targets.items():
        best_objective = bests.get(strat_name, {}).get("objective", float("-inf"))
        best_params = _get_best_params(strat_name, StratClass)

        print(f"\n{'=' * 60}")
        print(f"  {strat_name} - current best objective: {best_objective}")
        print(f"  Base params: {best_params}")
        print(f"{'=' * 60}")

        if strat_name not in bests:
            print("\n  [baseline] Running with defaults...")
            result = evaluate_augmented(StratClass(), start=start, end=end)
            result["_mutation"] = "baseline"
            best_objective = result["objective"]
            best_params = dict(StratClass.default_params)
            if not dry_run:
                findings.append(result)
            _print_result(result, is_baseline=True)
            all_results.append(result)

        mutations = generate_mutations(strat_name, best_params, n_mutations)
        print(f"\n  Generated {len(mutations)} mutations")

        winners = 0
        for idx, params in enumerate(mutations):
            changed = {k: v for k, v in params.items() if v != best_params.get(k)}
            print(f"\n  [{idx + 1}/{len(mutations)}] delta {changed}")

            result = evaluate_augmented(StratClass(**params), start=start, end=end)
            result["_mutation"] = changed

            if not dry_run:
                findings.append(result)

            is_winner = result["objective"] > best_objective
            if is_winner:
                winners += 1
                best_objective = result["objective"]
                best_params = dict(params)

            _print_result(result, is_winner=is_winner)
            all_results.append(result)

        print(f"\n  {strat_name} sweep complete: {winners} objective winners from {len(mutations)} mutations")
        print(f"  Best objective now: {best_objective:.4f}")
        print(f"  Best params now: {best_params}")

    return all_results


def report() -> None:
    all_entries = [
        e for e in findings.read_all()
        if e.get("metadata", {}).get("strategy") in STRATEGY_REGISTRY
    ]
    bests = best_by_objective()

    if not all_entries:
        print("No HTF findings yet. Run: python -m signals.htf_autoresearch")
        return

    print(f"\n{'=' * 60}")
    print("  HIGHER-TIMEFRAME AUTORESEARCH REPORT")
    print(f"  Total HTF evaluations: {len(all_entries)}")
    print(f"  Strategies tested: {len(bests)}")
    print(f"{'=' * 60}")

    rows = [
        "| Strategy | Objective | Sharpe | B&H Sharpe | CAGR | Max DD | Exposure | WF Sharpe | WF B&H Beat | Params |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, entry in sorted(bests.items(), key=lambda x: x[1].get("objective", 0), reverse=True):
        wf = entry.get("walk_forward", {})
        params = entry.get("metadata", {}).get("params", {})
        rows.append(
            f"| {name} "
            f"| {entry.get('objective', float('nan')):.3f} "
            f"| {entry.get('sharpe', float('nan')):.3f} "
            f"| {entry.get('bh_sharpe', float('nan')):.3f} "
            f"| {entry.get('cagr', 0) * 100:.1f}% "
            f"| {entry.get('max_drawdown', 0) * 100:.1f}% "
            f"| {entry.get('exposure', 0) * 100:.0f}% "
            f"| {wf.get('mean_sharpe', float('nan')):.3f} "
            f"| {wf.get('beats_bh_sharpe_rate', 0) * 100:.0f}% "
            f"| {params} |"
        )
    print("\n".join(rows))

    for name, entry in bests.items():
        strat_entries = [e for e in all_entries if e.get("metadata", {}).get("strategy") == name]
        objectives = [e.get("objective", 0) for e in strat_entries]
        print(f"\n--- {name} ({len(strat_entries)} runs) ---")
        print(f"  Best objective:  {max(objectives):.4f}")
        print(f"  Worst objective: {min(objectives):.4f}")
        print(f"  Mean objective:  {sum(objectives) / len(objectives):.4f}")
        print(f"  Best params:     {entry.get('metadata', {}).get('params', {})}")
        wf = entry.get("walk_forward", {})
        if wf:
            print(
                "  Walk-forward:    "
                f"{wf.get('window_count', 0)} windows, "
                f"mean Sharpe {wf.get('mean_sharpe', float('nan')):.3f}, "
                f"beats B&H Sharpe {wf.get('beats_bh_sharpe_rate', 0) * 100:.0f}%"
            )


def _print_result(result: dict, is_baseline: bool = False, is_winner: bool = False) -> None:
    marker = "NEW BEST" if is_winner else ("BASELINE" if is_baseline else "")
    wf = result.get("walk_forward", {})
    print(
        f"  {marker:8s} Obj {result['objective']:.4f} | "
        f"Sharpe {result['sharpe']:.4f} (B&H {result['bh_sharpe']:.3f}) | "
        f"CAGR {result['cagr'] * 100:.1f}% | "
        f"DD {result['max_drawdown'] * 100:.1f}% | "
        f"Exposure {result.get('exposure', 0) * 100:.0f}% | "
        f"WF Sharpe {wf.get('mean_sharpe', float('nan')):.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Higher-timeframe signal autoresearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--strategy", choices=list(STRATEGY_REGISTRY), help="Strategy to sweep")
    parser.add_argument("--mutations", type=int, default=10, help="Mutations per strategy")
    parser.add_argument("--start", default="2000-01-01", help="Backtest start date")
    parser.add_argument("--end", help="Backtest end date")
    parser.add_argument("--report", action="store_true", help="Print HTF findings report and exit")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writing findings")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if args.report:
        report()
        return

    results = run_sweep(
        strategy_name=args.strategy,
        n_mutations=args.mutations,
        dry_run=args.dry_run,
        start=args.start,
        end=args.end,
    )

    print(f"\n{'=' * 60}")
    print("  HTF SWEEP COMPLETE")
    print(f"  Total evaluations: {len(results)}")
    print(f"{'=' * 60}")

    if args.dry_run:
        print("\n(dry run - nothing written to findings log)")
    else:
        print("\nUpdated HTF leaderboard:")
        report()


if __name__ == "__main__":
    main()
