"""MomentumCrossover — dual simple moving average crossover.

Strategy logic
--------------
Classic trend-following signal. Long S&P 500 when the fast SMA is above
the slow SMA (uptrend confirmed). Flat (cash) when fast SMA crosses below
slow SMA (trend breakdown).

Signal is held flat for `hold_days` after each bearish crossover.
Target: S&P 500 (^GSPC) daily returns.

Autoresearch mutation surface
------------------------------
    fast_period   int    default 20   — fast SMA window (range: 5–50)
    slow_period   int    default 100  — slow SMA window (range: 50–250)
    hold_days     int    default 1    — flat hold extension after bearish cross
"""
import pandas as pd

from ..strategy import BaseStrategy


class MomentumCrossover(BaseStrategy):
    name = "MomentumCrossover"
    version = "v1"
    description = (
        "Long S&P 500 when fast SMA > slow SMA (uptrend); "
        "flat when fast crosses below slow (trend breakdown)."
    )
    target_symbol = "^GSPC"
    target_label = "S&P 500 / SPY / ES beta"
    trade_long = "Maintain long S&P 500 exposure while trend is up."
    trade_flat = "Move out of S&P 500 exposure while trend is broken."
    cadence = "Daily close; medium-term trend"
    sizing_note = "Trend permission switch; exposure percentage is historical time-in-market."

    default_params = {
        "fast_period": 20,
        "slow_period": 100,
        "hold_days": 1,
    }

    def required_symbols(self) -> list[str]:
        return []  # only needs target_symbol (^GSPC)

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params
        close = prices[self.target_symbol]

        fast_sma = close.rolling(p["fast_period"], min_periods=p["fast_period"]).mean()
        slow_sma = close.rolling(p["slow_period"], min_periods=p["slow_period"]).mean()

        # Long when fast > slow, flat otherwise
        trend_up = (fast_sma > slow_sma).astype(int)

        # Extend flat periods by hold_days after each bearish crossover
        bearish_cross = (trend_up.diff() < 0).astype(int)
        if p["hold_days"] > 1:
            extended_flat = bearish_cross.rolling(p["hold_days"], min_periods=1).max()
            signal = trend_up.copy()
            signal[extended_flat > 0] = 0
        else:
            signal = trend_up

        signal = signal.fillna(0).astype(int)
        signal.name = "signal"
        return signal
