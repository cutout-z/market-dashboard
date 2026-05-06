"""FRED (Federal Reserve Economic Data) API integration.

Provides:
- Full US yield curve (1M through 30Y)
- Breakeven inflation rates
- Key economic indicators (CPI, unemployment, GDP, Fed Funds)
- Real rates calculation
"""

import json
import os
from pathlib import Path

import httpx

from app.sources.base import BaseSource, logger

# Read FRED API key — env var first (cloud), OpenBB settings as local fallback
_OPENBB_SETTINGS = Path.home() / ".openbb_platform" / "user_settings.json"
_FRED_API_KEY = None

def _get_fred_key() -> str | None:
    global _FRED_API_KEY
    if _FRED_API_KEY:
        return _FRED_API_KEY
    env_key = os.environ.get("FRED_API_KEY")
    if env_key:
        _FRED_API_KEY = env_key
        return _FRED_API_KEY
    try:
        settings = json.loads(_OPENBB_SETTINGS.read_text())
        _FRED_API_KEY = settings.get("credentials", {}).get("fred_api_key")
        return _FRED_API_KEY
    except (OSError, json.JSONDecodeError, KeyError):
        return None


FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# Full yield curve series
YIELD_SERIES = [
    {"series_id": "DGS1MO", "name": "1-Month",  "maturity": 1/12},
    {"series_id": "DGS3MO", "name": "3-Month",  "maturity": 0.25},
    {"series_id": "DGS6MO", "name": "6-Month",  "maturity": 0.5},
    {"series_id": "DGS1",   "name": "1-Year",   "maturity": 1},
    {"series_id": "DGS2",   "name": "2-Year",   "maturity": 2},
    {"series_id": "DGS3",   "name": "3-Year",   "maturity": 3},
    {"series_id": "DGS5",   "name": "5-Year",   "maturity": 5},
    {"series_id": "DGS7",   "name": "7-Year",   "maturity": 7},
    {"series_id": "DGS10",  "name": "10-Year",  "maturity": 10},
    {"series_id": "DGS20",  "name": "20-Year",  "maturity": 20},
    {"series_id": "DGS30",  "name": "30-Year",  "maturity": 30},
]

# Credit spreads (ICE BofA via FRED)
CREDIT_SPREAD_SERIES = [
    {"series_id": "BAMLC0A0CM",   "name": "US IG OAS",  "desc": "Investment Grade Option-Adjusted Spread"},
    {"series_id": "BAMLH0A0HYM2", "name": "US HY OAS",  "desc": "High Yield Option-Adjusted Spread"},
    {"series_id": "BAMLC0A4CBBB", "name": "BBB OAS",    "desc": "BBB Corporate Option-Adjusted Spread"},
    {"series_id": "BAMLH0A1HYBB", "name": "BB OAS",     "desc": "BB High Yield Option-Adjusted Spread"},
]

# Breakeven inflation
BREAKEVEN_SERIES = [
    {"series_id": "T5YIE",  "name": "5Y Breakeven", "maturity": 5},
    {"series_id": "T10YIE", "name": "10Y Breakeven", "maturity": 10},
]

# Key economic indicators
ECONOMIC_SERIES = [
    {"series_id": "FEDFUNDS",   "name": "Fed Funds Rate",    "unit": "%",     "category": "rates"},
    {"series_id": "CPIAUCSL",   "name": "CPI (All Urban)",   "unit": "index", "category": "inflation"},
    {"series_id": "CPILFESL",   "name": "Core CPI",          "unit": "index", "category": "inflation"},
    {"series_id": "UNRATE",     "name": "Unemployment Rate",  "unit": "%",     "category": "labor"},
    {"series_id": "PAYEMS",     "name": "Nonfarm Payrolls",   "unit": "K",     "category": "labor"},
    {"series_id": "GDP",        "name": "GDP",                "unit": "$B",    "category": "growth"},
    {"series_id": "GDPC1",      "name": "Real GDP",           "unit": "$B",    "category": "growth"},
    {"series_id": "UMCSENT",    "name": "Consumer Sentiment",  "unit": "index", "category": "sentiment"},
    {"series_id": "VIXCLS",     "name": "VIX (FRED)",         "unit": "index", "category": "volatility"},
    {"series_id": "DTWEXBGS",   "name": "Trade-Weighted USD",  "unit": "index", "category": "currency"},
]


class FredYieldSource(BaseSource):
    """Full US yield curve + breakevens from FRED."""
    cache_key = "fred_yields"
    refresh_interval = 300  # 5 minutes

    async def fetch(self) -> dict:
        key = _get_fred_key()
        if not key:
            return {"yields": [], "breakevens": [], "error": "No FRED API key"}

        async with httpx.AsyncClient(timeout=15) as client:
            yields = await self._fetch_series(client, key, YIELD_SERIES)
            breakevens = await self._fetch_series(client, key, BREAKEVEN_SERIES)
            credit_spreads = await self._fetch_series(client, key, CREDIT_SPREAD_SERIES)

        # Build US yield curve data
        curve = {"maturities": [], "yields": [], "labels": []}
        for item in yields:
            if item.get("value") is not None:
                curve["maturities"].append(item["maturity"])
                curve["yields"].append(item["value"])
                curve["labels"].append(item["name"])

        # Calculate US spreads
        yield_map = {item["maturity"]: item.get("value") for item in yields if item.get("value") is not None}
        spread_2s10s = self._calc_spread(yield_map, 2, 10, "2s10s")
        spread_3m10y = self._calc_spread(yield_map, 0.25, 10, "3M/10Y")
        spread_2s30s = self._calc_spread(yield_map, 2, 30, "2s30s")

        # Real rate = 10Y nominal - 10Y breakeven
        ten_y = yield_map.get(10)
        be_10y = next((b["value"] for b in breakevens if b.get("maturity") == 10 and b.get("value") is not None), None)
        real_rate = None
        if ten_y is not None and be_10y is not None:
            real_rate = {
                "value": round(ten_y - be_10y, 3),
                "nominal": ten_y,
                "breakeven": be_10y,
            }

        return {
            "yields": yields,
            "breakevens": breakevens,
            "credit_spreads": credit_spreads,
            "yield_curve": curve,
            "spread_2s10s": spread_2s10s,
            "spread_3m10y": spread_3m10y,
            "spread_2s30s": spread_2s30s,
            "real_rate": real_rate,
        }

    async def _fetch_series(self, client: httpx.AsyncClient, key: str, series_list: list[dict]) -> list[dict]:
        results = []
        for series in series_list:
            try:
                resp = await client.get(FRED_BASE, params={
                    "series_id": series["series_id"],
                    "api_key": key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 2,
                })
                if resp.status_code != 200:
                    results.append({**series, "value": None, "prev_value": None, "date": None})
                    continue

                data = resp.json()
                obs = data.get("observations", [])

                # Get latest non-"." value
                value = None
                prev_value = None
                date = None
                for i, o in enumerate(obs):
                    v = o.get("value", ".")
                    if v != "." and value is None:
                        value = round(float(v), 3)
                        date = o.get("date")
                    elif v != "." and prev_value is None:
                        prev_value = round(float(v), 3)

                change = round(value - prev_value, 3) if value is not None and prev_value is not None else None
                results.append({
                    **series,
                    "value": value,
                    "prev_value": prev_value,
                    "change": change,
                    "date": date,
                })
            except Exception as e:
                logger.debug("FRED %s error: %s", series["series_id"], e)
                results.append({**series, "value": None, "prev_value": None, "date": None})

        return results

    def _calc_spread(self, yield_map: dict, short_mat: float, long_mat: float, label: str) -> dict | None:
        short = yield_map.get(short_mat)
        long = yield_map.get(long_mat)
        if short is not None and long is not None:
            return {
                "spread": round(long - short, 3),
                "long": long,
                "short": short,
                "label": label,
            }
        return None


async def _fetch_fred_series_list(client: httpx.AsyncClient, key: str, series_list: list[dict]) -> list[dict]:
    """Shared helper to fetch a list of FRED series."""
    results = []
    for series in series_list:
        try:
            resp = await client.get(FRED_BASE, params={
                "series_id": series["series_id"],
                "api_key": key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 2,
            })
            if resp.status_code != 200:
                results.append({**series, "value": None, "prev_value": None, "date": None, "change": None})
                continue

            data = resp.json()
            obs = data.get("observations", [])

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
            results.append({
                **series,
                "value": value,
                "prev_value": prev_value,
                "change": change,
                "date": date,
            })
        except Exception as e:
            logger.debug("FRED %s error: %s", series["series_id"], e)
            results.append({**series, "value": None, "prev_value": None, "date": None, "change": None})

    return results


class FredEconomySource(BaseSource):
    """Key US economic indicators from FRED."""
    cache_key = "fred_economy"
    refresh_interval = 3600  # hourly (most series update monthly)

    async def fetch(self) -> dict:
        key = _get_fred_key()
        if not key:
            return {"indicators": [], "nowcasts": [], "cb_rates": [], "error": "No FRED API key"}

        from app.config import INFLATION_NOWCAST_SERIES, CENTRAL_BANK_RATES

        async with httpx.AsyncClient(timeout=15) as client:
            nowcasts = await _fetch_fred_series_list(client, key, INFLATION_NOWCAST_SERIES)
            cb_rates = await _fetch_fred_series_list(client, key, CENTRAL_BANK_RATES)
            indicators = []
            for series in ECONOMIC_SERIES:
                try:
                    resp = await client.get(FRED_BASE, params={
                        "series_id": series["series_id"],
                        "api_key": key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 2,
                    })
                    if resp.status_code != 200:
                        indicators.append({**series, "value": None, "date": None})
                        continue

                    data = resp.json()
                    obs = data.get("observations", [])
                    value = None
                    prev_value = None
                    date = None

                    for o in obs:
                        v = o.get("value", ".")
                        if v != "." and value is None:
                            value = float(v)
                            date = o.get("date")
                        elif v != "." and prev_value is None:
                            prev_value = float(v)

                    # For index-type series, calculate YoY change
                    change = None
                    if value is not None and prev_value is not None:
                        change = round(value - prev_value, 2)

                    indicators.append({
                        **series,
                        "value": round(value, 2) if value is not None else None,
                        "prev_value": round(prev_value, 2) if prev_value is not None else None,
                        "change": change,
                        "date": date,
                    })
                except Exception as e:
                    logger.debug("FRED economy %s error: %s", series["series_id"], e)
                    indicators.append({**series, "value": None, "date": None})

        return {"indicators": indicators, "nowcasts": nowcasts, "cb_rates": cb_rates}
