"""Financial Modeling Prep (FMP) API client.

General-purpose async client for FMP endpoints. Not a BaseSource subclass —
this is a utility module imported by other sources that need FMP data.

Key loading order:
  1. FMP_API_KEY environment variable  (cloud/production)
  2. ~/.openbb_platform/user_settings.json  (local dev / OpenBB config)
  3. macOS Keychain  (security find-generic-password -s fmp_api_key -w)
"""

import json
import os
import subprocess
from pathlib import Path

import httpx

from app.sources.base import logger

FMP_BASE = "https://financialmodelingprep.com/api"

_OPENBB_SETTINGS = Path.home() / ".openbb_platform" / "user_settings.json"
_FMP_API_KEY: str | None = None


def get_fmp_key() -> str | None:
    global _FMP_API_KEY
    if _FMP_API_KEY:
        return _FMP_API_KEY

    # 1. Environment variable (Docker / Render)
    env_key = os.environ.get("FMP_API_KEY")
    if env_key:
        _FMP_API_KEY = env_key
        return _FMP_API_KEY

    # 2. OpenBB platform settings
    try:
        settings = json.loads(_OPENBB_SETTINGS.read_text())
        key = settings.get("credentials", {}).get("fmp_api_key")
        if key:
            _FMP_API_KEY = key
            return _FMP_API_KEY
    except (OSError, json.JSONDecodeError):
        pass

    # 3. macOS Keychain fallback
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "fmp_api_key", "-w"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            key = result.stdout.strip()
            if key:
                _FMP_API_KEY = key
                return _FMP_API_KEY
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

async def _get(client: httpx.AsyncClient, path: str, **params) -> dict | list | None:
    """Make an authenticated GET request to FMP. Returns parsed JSON or None on error."""
    key = get_fmp_key()
    if not key:
        logger.warning("FMP: no API key available")
        return None
    try:
        resp = await client.get(
            f"{FMP_BASE}{path}",
            params={"apikey": key, **params},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.debug("FMP %s → HTTP %d", path, resp.status_code)
    except Exception as e:
        logger.debug("FMP %s error: %s", path, e)
    return None


# ---------------------------------------------------------------------------
# Public endpoint functions (all accept a single httpx.AsyncClient)
# ---------------------------------------------------------------------------

async def get_quote(client: httpx.AsyncClient, symbol: str) -> dict | None:
    """Real-time quote: price, change%, market cap, PE, EPS, shares outstanding."""
    data = await _get(client, f"/v3/quote/{symbol}")
    if data and isinstance(data, list) and data:
        return data[0]
    return None


async def get_quotes(client: httpx.AsyncClient, symbols: list[str]) -> list[dict]:
    """Batch real-time quotes (comma-separated, up to ~50 symbols per call)."""
    joined = ",".join(symbols)
    data = await _get(client, f"/v3/quote/{joined}")
    return data if isinstance(data, list) else []


async def get_profile(client: httpx.AsyncClient, symbol: str) -> dict | None:
    """Company profile: sector, industry, description, exchange, employees, CEO."""
    data = await _get(client, f"/v3/profile/{symbol}")
    if data and isinstance(data, list) and data:
        return data[0]
    return None


async def get_key_metrics(
    client: httpx.AsyncClient, symbol: str, period: str = "annual", limit: int = 4
) -> list[dict]:
    """Key metrics per period: PE, EV/EBITDA, P/FCF, ROIC, debt/equity, etc."""
    data = await _get(client, f"/v3/key-metrics/{symbol}", period=period, limit=limit)
    return data if isinstance(data, list) else []


async def get_ratios(
    client: httpx.AsyncClient, symbol: str, period: str = "annual", limit: int = 4
) -> list[dict]:
    """Financial ratios: gross/net margin, ROE, ROA, current ratio, etc."""
    data = await _get(client, f"/v3/ratios/{symbol}", period=period, limit=limit)
    return data if isinstance(data, list) else []


async def get_income(
    client: httpx.AsyncClient, symbol: str, period: str = "annual", limit: int = 4
) -> list[dict]:
    """Income statement: revenue, gross profit, EBITDA, net income, EPS."""
    data = await _get(client, f"/v3/income-statement/{symbol}", period=period, limit=limit)
    return data if isinstance(data, list) else []


async def get_cashflow(
    client: httpx.AsyncClient, symbol: str, period: str = "annual", limit: int = 4
) -> list[dict]:
    """Cash flow statement: operating CF, capex, free cash flow."""
    data = await _get(client, f"/v3/cash-flow-statement/{symbol}", period=period, limit=limit)
    return data if isinstance(data, list) else []


async def get_financial_growth(
    client: httpx.AsyncClient, symbol: str, period: str = "annual", limit: int = 4
) -> list[dict]:
    """YoY growth rates: revenue, earnings, FCF, dividends."""
    data = await _get(client, f"/v3/financial-growth/{symbol}", period=period, limit=limit)
    return data if isinstance(data, list) else []


async def get_earnings_calendar(
    client: httpx.AsyncClient, from_date: str, to_date: str
) -> list[dict]:
    """Earnings calendar for a date range (YYYY-MM-DD format)."""
    data = await _get(
        client, "/v3/earning_calendar", **{"from": from_date, "to": to_date}
    )
    return data if isinstance(data, list) else []


async def get_economic_calendar(
    client: httpx.AsyncClient, from_date: str, to_date: str
) -> list[dict]:
    """Economic calendar (GDP, CPI, NFP, etc.) for a date range."""
    data = await _get(
        client, "/v3/economic_calendar", **{"from": from_date, "to": to_date}
    )
    return data if isinstance(data, list) else []
