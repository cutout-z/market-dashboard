"""Autoresearch loop — automated parameter mutation and evaluation.

Implements Karpathy's autoresearch pattern: read findings, propose mutations,
evaluate, log results, report winners. Designed to be run by Claude Code
agent or manually from CLI.

Usage
-----
# Full sweep — 10 mutations per strategy (default)
python -m signals.autoresearch

# Single strategy, more mutations
python -m signals.autoresearch --strategy RiskOffComposite --mutations 20

# Report: analyse findings log and suggest next mutations
python -m signals.autoresearch --report

# Dry run — evaluate but don't log
python -m signals.autoresearch --dry-run

Mutation strategies
-------------------
1. Perturbation — ±10-30% of current best value, 1 param at a time
2. Boundary — try edges of the defined mutation range
3. Random uniform — sample within the full range
4. Combo — mutate 2 params simultaneously (perturbation on both)

Each mutation is evaluated against the full backtest period.
Winners (Sharpe > current best) are flagged in the output.
"""
import argparse
import json
import random
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
from signals.strategies.audusd_rate_shock import AUDUSDRateShock

STRATEGY_REGISTRY: dict = {
    "RiskOffComposite": RiskOffComposite,
    "VIXTermStructure": VIXTermStructure,
    "MomentumCrossover": MomentumCrossover,
    "MeanReversion": MeanReversion,
    "GoldCopperMomentum": GoldCopperMomentum,
    "AUDUSDRateShock": AUDUSDRateShock,
}

# Mutation ranges for each strategy's params.
# Format: {strategy_name: {param_name: (min, max, type)}}
MUTATION_RANGES: dict = {
    "RiskOffComposite": {
        "vix_threshold": (15.0, 30.0, float),
        "copper_gold_lookback": (3, 15, int),
        "copper_gold_change": (-0.07, -0.01, float),
        "dxy_breakout_days": (5, 30, int),
        "conditions_required": (1, 4, int),
        "hold_days": (1, 10, int),
    },
    "VIXTermStructure": {
        "vix_floor": (12.0, 25.0, float),
        "hold_days": (1, 10, int),
    },
    "MomentumCrossover": {
        "fast_period": (5, 50, int),
        "slow_period": (50, 250, int),
        "hold_days": (1, 10, int),
    },
    "MeanReversion": {
        "lookback": (20, 200, int),
        "z_upper": (1.0, 3.0, float),
        "hold_days": (1, 10, int),
    },
    "GoldCopperMomentum": {
        "lookback": (3, 30, int),
        "roc_threshold": (-0.10, -0.01, float),
        "hold_days": (1, 15, int),
        "smooth_period": (1, 10, int),
    },
    "AUDUSDRateShock": {
        "rate_lookback": (2, 20, int),
        "rate_shock_bps": (8.0, 50.0, float),
        "rate_relief_bps": (-40.0, -5.0, float),
        "dxy_lookback": (2, 20, int),
        "dxy_shock": (0.005, 0.04, float),
        "dxy_relief": (-0.03, -0.003, float),
        "vix_floor": (14.0, 35.0, float),
        "commodity_lookback": (5, 60, int),
        "commodity_threshold": (0.005, 0.08, float),
        "conditions_required": (1, 3, int),
        "hold_days": (1, 20, int),
    },
}


def _get_best_params(strategy_name: str, StratClass) -> dict:
    """Get the best known params for a strategy from findings, or defaults."""
    bests = findings.best_by_strategy()
    if strategy_name in bests:
        return bests[strategy_name].get("metadata", {}).get("params", StratClass.default_params)
    return dict(StratClass.default_params)


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
    strategy_name: str,
    base_params: dict,
    n_mutations: int,
) -> list[dict]:
    """Generate n_mutations param sets using mixed mutation strategies."""
    ranges = MUTATION_RANGES.get(strategy_name, {})
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
    strategy_name: str | None = None,
    n_mutations: int = 10,
    dry_run: bool = False,
    start: str = "2010-01-01",
    end: str | None = None,
) -> list[dict]:
    """Run autoresearch sweep: baseline + mutations for each strategy.

    Returns list of all results (including whether each is a new best).
    """
    targets = (
        {strategy_name: STRATEGY_REGISTRY[strategy_name]}
        if strategy_name
        else STRATEGY_REGISTRY
    )

    bests = findings.best_by_strategy()
    all_results = []

    for strat_name, StratClass in targets.items():
        best_sharpe = bests.get(strat_name, {}).get("sharpe", float("-inf"))
        best_params = _get_best_params(strat_name, StratClass)

        print(f"\n{'='*60}")
        print(f"  {strat_name} — current best Sharpe: {best_sharpe}")
        print(f"  Base params: {best_params}")
        print(f"{'='*60}")

        # If no prior findings, run baseline first
        if strat_name not in bests:
            print(f"\n  [baseline] Running with defaults...")
            strategy = StratClass()
            result = evaluate(strategy, start=start, end=end)
            result["_mutation"] = "baseline"
            best_sharpe = result["sharpe"]

            if not dry_run:
                findings.append(result)

            _print_result(result, best_sharpe, is_baseline=True)
            all_results.append(result)
            best_params = dict(StratClass.default_params)

        # Generate and evaluate mutations
        mutations = generate_mutations(strat_name, best_params, n_mutations)
        print(f"\n  Generated {len(mutations)} mutations")

        winners = 0
        for j, params in enumerate(mutations):
            # Find which params changed
            changed = {k: v for k, v in params.items() if v != best_params.get(k)}
            print(f"\n  [{j+1}/{len(mutations)}] Δ {changed}")

            strategy = StratClass(**params)
            result = evaluate(strategy, start=start, end=end)
            result["_mutation"] = changed

            if not dry_run:
                findings.append(result)

            is_winner = result["sharpe"] > best_sharpe
            if is_winner:
                winners += 1
                best_sharpe = result["sharpe"]
                best_params = dict(params)

            _print_result(result, best_sharpe, is_winner=is_winner)
            all_results.append(result)

        print(f"\n  {strat_name} sweep complete: {winners} winners from {len(mutations)} mutations")
        if winners > 0:
            print(f"  New best Sharpe: {best_sharpe:.4f}")
            print(f"  New best params: {best_params}")

    return all_results


def _print_result(result: dict, best_sharpe: float, is_baseline: bool = False, is_winner: bool = False):
    """Print a single evaluation result."""
    marker = "★ NEW BEST" if is_winner else ("◆ BASELINE" if is_baseline else "  ")
    sharpe = result["sharpe"]
    cagr = result.get("cagr", 0) * 100
    hit = result.get("hit_rate", 0) * 100
    dd = result.get("max_drawdown", 0) * 100
    trades = result.get("trade_count", "?")
    bh = result.get("bh_sharpe", 0)
    print(f"  {marker} Sharpe {sharpe:.4f} (B&H {bh:.3f}) | CAGR {cagr:.1f}% | Hit {hit:.1f}% | DD {dd:.1f}% | Trades {trades}")


def report():
    """Analyse the findings log and print insights."""
    all_entries = findings.read_all()
    bests = findings.best_by_strategy()

    if not all_entries:
        print("No findings yet. Run: python -m signals.autoresearch")
        return

    print(f"\n{'='*60}")
    print(f"  AUTORESEARCH FINDINGS REPORT")
    print(f"  Total evaluations: {len(all_entries)}")
    print(f"  Strategies tested: {len(bests)}")
    print(f"{'='*60}")

    print(f"\n{findings.summary()}")

    # Per-strategy analysis
    for strat_name, best in sorted(bests.items(), key=lambda x: x[1].get("sharpe", 0), reverse=True):
        strat_entries = [e for e in all_entries if e.get("metadata", {}).get("strategy") == strat_name]
        sharpes = [e["sharpe"] for e in strat_entries]
        bh_sharpe = best.get("bh_sharpe", 0)

        print(f"\n--- {strat_name} ({len(strat_entries)} runs) ---")
        print(f"  Best Sharpe:  {max(sharpes):.4f}")
        print(f"  Worst Sharpe: {min(sharpes):.4f}")
        print(f"  Mean Sharpe:  {sum(sharpes)/len(sharpes):.4f}")
        print(f"  B&H Sharpe:   {bh_sharpe:.4f}")
        print(f"  Best params:  {best.get('metadata', {}).get('params', {})}")

        # Coverage analysis — which params have been explored?
        ranges = MUTATION_RANGES.get(strat_name, {})
        if ranges:
            print(f"  Param coverage:")
            for param, (lo, hi, ptype) in ranges.items():
                values = [e.get("metadata", {}).get("params", {}).get(param) for e in strat_entries]
                values = [v for v in values if v is not None]
                if values:
                    print(f"    {param}: tested [{min(values)}, {max(values)}] of range [{lo}, {hi}]")
                else:
                    print(f"    {param}: UNTESTED (range [{lo}, {hi}])")


def main():
    parser = argparse.ArgumentParser(
        description="Autoresearch loop — automated signal mutation and evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--strategy", metavar="NAME",
                        choices=list(STRATEGY_REGISTRY),
                        help="Strategy to sweep (default: all)")
    parser.add_argument("--mutations", type=int, default=10, metavar="N",
                        help="Number of mutations per strategy (default: 10)")
    parser.add_argument("--start", default="2010-01-01", metavar="YYYY-MM-DD",
                        help="Backtest start date")
    parser.add_argument("--end", metavar="YYYY-MM-DD",
                        help="Backtest end date")
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
        strategy_name=args.strategy,
        n_mutations=args.mutations,
        dry_run=args.dry_run,
        start=args.start,
        end=args.end,
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"  SWEEP COMPLETE")
    print(f"  Total evaluations: {len(results)}")
    winners = [r for r in results if r.get("_mutation") != "baseline" and r["sharpe"] > 0]
    print(f"{'='*60}")

    if not args.dry_run:
        print(f"\nUpdated leaderboard:")
        print(findings.summary())
        print(f"\nTotal entries in log: {findings.count()}")
    else:
        print("\n(dry run — nothing written to findings log)")


if __name__ == "__main__":
    main()
