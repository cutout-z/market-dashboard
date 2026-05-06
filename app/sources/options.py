"""Options volatility skew data from yfinance.

Note: Options chain data requires yfinance — no fast alternative API exists.
This source is kept on yfinance intentionally.
"""

import asyncio
from datetime import datetime, timedelta

import yfinance as yf

from app.config import REFRESH_OPTIONS, SKEW_UNDERLYING
from app.sources.base import BaseSource, logger


class OptionsSkewSource(BaseSource):
    cache_key = "options_skew"
    refresh_interval = REFRESH_OPTIONS

    async def fetch(self) -> dict:
        return await asyncio.to_thread(self._fetch_skew)

    def _fetch_skew(self) -> dict:
        """Fetch options chain and compute put/call IV skew."""
        try:
            ticker = yf.Ticker(SKEW_UNDERLYING)
            spot = ticker.fast_info.last_price
            if not spot:
                return {"error": "No spot price", "strikes": [], "put_iv": [], "call_iv": []}

            # Pick expiry 14-45 days out
            expirations = ticker.options
            if not expirations:
                return {"error": "No expirations", "strikes": [], "put_iv": [], "call_iv": []}

            target_date = datetime.now() + timedelta(days=21)
            best_exp = None
            best_diff = float("inf")
            for exp_str in expirations:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
                diff = abs((exp_dt - target_date).days)
                days_out = (exp_dt - datetime.now()).days
                if 7 <= days_out <= 60 and diff < best_diff:
                    best_diff = diff
                    best_exp = exp_str

            if not best_exp:
                best_exp = expirations[0]

            chain = ticker.option_chain(best_exp)
            calls = chain.calls
            puts = chain.puts

            # Filter to strikes within ±10% of spot
            low = spot * 0.90
            high = spot * 1.10

            calls_f = calls[(calls["strike"] >= low) & (calls["strike"] <= high)].copy()
            puts_f = puts[(puts["strike"] >= low) & (puts["strike"] <= high)].copy()

            # Build strike-level IV data
            call_iv_map = dict(zip(calls_f["strike"], calls_f["impliedVolatility"]))
            put_iv_map = dict(zip(puts_f["strike"], puts_f["impliedVolatility"]))

            # Union of strikes, sorted
            all_strikes = sorted(set(call_iv_map.keys()) | set(put_iv_map.keys()))

            strikes = []
            put_ivs = []
            call_ivs = []
            for s in all_strikes:
                strikes.append(round(float(s), 1))
                put_ivs.append(round(float(put_iv_map.get(s, 0)) * 100, 2) if s in put_iv_map else None)
                call_ivs.append(round(float(call_iv_map.get(s, 0)) * 100, 2) if s in call_iv_map else None)

            # Compute 25-delta skew approximation (OTM put IV - OTM call IV at ±5% from ATM)
            put_otm_strike = spot * 0.95
            call_otm_strike = spot * 1.05
            put_25d_iv = self._interp_iv(put_iv_map, put_otm_strike)
            call_25d_iv = self._interp_iv(call_iv_map, call_otm_strike)
            skew_25d = round(put_25d_iv - call_25d_iv, 2) if put_25d_iv and call_25d_iv else None

            return {
                "underlying": SKEW_UNDERLYING,
                "spot": round(float(spot), 2),
                "expiry": best_exp,
                "strikes": strikes,
                "put_iv": put_ivs,
                "call_iv": call_ivs,
                "skew_25d": skew_25d,
            }
        except Exception as e:
            logger.warning("Options skew error: %s", e)
            return {"error": str(e), "strikes": [], "put_iv": [], "call_iv": []}

    def _interp_iv(self, iv_map: dict, target_strike: float) -> float | None:
        """Find IV closest to target strike."""
        if not iv_map:
            return None
        closest = min(iv_map.keys(), key=lambda s: abs(s - target_strike))
        if abs(closest - target_strike) / target_strike > 0.03:
            return None
        return round(float(iv_map[closest]) * 100, 2)
