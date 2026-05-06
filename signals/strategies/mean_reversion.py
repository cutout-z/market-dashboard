"""MeanReversion — z-score based mean reversion filter.

Strategy logic
--------------
Measures how far price has deviated from its rolling mean in standard
deviation units (z-score). Goes flat when the z-score exceeds
`z_upper` (overbought — price extended above mean, reversion risk).
Returns to long when z-score drops back below the threshold.

This is a defensive filter: it doesn't try to time entries, it removes
exposure during statistically extended rallies that are likely to revert.

Optionally holds flat for `hold_days` after each trigger.
Target: S&P 500 (^GSPC) daily returns.

Autoresearch mutation surface
------------------------------
    lookback      int    default 50   — rolling window for mean/std (range: 20–200)
    z_upper       float  default 2.0  — z-score threshold to go flat (range: 1.0–3.0)
    hold_days     int    default 1    — flat hold extension after trigger (range: 1–10)
"""
import pandas as pd

from ..strategy import BaseStrategy


class MeanReversion(BaseStrategy):
    name = "MeanReversion"
    version = "v1"
    description = (
        "Long S&P 500 by default; goes flat when z-score exceeds upper "
        "threshold (overbought/extended). Defensive mean-reversion filter."
    )
    target_symbol = "^GSPC"
    target_label = "S&P 500 / SPY / ES beta"
    trade_long = "Maintain long S&P 500 exposure."
    trade_flat = "Pause or trim S&P 500 exposure while price is statistically extended."
    cadence = "Daily close; tactical overextension filter"
    sizing_note = "Defensive filter only; does not estimate ideal position size."

    default_params = {
        "lookback": 50,
        "z_upper": 2.0,
        "hold_days": 1,
    }

    def required_symbols(self) -> list[str]:
        return []  # only needs target_symbol

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params
        close = prices[self.target_symbol]

        rolling_mean = close.rolling(p["lookback"], min_periods=p["lookback"]).mean()
        rolling_std = close.rolling(p["lookback"], min_periods=p["lookback"]).std()

        # Avoid division by zero
        rolling_std = rolling_std.replace(0, float("nan"))

        z_score = (close - rolling_mean) / rolling_std

        # Flat when overbought (z > threshold)
        overbought = (z_score > p["z_upper"]).astype(int)

        # Extend flat by hold_days
        if p["hold_days"] > 1:
            overbought = overbought.rolling(p["hold_days"], min_periods=1).max()

        signal = (1 - overbought).fillna(0).astype(int)
        signal.name = "signal"
        return signal
