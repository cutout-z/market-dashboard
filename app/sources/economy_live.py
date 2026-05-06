"""Economy indicators — live data from FRED + IMF DataMapper API.

Replaces the static DEFAULT_ECONOMY_DATA with:
- FRED: CPI YoY + Unemployment, monthly, 8 countries
- IMF DataMapper (WEO): GDP $T, GDP Growth, Budget/GDP, Govt Debt/GDP,
  Current Acct/GDP, CPI fallback — all 10 countries, latest available year

Refresh: 6 hours (monthly/annual source data).
Falls back to DEFAULT_ECONOMY_DATA on any fetch error.
"""

import asyncio
import copy
import json
import os
from pathlib import Path

import httpx

from app.config import ECONOMY_COUNTRIES, ECONOMY_INDICATORS
from app.sources.base import BaseSource, logger
from app.sources.economy import DEFAULT_ECONOMY_DATA

# ─── FRED ────────────────────────────────────────────────────────────────────

_OPENBB_SETTINGS = Path.home() / ".openbb_platform" / "user_settings.json"
_FRED_API_KEY = None

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


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


# CPI YoY % — growth same period prior year, monthly (OECD via FRED)
FRED_CPI_SERIES = {
    "USA":       "CPALTT01USM659N",
    "EU":        "EA19CPALTT01GYM",
    "Germany":   "CPALTT01DEM659N",
    "Japan":     "CPALTT01JPM659N",
    "UK":        "CPALTT01GBM659N",
    "France":    "CPALTT01FRM659N",
    "Canada":    "CPALTT01CAM659N",
    "Australia": "CPALTT01AUM659N",
    # China and India: no reliable monthly YoY series on FRED; fall back to IMF annual
}

# Harmonised unemployment rate %, monthly (OECD via FRED)
FRED_UNEMPLOYMENT_SERIES = {
    "USA":       "UNRATE",
    "EU":        "LRHUTTTTEZM156S",
    "Germany":   "LRHUTTTTDEM156S",
    "Japan":     "LRHUTTTTJPM156S",
    "UK":        "LRHUTTTTGBM156S",
    "France":    "LRHUTTTTFRM156S",
    "Canada":    "LRHUTTTTCAM156S",
    "Australia": "LRHUTTTTAUM156S",
    # China and India: not in OECD harmonised series
}

# Central bank policy rates (for Interest Rate column)
FRED_RATE_SERIES = {
    "USA":       "FEDFUNDS",
    "China":     "INTDSRCNM193N",
    "EU":        "ECBDFR",
    "Germany":   "ECBDFR",
    "Japan":     "IR3TIB01JPM156N",
    "India":     "IRSTCI01INM156N",
    "UK":        "IUDSOIA",
    "France":    "ECBDFR",
    "Canada":    "IR3TIB01CAM156N",
    "Australia": "IRSTCI01AUM156N",
}

# ─── IMF DataMapper ───────────────────────────────────────────────────────────

IMF_DATAMAPPER_BASE = "https://www.imf.org/external/datamapper/api/v1"

# Dashboard country → IMF WEO country code
IMF_COUNTRY = {
    "USA":       "USA",
    "China":     "CHN",
    "EU":        "EU",
    "Germany":   "DEU",
    "Japan":     "JPN",
    "India":     "IND",
    "UK":        "GBR",
    "France":    "FRA",
    "Canada":    "CAN",
    "Australia": "AUS",
}

# IMF WEO indicators to fetch
IMF_INDICATORS = {
    "NGDPD":        "GDP ($T)",          # Nominal GDP, USD billions
    "NGDP_RPCH":    "GDP Growth",         # Real GDP growth, %
    "PCPIPCH":      "Inflation Rate",     # CPI inflation, % (annual fallback)
    "GGXCNL_NGDP":  "Budget/GDP",         # Net lending/borrowing % of GDP
    "GGXWDG_NGDP":  "Govt Debt/GDP",      # Gross debt % of GDP
    "BCA_NGDPD":    "Current Acct/GDP",   # Current account % of GDP
}

# Current year — for data freshness cap
_CURRENT_YEAR = 2026


def _latest_imf_value(values_by_year: dict, max_year: int) -> float | None:
    """Return the value for the latest year <= max_year with a non-None value."""
    eligible = {
        int(y): v for y, v in values_by_year.items()
        if str(y).isdigit() and int(y) <= max_year and v is not None
    }
    if not eligible:
        return None
    return eligible[max(eligible)]


def _fmt_pct(val: float, decimals: int = 1) -> str:
    return f"{val:.{decimals}f}%"


def _fmt_gdp_t(val_billions: float) -> str:
    return f"{val_billions / 1000:.1f}"


# ─── Fetch helpers ────────────────────────────────────────────────────────────

async def _fetch_fred_latest(client: httpx.AsyncClient, key: str, series_id: str) -> float | None:
    """Fetch the latest non-missing value from a FRED series.

    Returns None if the most recent observation is more than 18 months old —
    this guards against stale series (e.g. OECD-sourced EU aggregates that
    stopped being updated when OECD migrated platforms).
    """
    from datetime import date, timedelta
    _stale_cutoff = date.today() - timedelta(days=548)  # ~18 months

    try:
        resp = await client.get(FRED_BASE, params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 3,
        })
        if resp.status_code != 200:
            return None
        for obs in resp.json().get("observations", []):
            v = obs.get("value", ".")
            if v == ".":
                continue
            obs_date = date.fromisoformat(obs.get("date", "2000-01-01"))
            if obs_date < _stale_cutoff:
                logger.debug("FRED %s stale (latest: %s), skipping", series_id, obs_date)
                return None
            return float(v)
    except Exception as e:
        logger.debug("FRED %s error: %s", series_id, e)
    return None


async def _fetch_imf_indicator(client: httpx.AsyncClient, indicator: str, imf_codes: list[str]) -> dict[str, float | None]:
    """Fetch one IMF DataMapper indicator for all countries. Returns {imf_code: value}."""
    country_str = "/".join(imf_codes)
    try:
        resp = await client.get(
            f"{IMF_DATAMAPPER_BASE}/{indicator}/{country_str}",
            timeout=20,
        )
        if resp.status_code != 200:
            logger.debug("IMF DataMapper %s HTTP %d", indicator, resp.status_code)
            return {}
        raw = resp.json().get("values", {}).get(indicator, {})
        # Use latest year <= current year - 1 (previous year = most recent full year)
        max_year = _CURRENT_YEAR - 1
        return {
            code: _latest_imf_value(vals, max_year)
            for code, vals in raw.items()
        }
    except Exception as e:
        logger.debug("IMF DataMapper %s error: %s", indicator, e)
        return {}


# ─── Main build ──────────────────────────────────────────────────────────────

async def _build_economy_data() -> dict:
    """Fetch live data and merge with DEFAULT_ECONOMY_DATA fallback."""
    data = copy.deepcopy(DEFAULT_ECONOMY_DATA)

    fred_key = _get_fred_key()
    imf_codes = list(IMF_COUNTRY.values())

    # Build all coroutines to run concurrently
    fred_keys: list[tuple[str, str]] = []    # [(kind, country), ...]
    fred_coros = []
    imf_indicator_list: list[str] = []
    imf_coros = []

    async with httpx.AsyncClient(timeout=15) as client:
        if fred_key:
            for country, series_id in FRED_CPI_SERIES.items():
                fred_keys.append(("cpi", country))
                fred_coros.append(_fetch_fred_latest(client, fred_key, series_id))
            for country, series_id in FRED_UNEMPLOYMENT_SERIES.items():
                fred_keys.append(("unemp", country))
                fred_coros.append(_fetch_fred_latest(client, fred_key, series_id))
            for country, series_id in FRED_RATE_SERIES.items():
                fred_keys.append(("rate", country))
                fred_coros.append(_fetch_fred_latest(client, fred_key, series_id))

        for indicator in IMF_INDICATORS:
            imf_indicator_list.append(indicator)
            imf_coros.append(_fetch_imf_indicator(client, indicator, imf_codes))

        # Run all concurrently
        all_results = await asyncio.gather(*(fred_coros + imf_coros), return_exceptions=True)

    fred_results = all_results[: len(fred_coros)]
    imf_results = all_results[len(fred_coros):]

    # ── Merge FRED results ──
    for (kind, country), result in zip(fred_keys, fred_results):
        if isinstance(result, Exception) or result is None:
            continue
        if country not in data:
            continue
        if kind == "cpi":
            data[country]["Inflation Rate"] = _fmt_pct(result)
        elif kind == "unemp":
            data[country]["Unemployment"] = _fmt_pct(result)
        elif kind == "rate":
            data[country]["Interest Rate"] = _fmt_pct(result, decimals=2)

    # ── Merge IMF DataMapper results ──
    for imf_indicator, result in zip(imf_indicator_list, imf_results):
        if isinstance(result, Exception) or not result:
            continue
        country_vals: dict[str, float | None] = result

        for dashboard_country, imf_code in IMF_COUNTRY.items():
            val = country_vals.get(imf_code)
            if val is None or dashboard_country not in data:
                continue

            if imf_indicator == "NGDPD":
                data[dashboard_country]["GDP ($T)"] = _fmt_gdp_t(val)
            elif imf_indicator == "NGDP_RPCH":
                data[dashboard_country]["GDP Growth"] = _fmt_pct(val)
            elif imf_indicator == "PCPIPCH":
                # IMF annual CPI as fallback for countries not covered by FRED monthly
                if dashboard_country not in FRED_CPI_SERIES:
                    data[dashboard_country]["Inflation Rate"] = _fmt_pct(val)
            elif imf_indicator == "GGXCNL_NGDP":
                data[dashboard_country]["Budget/GDP"] = _fmt_pct(val)
            elif imf_indicator == "GGXWDG_NGDP":
                data[dashboard_country]["Govt Debt/GDP"] = _fmt_pct(val, decimals=0)
            elif imf_indicator == "BCA_NGDPD":
                data[dashboard_country]["Current Acct/GDP"] = _fmt_pct(val)

    return data


class EconomyLiveSource(BaseSource):
    """Economy table with live FRED monthly + IMF annual data."""
    cache_key = "economy"
    refresh_interval = 21600  # 6 hours

    async def fetch(self) -> dict:
        try:
            data = await _build_economy_data()
        except Exception as e:
            logger.warning("EconomyLiveSource fetch error, using defaults: %s", e)
            data = copy.deepcopy(DEFAULT_ECONOMY_DATA)

        rows = []
        for country in ECONOMY_COUNTRIES:
            if country in data:
                row = {"country": country}
                for indicator in ECONOMY_INDICATORS:
                    row[indicator] = data[country].get(indicator, "—")
                rows.append(row)

        return {
            "countries": ECONOMY_COUNTRIES,
            "indicators": ECONOMY_INDICATORS,
            "rows": rows,
        }
