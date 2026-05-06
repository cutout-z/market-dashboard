"""Robustness scoring helpers for signal autoresearch.

The original harness ranks by full-period Sharpe. These helpers keep that
metric but add a composite objective and rolling-window checks so higher
timeframe strategies are judged on durability, not just one lucky backtest.
"""
from __future__ import annotations

import math

import pandas as pd

from .evaluate import TRADING_DAYS, _cagr, _load_prices, _max_drawdown, evaluate
from .strategy import BaseStrategy


def evaluate_augmented(
    strategy: BaseStrategy,
    start: str = "2010-01-01",
    end: str | None = None,
    friction: float = 0.0005,
    walk_forward: bool = True,
    window_years: int = 5,
    step_years: int = 1,
) -> dict:
    """Run the normal backtest and add objective + robustness fields."""
    result = evaluate(strategy, start=start, end=end, friction=friction)
    result["bh_max_drawdown"] = _round(_buy_hold_max_drawdown(strategy, start, end))
    result["exposure"] = _round(_exposure(strategy, start, end))
    result["objective"] = _round(_objective_score(result))

    if walk_forward:
        result["walk_forward"] = evaluate_walk_forward(
            strategy,
            start=start,
            end=end,
            friction=friction,
            window_years=window_years,
            step_years=step_years,
        )

    return result


def evaluate_walk_forward(
    strategy: BaseStrategy,
    start: str = "2010-01-01",
    end: str | None = None,
    friction: float = 0.0005,
    window_years: int = 5,
    step_years: int = 1,
) -> dict:
    """Evaluate fixed params over rolling windows."""
    needed = list(set(strategy.required_symbols() + [strategy.target_symbol]))
    prices = _load_prices(needed, start=start, end=end)
    target = prices.get(strategy.target_symbol, pd.Series(dtype=float)).dropna()
    if target.empty:
        return {"window_count": 0, "windows": []}

    first = max(pd.Timestamp(start), target.index.min())
    last = pd.Timestamp(end) if end else target.index.max()
    starts = pd.date_range(first, last, freq=pd.DateOffset(years=step_years))

    windows = []
    for window_start in starts:
        window_end = window_start + pd.DateOffset(years=window_years)
        if window_end > last:
            break
        try:
            r = evaluate_augmented(
                strategy,
                start=str(window_start.date()),
                end=str(window_end.date()),
                friction=friction,
                walk_forward=False,
            )
        except Exception:
            continue
        windows.append({
            "start": r["eval_period"]["start"],
            "end": r["eval_period"]["end"],
            "sharpe": r["sharpe"],
            "objective": r["objective"],
            "cagr": r["cagr"],
            "max_drawdown": r["max_drawdown"],
            "trade_count": r["trade_count"],
            "beats_bh_sharpe": r["sharpe"] > r["bh_sharpe"],
            "beats_bh_drawdown": abs(r["max_drawdown"]) < abs(r["bh_max_drawdown"]),
        })

    sharpes = [w["sharpe"] for w in windows if _is_number(w["sharpe"])]
    objectives = [w["objective"] for w in windows if _is_number(w["objective"])]
    if not windows:
        return {"window_count": 0, "windows": []}

    return {
        "window_count": len(windows),
        "window_years": window_years,
        "step_years": step_years,
        "mean_sharpe": _round(sum(sharpes) / len(sharpes)) if sharpes else float("nan"),
        "mean_objective": _round(sum(objectives) / len(objectives)) if objectives else float("nan"),
        "positive_sharpe_rate": _round(sum(1 for s in sharpes if s > 0) / len(sharpes)) if sharpes else float("nan"),
        "beats_bh_sharpe_rate": _round(sum(1 for w in windows if w["beats_bh_sharpe"]) / len(windows)),
        "beats_bh_drawdown_rate": _round(sum(1 for w in windows if w["beats_bh_drawdown"]) / len(windows)),
        "windows": windows,
    }


def _objective_score(result: dict) -> float:
    """Composite objective: Sharpe plus drawdown/CAGR/turnover discipline."""
    sharpe = result.get("sharpe", 0.0)
    cagr = result.get("cagr", 0.0)
    bh_cagr = result.get("bh_cagr", 0.0)
    max_dd = result.get("max_drawdown", 0.0)
    bh_max_dd = result.get("bh_max_drawdown", 0.0)
    trade_count = result.get("trade_count", 0)

    p = result.get("eval_period", {})
    years = _years_between(p.get("start"), p.get("end"))
    trades_per_year = trade_count / max(years, 0.0001)

    drawdown_delta = abs(bh_max_dd) - abs(max_dd)
    cagr_delta = cagr - bh_cagr
    turnover_penalty = 0.02 * trades_per_year

    return sharpe + 0.75 * drawdown_delta + 0.50 * cagr_delta - turnover_penalty


def _buy_hold_max_drawdown(
    strategy: BaseStrategy,
    start: str | None,
    end: str | None,
) -> float:
    prices = _load_prices([strategy.target_symbol], start=start, end=end)
    close = prices[strategy.target_symbol]
    returns = close.pct_change().shift(-1).dropna()
    return _max_drawdown(returns)


def _exposure(strategy: BaseStrategy, start: str | None, end: str | None) -> float:
    needed = list(set(strategy.required_symbols() + [strategy.target_symbol]))
    prices = _load_prices(needed, start=start, end=end)
    target = prices[strategy.target_symbol]
    signals = strategy.generate_signals(prices).reindex(target.index, method="ffill").fillna(0)
    return float((signals != 0).mean())


def _years_between(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0.0
    return max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 0.0)


def _is_number(value) -> bool:
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _round(x: float, decimals: int = 4) -> float:
    try:
        return round(float(x), decimals)
    except (TypeError, ValueError):
        return float("nan")
