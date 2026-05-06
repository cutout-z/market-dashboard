"""AUDUSDRateShock — AUD/USD rate shock and risk regime proxy.

Strategy logic
--------------
Frames AUD/USD around shocks that commonly surround rate decisions:
    - sharp US yield rises (hawkish Fed / USD rate shock proxy)
    - DXY breakouts (broad USD strength)
    - VIX stress (risk-off, usually AUD-negative)
    - copper/gold improvement (commodity/growth support, usually AUD-positive)

The current dataset does not include a clean RBA-vs-Fed surprise calendar, so
this is deliberately labelled as a proxy strategy rather than a literal central
bank event parser.
"""
import pandas as pd

from ..strategy import BaseStrategy


class AUDUSDRateShock(BaseStrategy):
    name = "AUDUSDRateShock"
    version = "v1"
    description = (
        "Long/flat/short AUD/USD using US yield shock, DXY, VIX, and "
        "commodity-growth proxies around rate-shock regimes."
    )
    target_symbol = "AUDUSD=X"
    target_label = "AUD/USD spot / FXA / 6A futures"
    trade_long = "Long AUD/USD: own AUD against USD while rate/risk backdrop is AUD-supportive."
    trade_flat = "No AUD/USD directional exposure; wait for clearer rate/risk impulse."
    trade_short = "Short AUD/USD: own USD against AUD during USD rate shock or risk-off impulse."
    cadence = "Daily close; event/rate-shock proxy"
    sizing_note = (
        "Uses market proxies for rate shocks, not actual RBA/Fed surprise data. "
        "Treat as an FX regime signal, not a standalone leverage recommendation."
    )

    default_params = {
        "rate_lookback": 5,
        "rate_shock_bps": 20.0,
        "rate_relief_bps": -12.0,
        "dxy_lookback": 5,
        "dxy_shock": 0.015,
        "dxy_relief": -0.008,
        "vix_floor": 20.0,
        "commodity_lookback": 20,
        "commodity_threshold": 0.02,
        "conditions_required": 2,
        "hold_days": 5,
    }

    def required_symbols(self) -> list[str]:
        return ["^FVX", "DX-Y.NYB", "^VIX", "HG=F", "GC=F"]

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params
        audusd = prices[self.target_symbol].dropna()
        idx = audusd.index

        def _align(symbol: str) -> pd.Series:
            return prices[symbol].reindex(idx, method="ffill")

        us5y = _align("^FVX")
        dxy = _align("DX-Y.NYB")
        vix = _align("^VIX")
        copper = _align("HG=F")
        gold = _align("GC=F")

        # Yahoo yield indices are quoted in percentage-point yield terms.
        # Diff * 100 converts percentage points to basis points.
        yield_change_bps = us5y.diff(int(p["rate_lookback"])) * 100.0
        dxy_change = dxy.pct_change(int(p["dxy_lookback"]))
        copper_gold_roc = (copper / gold).pct_change(int(p["commodity_lookback"]))

        usd_rate_shock = yield_change_bps >= float(p["rate_shock_bps"])
        usd_rate_relief = yield_change_bps <= float(p["rate_relief_bps"])
        usd_breakout = dxy_change >= float(p["dxy_shock"])
        usd_fade = dxy_change <= float(p["dxy_relief"])
        risk_off = vix >= float(p["vix_floor"])
        commodity_tailwind = copper_gold_roc >= float(p["commodity_threshold"])

        bearish_score = usd_rate_shock.astype(int) + usd_breakout.astype(int) + risk_off.astype(int)
        bullish_score = usd_rate_relief.astype(int) + usd_fade.astype(int) + commodity_tailwind.astype(int)

        threshold = int(p["conditions_required"])
        raw = pd.Series(0, index=idx, dtype=int)
        raw[bullish_score >= threshold] = 1
        raw[bearish_score >= threshold] = -1  # stress wins if both fire

        hold_days = int(p["hold_days"])
        if hold_days > 1:
            held = raw.astype(float).replace(0.0, float("nan")).ffill(limit=hold_days - 1).fillna(0)
        else:
            held = raw

        signal = held.astype(int)
        signal.name = "signal"
        return signal
