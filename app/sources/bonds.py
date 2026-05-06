"""Government bond yield data via Yahoo spark API."""

from app.config import REFRESH_BONDS, US_TREASURY_YIELDS, MOVE_INDEX
from app.sources.base import BaseSource, logger
from app.sources.yahoo_quotes import fetch_all_spark


class BondsSource(BaseSource):
    cache_key = "bonds"
    refresh_interval = REFRESH_BONDS

    async def fetch(self) -> dict:
        # Fetch all bond symbols + MOVE in one batch
        all_symbols = [i["symbol"] for i in US_TREASURY_YIELDS] + [MOVE_INDEX["symbol"]]
        spark_data = await fetch_all_spark(all_symbols, time_range="5d")

        us_yields = self._parse_yields(US_TREASURY_YIELDS, spark_data)
        yield_curve = self._build_yield_curve(us_yields)
        spread_2s10s = self._calc_2s10s(us_yields)
        spread_3m10y = self._calc_spread(us_yields, 0.25, 10, "3M/10Y")
        move = self._parse_move(spark_data)
        real_rate = self._calc_real_rate(us_yields)
        return {
            "us_yields": us_yields,
            "yield_curve": yield_curve,
            "spread_2s10s": spread_2s10s,
            "spread_3m10y": spread_3m10y,
            "move": move,
            "real_rate": real_rate,
        }

    def _parse_yields(self, items: list[dict], spark_data: dict) -> list[dict]:
        results = []
        for entry in items:
            sym = entry["symbol"]
            sd = spark_data.get(sym)
            if sd and sd["closes"] and len(sd["closes"]) >= 2:
                price = sd["closes"][-1]
                prev = sd["closes"][-2]
                chg = price - prev if prev else None
                results.append({
                    **entry,
                    "yield_pct": round(price, 3),
                    "change": round(chg, 3) if chg is not None else None,
                })
            else:
                results.append({**entry, "yield_pct": None, "change": None, "error": "No data"})
        return results

    def _parse_move(self, spark_data: dict) -> dict | None:
        """Parse MOVE index from spark data."""
        sd = spark_data.get(MOVE_INDEX["symbol"])
        if not sd or not sd["closes"] or len(sd["closes"]) < 2:
            return None
        price = sd["closes"][-1]
        prev = sd["closes"][-2]
        chg = price - prev
        pct = (chg / prev * 100) if prev else None
        return {
            **MOVE_INDEX,
            "value": round(price, 2),
            "change": round(chg, 2),
            "change_pct": round(pct, 2) if pct is not None else None,
        }

    def _build_yield_curve(self, us_yields: list[dict]) -> dict:
        maturities = []
        yields = []
        labels = []
        for item in us_yields:
            if item.get("yield_pct") is not None and "maturity" in item:
                maturities.append(item["maturity"])
                yields.append(item["yield_pct"])
                labels.append(item["name"])
        return {"maturities": maturities, "yields": yields, "labels": labels}

    def _calc_2s10s(self, us_yields: list[dict]) -> dict | None:
        """Calculate true 2s10s spread using 2Y yield futures."""
        ten_y = None
        two_y = None
        for item in us_yields:
            if item.get("yield_pct") is None:
                continue
            mat = item.get("maturity", 0)
            if mat == 10:
                ten_y = item["yield_pct"]
            if mat == 2:
                two_y = item["yield_pct"]

        if ten_y is not None and two_y is not None:
            return {
                "spread": round(ten_y - two_y, 3),
                "ten_y": ten_y,
                "two_y": two_y,
                "label": "2s10s",
            }
        return None

    def _calc_spread(self, us_yields: list[dict], short_mat: float, long_mat: float, label: str) -> dict | None:
        long_y = None
        short_y = None
        for item in us_yields:
            if item.get("yield_pct") is None:
                continue
            mat = item.get("maturity", 0)
            if mat == long_mat:
                long_y = item["yield_pct"]
            if mat == short_mat:
                short_y = item["yield_pct"]

        if long_y is not None and short_y is not None:
            return {
                "spread": round(long_y - short_y, 3),
                "long": long_y,
                "short": short_y,
                "label": label,
            }
        return None

    def _calc_real_rate(self, us_yields: list[dict]) -> dict | None:
        """Approximate real rate = 10Y nominal - breakeven inflation proxy.

        Uses 10Y-5Y spread as a rough breakeven proxy when TIPS data unavailable.
        """
        ten_y = None
        five_y = None
        for item in us_yields:
            if item.get("yield_pct") is None:
                continue
            mat = item.get("maturity", 0)
            if mat == 10:
                ten_y = item["yield_pct"]
            if mat == 5:
                five_y = item["yield_pct"]

        if ten_y is not None and five_y is not None:
            # Term premium proxy: 10Y - 5Y gives a rough measure of longer-term expectations
            return {
                "ten_y": ten_y,
                "five_y": five_y,
                "term_premium": round(ten_y - five_y, 3),
            }
        return None
