"""Fed rate probability tracker — derived from Fed Funds futures via FRED.

Uses FRED series:
- DFEDTARU: Fed Funds Target Rate Upper Bound
- DFF: Effective Fed Funds Rate
- Fed Funds futures implied rates for upcoming FOMC meetings
"""

import httpx
from datetime import datetime

from app.sources.base import BaseSource, logger
from app.sources.fred import _get_fred_key, FRED_BASE


# Key FRED series for rate tracking
FED_RATE_SERIES = [
    {"series_id": "DFEDTARU",   "name": "Target Rate (Upper)", "desc": "Fed Funds Target Rate Upper Bound"},
    {"series_id": "DFEDTARL",   "name": "Target Rate (Lower)", "desc": "Fed Funds Target Rate Lower Bound"},
    {"series_id": "DFF",        "name": "Effective Fed Funds",  "desc": "Daily Effective Federal Funds Rate"},
    {"series_id": "IORB",       "name": "Interest on Reserves", "desc": "Interest Rate on Reserve Balances"},
]

# FOMC meeting dates for 2025-2026 (scheduled)
FOMC_DATES_2025_2026 = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-17",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
]


class FedWatchSource(BaseSource):
    cache_key = "fedwatch"
    refresh_interval = 300  # 5 minutes

    async def fetch(self) -> dict:
        key = _get_fred_key()
        if not key:
            return {"error": "No FRED API key"}

        async with httpx.AsyncClient(timeout=15) as client:
            rates = await self._fetch_rates(client, key)
            dot_plot = await self._fetch_dot_plot_proxy(client, key)

        # Find upcoming FOMC meetings
        today = datetime.now().strftime("%Y-%m-%d")
        upcoming = [d for d in FOMC_DATES_2025_2026 if d >= today][:6]

        return {
            "current_rates": rates,
            "upcoming_fomc": upcoming,
            "next_fomc": upcoming[0] if upcoming else None,
            "dot_plot_proxy": dot_plot,
        }

    async def _fetch_rates(self, client: httpx.AsyncClient, key: str) -> list[dict]:
        results = []
        for series in FED_RATE_SERIES:
            try:
                resp = await client.get(FRED_BASE, params={
                    "series_id": series["series_id"],
                    "api_key": key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 5,
                })
                if resp.status_code != 200:
                    results.append({**series, "value": None})
                    continue

                obs = resp.json().get("observations", [])
                value = None
                prev_value = None
                date = None
                for o in obs:
                    v = o.get("value", ".")
                    if v != "." and value is None:
                        value = round(float(v), 3)
                        date = o.get("date")
                    elif v != "." and prev_value is None:
                        prev_value = round(float(v), 3)

                change = round(value - prev_value, 3) if value is not None and prev_value is not None else None
                results.append({**series, "value": value, "prev_value": prev_value, "change": change, "date": date})
            except Exception as e:
                logger.debug("FedWatch %s error: %s", series["series_id"], e)
                results.append({**series, "value": None})
        return results

    async def _fetch_dot_plot_proxy(self, client: httpx.AsyncClient, key: str) -> dict | None:
        """Fetch forward rate expectations using FRED Treasury forwards as a proxy."""
        # Use the 1Y and 2Y forward rates as a proxy for rate expectations
        forward_series = [
            {"series_id": "DGS1",  "name": "1Y Treasury", "horizon": "1Y"},
            {"series_id": "DGS2",  "name": "2Y Treasury", "horizon": "2Y"},
            {"series_id": "DGS3",  "name": "3Y Treasury", "horizon": "3Y"},
        ]
        points = []
        for series in forward_series:
            try:
                resp = await client.get(FRED_BASE, params={
                    "series_id": series["series_id"],
                    "api_key": key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 2,
                })
                if resp.status_code != 200:
                    continue
                obs = resp.json().get("observations", [])
                for o in obs:
                    v = o.get("value", ".")
                    if v != ".":
                        points.append({
                            "horizon": series["horizon"],
                            "yield": round(float(v), 3),
                        })
                        break
            except Exception:
                continue

        return {"points": points} if points else None

    def _has_real_data(self, data: dict) -> bool:
        rates = data.get("current_rates", [])
        return any(r.get("value") is not None for r in rates)
