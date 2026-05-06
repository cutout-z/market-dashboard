"""CFTC Commitment of Traders (COT) data — weekly positioning from Socrata API.

Updates weekly: Tuesday data, released Friday 3:30 PM ET.
Uses the Legacy Futures-Only report via CFTC's public Socrata API (no auth needed).
"""

import csv
import io

import httpx

from app.sources.base import BaseSource, logger

# CFTC Socrata API — Legacy Futures-Only report
# Full CSV is ~30MB, so we use SoQL to filter to specific contracts and recent data
COT_BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# Markets we track — CFTC contract market codes
COT_MARKETS = [
    {"code": "067651", "name": "WTI Crude Oil",  "category": "Energy",   "symbol": "CL=F"},
    {"code": "023651", "name": "Natural Gas",     "category": "Energy",   "symbol": "NG=F"},
    {"code": "088691", "name": "Gold",            "category": "Metals",   "symbol": "GC=F"},
    {"code": "084691", "name": "Silver",          "category": "Metals",   "symbol": "SI=F"},
    {"code": "085692", "name": "Copper",          "category": "Metals",   "symbol": "HG=F"},
    {"code": "099741", "name": "Euro FX",         "category": "Currency", "symbol": "6E=F"},
    {"code": "097741", "name": "Japanese Yen",    "category": "Currency", "symbol": "6J=F"},
    {"code": "096742", "name": "British Pound",   "category": "Currency", "symbol": "6B=F"},
    {"code": "232741", "name": "Australian Dollar","category": "Currency","symbol": "6A=F"},
    {"code": "090741", "name": "Canadian Dollar",  "category": "Currency","symbol": "6C=F"},
    {"code": "13874A", "name": "S&P 500 E-Mini",  "category": "Index",   "symbol": "ES=F"},
    {"code": "043602", "name": "10Y T-Note",      "category": "Rates",   "symbol": "ZN=F"},
]


class COTSource(BaseSource):
    cache_key = "cot"
    refresh_interval = 3600  # hourly (data only changes weekly)

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            positions = []
            for market in COT_MARKETS:
                data = await self._fetch_market(client, market)
                if data:
                    positions.append(data)

        return {"positions": positions}

    async def _fetch_market(self, client: httpx.AsyncClient, market: dict) -> dict | None:
        """Fetch latest COT data for a single market via Socrata JSON API."""
        try:
            # SoQL query: latest 2 weeks for this contract code
            params = {
                "$where": f"cftc_contract_market_code='{market['code']}'",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": "2",
            }
            resp = await client.get(COT_BASE, params=params)
            if resp.status_code != 200:
                logger.debug("COT %s HTTP %d", market["name"], resp.status_code)
                return None

            rows = resp.json()
            if not rows:
                return None

            latest = rows[0]
            prev = rows[1] if len(rows) > 1 else None

            # Extract positioning data
            noncomm_long = _safe_int(latest.get("noncomm_positions_long_all"))
            noncomm_short = _safe_int(latest.get("noncomm_positions_short_all"))
            comm_long = _safe_int(latest.get("comm_positions_long_all"))
            comm_short = _safe_int(latest.get("comm_positions_short_all"))
            open_interest = _safe_int(latest.get("open_interest_all"))

            noncomm_net = noncomm_long - noncomm_short if noncomm_long is not None and noncomm_short is not None else None
            comm_net = comm_long - comm_short if comm_long is not None and comm_short is not None else None

            # Week-over-week change in net positioning
            net_change = None
            if prev and noncomm_net is not None:
                prev_long = _safe_int(prev.get("noncomm_positions_long_all"))
                prev_short = _safe_int(prev.get("noncomm_positions_short_all"))
                if prev_long is not None and prev_short is not None:
                    prev_net = prev_long - prev_short
                    net_change = noncomm_net - prev_net

            # Net as % of open interest (positioning intensity)
            net_pct_oi = None
            if noncomm_net is not None and open_interest and open_interest > 0:
                net_pct_oi = round(noncomm_net / open_interest * 100, 1)

            return {
                **market,
                "report_date": latest.get("report_date_as_yyyy_mm_dd", "")[:10],
                "open_interest": open_interest,
                "noncomm_long": noncomm_long,
                "noncomm_short": noncomm_short,
                "noncomm_net": noncomm_net,
                "comm_long": comm_long,
                "comm_short": comm_short,
                "comm_net": comm_net,
                "net_change": net_change,
                "net_pct_oi": net_pct_oi,
            }

        except Exception as e:
            logger.debug("COT %s error: %s", market["name"], e)
            return None

    def _has_real_data(self, data: dict) -> bool:
        return bool(data.get("positions"))


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
