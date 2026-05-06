"""RiskOffComposite — multi-indicator macro risk-off signal.

Strategy logic
--------------
Goes flat (cash) when at least `conditions_required` of the following fire:
    1. VIX above `vix_threshold` (default: 20) — elevated fear
    2. Copper/Gold `copper_gold_lookback`-day pct change below `copper_gold_change`
       (default: -3% over 5 days) — growth concern
    3. DXY at or above its `dxy_breakout_days`-day high (default: 10-day) — USD safe-haven
    4. VIX spot above VIX 3-Month (term structure inverted) — near-term stress premium

Signal is held flat for `hold_days` days after each trigger, then reverts to long.
Target: S&P 500 (^GSPC) daily returns.

Autoresearch mutation surface
------------------------------
All of the following are tunable via --params on the CLI:
    vix_threshold         float  default 20.0
    copper_gold_lookback  int    default 5
    copper_gold_change    float  default -0.03
    dxy_breakout_days     int    default 10
    conditions_required   int    default 2  (range: 1–4)
    hold_days             int    default 5
"""
import pandas as pd

from ..strategy import BaseStrategy


class RiskOffComposite(BaseStrategy):
    name = "RiskOffComposite"
    version = "v4"
    description = (
        "Long S&P 500; goes flat when 2+ macro risk-off conditions fire "
        "(VIX spike, copper/gold selloff, DXY breakout, VIX term inversion)."
    )
    target_symbol = "^GSPC"
    target_label = "S&P 500 / SPY / ES beta"
    trade_long = "Maintain long S&P 500 exposure."
    trade_flat = "De-risk S&P 500 exposure; use cash, T-bills, or defensive substitute."
    cadence = "Daily close; tactical risk switch"
    sizing_note = "Use as an equity-beta permission switch, not a standalone sizing model."

    # v4 defaults — best from autoresearch sweep 2026-05-02
    # Sharpe 0.855 vs v3 0.764 vs B&H 0.745
    # Key finding: copper_gold_lookback 6 + dxy_breakout_days 21 — slightly
    # longer windows capture macro shifts more reliably
    default_params = {
        "vix_threshold": 17.0,
        "copper_gold_lookback": 6,
        "copper_gold_change": -0.05,
        "dxy_breakout_days": 21,
        "conditions_required": 2,
        "hold_days": 1,
    }

    def required_symbols(self) -> list[str]:
        return ["^VIX", "^VIX3M", "HG=F", "GC=F", "DX-Y.NYB"]

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params

        # Target index — use S&P if available, else VIX
        ref = prices.get("^GSPC", prices["^VIX"])
        idx = ref.index

        def _align(s: pd.Series) -> pd.Series:
            return s.reindex(idx, method="ffill")

        vix = _align(prices["^VIX"])
        copper = _align(prices["HG=F"])
        gold = _align(prices["GC=F"])
        dxy = _align(prices["DX-Y.NYB"])
        vix3m = _align(prices["^VIX3M"]) if "^VIX3M" in prices else None

        # ── Condition 1: VIX spike ────────────────────────────────────────
        c1 = (vix > p["vix_threshold"]).astype(int)

        # ── Condition 2: Copper/Gold momentum ────────────────────────────
        copper_gold = copper / gold
        cg_change = copper_gold.pct_change(p["copper_gold_lookback"])
        c2 = (cg_change < p["copper_gold_change"]).astype(int)

        # ── Condition 3: DXY N-day high breakout ─────────────────────────
        dxy_high = dxy.rolling(p["dxy_breakout_days"]).max()
        c3 = (dxy >= dxy_high).astype(int)

        # ── Condition 4: VIX term structure inversion ─────────────────────
        if vix3m is not None:
            c4 = (vix > vix3m).astype(int)
        else:
            c4 = pd.Series(0, index=idx)

        # ── Composite ─────────────────────────────────────────────────────
        score = c1 + c2 + c3 + c4
        risk_off_raw = (score >= p["conditions_required"]).astype(int)

        # Extend: if any of the last hold_days were risk-off, stay flat
        risk_off = risk_off_raw.rolling(p["hold_days"], min_periods=1).max()

        # 1 = long, 0 = flat
        signal = (1 - risk_off).astype(int)
        signal.name = "signal"
        return signal
