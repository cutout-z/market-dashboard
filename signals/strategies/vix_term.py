"""VIXTermStructure — pure VIX term structure signal.

Strategy logic
--------------
Goes flat (cash) when VIX spot is above VIX 3-Month futures (backwardation).
This isolates near-term stress premium: when spot VIX > VIX3M, the market
is pricing elevated near-term risk relative to 3-month expected volatility —
historically associated with corrections and elevated drawdown risk.

Optionally, require VIX spot to also be above `vix_floor` to filter out
false positives during low-vol regimes where the inversion is noise.

Signal is held flat for `hold_days` days after each trigger, then reverts
to long.

Target: S&P 500 (^GSPC) daily returns.

Autoresearch mutation surface
------------------------------
    vix_floor     float  default 15.0  — minimum VIX level to act on inversion
    hold_days     int    default 5     — flat hold extension after trigger
"""
import pandas as pd

from ..strategy import BaseStrategy


class VIXTermStructure(BaseStrategy):
    name = "VIXTermStructure"
    version = "v2"
    description = (
        "Long S&P 500; goes flat when VIX spot > VIX 3-Month (term inversion) "
        "and VIX is above vix_floor. Isolates the term structure condition from "
        "RiskOffComposite for clean comparison."
    )
    target_symbol = "^GSPC"
    target_label = "S&P 500 / SPY / ES beta"
    trade_long = "Maintain long S&P 500 exposure while vol term structure is healthy."
    trade_flat = "Reduce or hedge S&P 500 exposure while VIX term structure is stressed."
    cadence = "Daily close; tactical volatility regime"
    sizing_note = "Signal is a risk-on/risk-off overlay, not a volatility trade."

    # v2 defaults — best from autoresearch run 2026-04-29
    # Sharpe 0.64 vs v1 baseline 0.52 (B&H: 0.74)
    default_params = {
        "vix_floor": 20.0,
        "hold_days": 3,
    }

    def required_symbols(self) -> list[str]:
        return ["^VIX", "^VIX3M"]

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params

        ref = prices.get("^GSPC", prices["^VIX"])
        idx = ref.index

        def _align(s: pd.Series) -> pd.Series:
            return s.reindex(idx, method="ffill")

        vix = _align(prices["^VIX"])
        vix3m = _align(prices["^VIX3M"])

        # Term structure inversion AND VIX above noise floor
        inversion = (vix > vix3m) & (vix >= p["vix_floor"])
        risk_off_raw = inversion.astype(int)

        # Extend hold
        risk_off = risk_off_raw.rolling(p["hold_days"], min_periods=1).max()

        # 1 = long, 0 = flat
        signal = (1 - risk_off).astype(int)
        signal.name = "signal"
        return signal
