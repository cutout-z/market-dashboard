"""Historical economic indicators from FRED for time-series charts."""

import json
import os
from pathlib import Path

import httpx

from app.config import ECONOMY_HISTORICAL, REFRESH_ECONOMY_HISTORICAL
from app.sources.base import BaseSource, logger

# Read FRED API key — env var first (cloud), OpenBB settings as local fallback
_OPENBB_SETTINGS = Path.home() / ".openbb_platform" / "user_settings.json"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _get_fred_key() -> str | None:
    env_key = os.environ.get("FRED_API_KEY")
    if env_key:
        return env_key
    try:
        settings = json.loads(_OPENBB_SETTINGS.read_text())
        return settings.get("credentials", {}).get("fred_api_key")
    except (OSError, json.JSONDecodeError, KeyError):
        return None


class EconomyHistoricalSource(BaseSource):
    cache_key = "economy_historical"
    refresh_interval = REFRESH_ECONOMY_HISTORICAL

    async def fetch(self) -> dict:
        key = _get_fred_key()
        if not key:
            return {"charts": [], "error": "No FRED API key"}

        charts = []
        async with httpx.AsyncClient(timeout=20) as client:
            for indicator_name, country_series in ECONOMY_HISTORICAL.items():
                chart_data = {"indicator": indicator_name, "series": []}

                for country, series_id in country_series.items():
                    try:
                        resp = await client.get(FRED_BASE, params={
                            "series_id": series_id,
                            "api_key": key,
                            "file_type": "json",
                            "sort_order": "asc",
                            "observation_start": "2015-01-01",
                        })
                        if resp.status_code != 200:
                            continue

                        data = resp.json()
                        obs = data.get("observations", [])

                        dates = []
                        values = []
                        for o in obs:
                            v = o.get("value", ".")
                            if v != ".":
                                dates.append(o["date"])
                                values.append(round(float(v), 2))

                        if dates:
                            chart_data["series"].append({
                                "country": country,
                                "dates": dates,
                                "values": values,
                            })
                    except Exception as e:
                        logger.debug("FRED historical %s/%s error: %s", indicator_name, country, e)

                charts.append(chart_data)

        return {"charts": charts}
