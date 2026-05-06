"""Evaluation harness — backtest a strategy against historical parquet data."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .strategy import BaseStrategy

logger = logging.getLogger("signals.evaluate")

PARQUET_PATH = (
    Path(__file__).resolve().parent.parent / "app" / "data" / "history" / "prices.parquet"
)
TRADING_DAYS = 252


def _load_prices(
    symbols: list[str], start: str | None = None, end: str | None = None
) -> dict[str, pd.Series]:
    """Load close price series for requested symbols from the parquet file."""
    df = pd.read_parquet(PARQUET_PATH)
    df["date"] = pd.to_datetime(df["date"])
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]

    result: dict[str, pd.Series] = {}
    for sym in symbols:
        sub = df[df["symbol"] == sym][["date", "close"]].copy()
        sub = sub.set_index("date").sort_index()["close"]
        sub = sub[~sub.index.duplicated(keep="last")]
        result[sym] = sub
    return result


def evaluate(
    strategy: BaseStrategy,
    start: str = "2010-01-01",
    end: str | None = None,
    friction: float = 0.0005,
) -> dict:
    """Backtest a strategy and return a metrics dict for the findings log.

    Parameters
    ----------
    strategy : instantiated BaseStrategy subclass
    start    : backtest start date (YYYY-MM-DD)
    end      : backtest end date (None = latest in parquet)
    friction : one-way transaction cost as a fraction of position value
               default 0.05% — applied on each signal change

    Returns
    -------
    dict with keys:
        sharpe, hit_rate, max_drawdown, cagr,
        trade_count, bh_sharpe, bh_cagr,
        eval_period, metadata
    """
    # ── Load prices ───────────────────────────────────────────────────────
    needed = list(set(strategy.required_symbols() + [strategy.target_symbol]))
    prices = _load_prices(needed, start=start, end=end)

    if strategy.target_symbol not in prices:
        raise ValueError(f"Target symbol {strategy.target_symbol!r} not in parquet")

    target_close = prices[strategy.target_symbol]

    # ── Generate signals ──────────────────────────────────────────────────
    raw_signals = strategy.generate_signals(prices)

    # Align signals to target trading days (forward-fill gaps — no lookahead)
    idx = target_close.index
    signals = raw_signals.reindex(idx, method="ffill").fillna(0).astype(int)

    # ── Compute returns ───────────────────────────────────────────────────
    # next-day return: signal at close-of-day t → position held during day t+1
    fwd_returns = target_close.pct_change().shift(-1)

    # Apply transaction friction on each change in signal value
    signal_changes = signals.diff().abs().fillna(0) > 0
    friction_drag = signal_changes.astype(float) * friction

    strat_returns = (signals * fwd_returns - friction_drag).dropna()
    bh_returns = fwd_returns.reindex(strat_returns.index)

    # ── Metrics ───────────────────────────────────────────────────────────
    active_mask = signals.reindex(strat_returns.index) != 0
    active_returns = strat_returns[active_mask]
    hit_rate = float((active_returns > 0).mean()) if len(active_returns) > 0 else float("nan")

    # Trade count = days where we enter a non-flat position
    trade_count = int(
        ((signals.diff() != 0) & (signals != 0)).reindex(strat_returns.index).sum()
    )

    return {
        "sharpe": _round(_sharpe(strat_returns)),
        "hit_rate": _round(hit_rate),
        "max_drawdown": _round(_max_drawdown(strat_returns)),
        "cagr": _round(_cagr(strat_returns)),
        "trade_count": trade_count,
        "bh_sharpe": _round(_sharpe(bh_returns)),
        "bh_cagr": _round(_cagr(bh_returns)),
        "eval_period": {
            "start": str(strat_returns.index.min().date()),
            "end": str(strat_returns.index.max().date()),
        },
        "metadata": strategy.metadata(),
    }


# ── Metric helpers ─────────────────────────────────────────────────────────

def _round(x: float, decimals: int = 4) -> float:
    try:
        return round(float(x), decimals)
    except (TypeError, ValueError):
        return float("nan")


def _sharpe(returns: pd.Series) -> float:
    std = returns.std()
    if std == 0 or pd.isna(std):
        return float("nan")
    return float(returns.mean() / std * np.sqrt(TRADING_DAYS))


def _max_drawdown(returns: pd.Series) -> float:
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(dd.min())


def _cagr(returns: pd.Series) -> float:
    n_years = len(returns) / TRADING_DAYS
    cum = (1 + returns).prod()
    if cum <= 0 or n_years <= 0:
        return float("-inf")
    return float(cum ** (1 / n_years) - 1)
