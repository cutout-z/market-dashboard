"""GoldCopperMomentum — cross-asset growth/risk signal.

Strategy logic
--------------
The copper/gold ratio is a well-known macro barometer:
    - Rising copper/gold → growth expectations improving → risk-on
    - Falling copper/gold → growth expectations deteriorating → risk-off

This strategy goes flat when the copper/gold ratio's N-day rate of change
falls below a negative threshold (growth deterioration). Long otherwise.

Different philosophy from RiskOffComposite: instead of combining multiple
conditions, isolates one fundamental macro relationship and optimizes around it.

Autoresearch mutation surface
------------------------------
    lookback          int    default 10   — rate-of-change window (range: 3–30)
    roc_threshold     float  default -0.03 — go flat below this change (range: -0.01 to -0.10)
    hold_days         int    default 3    — flat hold extension (range: 1–15)
    smooth_period     int    default 1    — SMA smoothing on ratio before ROC (range: 1–10)
"""
import pandas as pd

from ..strategy import BaseStrategy


class GoldCopperMomentum(BaseStrategy):
    name = "GoldCopperMomentum"
    version = "v1"
    description = (
        "Long S&P 500 when copper/gold ratio momentum is positive (growth); "
        "flat when ratio deteriorates below threshold (risk-off)."
    )
    target_symbol = "^GSPC"
    target_label = "S&P 500 / SPY / ES beta"
    trade_long = "Maintain long S&P 500 exposure while copper/gold confirms growth."
    trade_flat = "De-risk S&P 500 exposure while copper/gold momentum deteriorates."
    cadence = "Daily close; macro growth/risk overlay"
    sizing_note = "Cross-asset macro filter, not a direct copper or gold trade."

    default_params = {
        "lookback": 10,
        "roc_threshold": -0.03,
        "hold_days": 3,
        "smooth_period": 1,
    }

    def required_symbols(self) -> list[str]:
        return ["HG=F", "GC=F"]

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params

        ref = prices.get("^GSPC", prices["HG=F"])
        idx = ref.index

        def _align(s: pd.Series) -> pd.Series:
            return s.reindex(idx, method="ffill")

        copper = _align(prices["HG=F"])
        gold = _align(prices["GC=F"])

        ratio = copper / gold

        # Optional smoothing
        if p["smooth_period"] > 1:
            ratio = ratio.rolling(p["smooth_period"], min_periods=1).mean()

        # Rate of change
        roc = ratio.pct_change(p["lookback"])

        # Flat when growth deteriorating
        risk_off_raw = (roc < p["roc_threshold"]).astype(int)

        # Extend hold
        if p["hold_days"] > 1:
            risk_off = risk_off_raw.rolling(p["hold_days"], min_periods=1).max()
        else:
            risk_off = risk_off_raw

        signal = (1 - risk_off).fillna(0).astype(int)
        signal.name = "signal"
        return signal
