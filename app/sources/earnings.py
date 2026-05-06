"""Earnings calendar — upcoming earnings releases via FMP API."""

import httpx
from datetime import datetime, timedelta

from app.sources.base import BaseSource, logger
from app.sources.fmp import get_earnings_calendar, get_fmp_key


class EarningsSource(BaseSource):
    cache_key = "earnings"
    refresh_interval = 3600  # hourly (earnings dates don't change frequently)

    async def fetch(self) -> dict:
        if not get_fmp_key():
            return {"events": [], "error": "No FMP API key"}

        today = datetime.now()
        from_date = today.strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=13)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=15) as client:
            raw = await get_earnings_calendar(client, from_date, to_date)

        events = []
        for e in raw:
            symbol = e.get("symbol", "")
            if not symbol:
                continue

            timing_raw = e.get("time", "")
            if timing_raw in ("bmo", "before market open"):
                timing = "BMO"
            elif timing_raw in ("amc", "after market close"):
                timing = "AMC"
            else:
                timing = timing_raw.upper() if timing_raw else ""

            eps_est = e.get("epsEstimated")
            eps_act = e.get("eps")
            revenue_est = e.get("revenueEstimated")
            revenue_act = e.get("revenue")

            events.append({
                "symbol": symbol,
                "company": (e.get("name") or symbol)[:40],
                "date": e.get("date", ""),
                "timing": timing,
                "eps_estimate": round(eps_est, 2) if eps_est is not None else None,
                "eps_actual": round(eps_act, 2) if eps_act is not None else None,
                "revenue_estimate": revenue_est,
                "revenue_actual": revenue_act,
                "reported": eps_act is not None,
            })

        # Sort by date, then filter to weekdays only
        events.sort(key=lambda e: e["date"])

        return {"events": events}

    def _has_real_data(self, data: dict) -> bool:
        return bool(data.get("events"))
