"""International government bond yields from central bank sources.

- Australia: RBA Table F2 (daily CSV)
- Japan: Ministry of Finance JGB yields (daily CSV)
- Euro Area: ECB Yield Curve API (daily, Svensson model spot rates)
"""

import csv
import io
from datetime import datetime

import httpx

from app.sources.base import BaseSource, logger

# ─── URLs ───
# UK Gilts from Bank of England (IUMAAJNB = 2Y, IUMALNPY = 5Y, IUMAMNPY = 10Y, IUMASNPY = 20Y, IUMAVNPY = 30Y)
BOE_GILT_SERIES = [
    {"series": "IUMAAJNB", "name": "2-Year",  "maturity": 2},
    {"series": "IUMALNPY", "name": "5-Year",  "maturity": 5},
    {"series": "IUMAMNPY", "name": "10-Year", "maturity": 10},
    {"series": "IUMASNPY", "name": "20-Year", "maturity": 20},
    {"series": "IUMAVNPY", "name": "30-Year", "maturity": 30},
]
BOE_URL_TEMPLATE = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2024&Dateto=now&SeriesCodes={codes}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N"

RBA_F2_URL = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
MOF_JGB_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
ECB_YC_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/"
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M+SR_1Y+SR_2Y+SR_3Y+SR_5Y+SR_7Y+SR_10Y+SR_20Y+SR_30Y"
    "?lastNObservations=2&format=csvdata"
)

# ─── Maturity configs ───
AU_MATURITIES = [
    {"col_idx": 1, "name": "2-Year",  "maturity": 2},
    {"col_idx": 2, "name": "3-Year",  "maturity": 3},
    {"col_idx": 3, "name": "5-Year",  "maturity": 5},
    {"col_idx": 4, "name": "10-Year", "maturity": 10},
]

JP_MATURITIES = {
    "1Y": {"name": "1-Year", "maturity": 1},
    "2Y": {"name": "2-Year", "maturity": 2},
    "3Y": {"name": "3-Year", "maturity": 3},
    "5Y": {"name": "5-Year", "maturity": 5},
    "7Y": {"name": "7-Year", "maturity": 7},
    "10Y": {"name": "10-Year", "maturity": 10},
    "20Y": {"name": "20-Year", "maturity": 20},
    "30Y": {"name": "30-Year", "maturity": 30},
    "40Y": {"name": "40-Year", "maturity": 40},
}

ECB_TENOR_MAP = {
    "SR_3M":  {"name": "3-Month", "maturity": 0.25},
    "SR_1Y":  {"name": "1-Year",  "maturity": 1},
    "SR_2Y":  {"name": "2-Year",  "maturity": 2},
    "SR_3Y":  {"name": "3-Year",  "maturity": 3},
    "SR_5Y":  {"name": "5-Year",  "maturity": 5},
    "SR_7Y":  {"name": "7-Year",  "maturity": 7},
    "SR_10Y": {"name": "10-Year", "maturity": 10},
    "SR_20Y": {"name": "20-Year", "maturity": 20},
    "SR_30Y": {"name": "30-Year", "maturity": 30},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/csv, application/json, */*",
}


class IntlBondsSource(BaseSource):
    cache_key = "intl_bonds"
    refresh_interval = 300  # 5 minutes

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            au = await self._fetch_au(client)
            jp = await self._fetch_jp(client)
            euro = await self._fetch_euro(client)

            uk = await self._fetch_uk(client)

        return {
            "au_yields": au["yields"],
            "au_curve": au["curve"],
            "au_spreads": _calc_spreads(au["yields"]),
            "jp_yields": jp["yields"],
            "jp_curve": jp["curve"],
            "jp_spreads": _calc_spreads(jp["yields"]),
            "euro_yields": euro["yields"],
            "euro_curve": euro["curve"],
            "euro_spreads": _calc_spreads(euro["yields"]),
            "uk_yields": uk["yields"],
            "uk_curve": uk["curve"],
            "uk_spreads": _calc_spreads(uk["yields"]),
        }

    async def _fetch_au(self, client: httpx.AsyncClient) -> dict:
        """Fetch Australian Government Bond yields from RBA Table F2."""
        try:
            resp = await client.get(RBA_F2_URL)
            if resp.status_code != 200:
                logger.warning("RBA F2 HTTP %d", resp.status_code)
                return {"yields": [], "curve": _empty_curve()}

            lines = resp.text.strip().split("\n")
            # Skip 11 header/metadata rows
            data_lines = lines[11:]
            if not data_lines:
                return {"yields": [], "curve": _empty_curve()}

            reader = csv.reader(data_lines)
            rows = list(reader)

            # Get last two non-empty rows for current + previous (for change calc)
            valid_rows = [r for r in rows if len(r) > 4 and r[1].strip()]
            if not valid_rows:
                return {"yields": [], "curve": _empty_curve()}

            latest = valid_rows[-1]
            prev = valid_rows[-2] if len(valid_rows) > 1 else None

            yields = []
            for m in AU_MATURITIES:
                try:
                    val = float(latest[m["col_idx"]].strip())
                    chg = None
                    if prev:
                        try:
                            prev_val = float(prev[m["col_idx"]].strip())
                            chg = round(val - prev_val, 3)
                        except (ValueError, IndexError):
                            pass
                    yields.append({
                        "name": m["name"],
                        "maturity": m["maturity"],
                        "value": round(val, 3),
                        "change": chg,
                    })
                except (ValueError, IndexError):
                    yields.append({"name": m["name"], "maturity": m["maturity"], "value": None, "change": None})

            return {"yields": yields, "curve": _build_curve(yields)}

        except Exception as e:
            logger.warning("RBA fetch error: %s", e)
            return {"yields": [], "curve": _empty_curve()}

    async def _fetch_jp(self, client: httpx.AsyncClient) -> dict:
        """Fetch JGB yields from Japan Ministry of Finance."""
        try:
            resp = await client.get(MOF_JGB_URL)
            if resp.status_code != 200:
                logger.warning("MoF JGB HTTP %d", resp.status_code)
                return {"yields": [], "curve": _empty_curve()}

            lines = resp.text.strip().split("\n")
            # Row 0 is title, Row 1 is header, rest is data
            if len(lines) < 3:
                return {"yields": [], "curve": _empty_curve()}

            reader = csv.reader(lines[1:])
            header = next(reader)
            rows = [r for r in reader if r and r[0].strip() and r[0][0].isdigit()]

            if not rows:
                return {"yields": [], "curve": _empty_curve()}

            latest = rows[-1]
            prev = rows[-2] if len(rows) > 1 else None

            # Map header columns to our tenor keys
            col_map = {}
            for i, h in enumerate(header):
                h = h.strip()
                if h in JP_MATURITIES:
                    col_map[h] = i

            yields = []
            for tenor_key, meta in JP_MATURITIES.items():
                if tenor_key not in col_map:
                    continue
                idx = col_map[tenor_key]
                try:
                    val_str = latest[idx].strip()
                    if not val_str or val_str == '-':
                        yields.append({"name": meta["name"], "maturity": meta["maturity"], "value": None, "change": None})
                        continue
                    val = float(val_str)
                    chg = None
                    if prev:
                        try:
                            prev_str = prev[idx].strip()
                            if prev_str and prev_str != '-':
                                chg = round(val - float(prev_str), 3)
                        except (ValueError, IndexError):
                            pass
                    yields.append({
                        "name": meta["name"],
                        "maturity": meta["maturity"],
                        "value": round(val, 3),
                        "change": chg,
                    })
                except (ValueError, IndexError):
                    yields.append({"name": meta["name"], "maturity": meta["maturity"], "value": None, "change": None})

            return {"yields": yields, "curve": _build_curve(yields)}

        except Exception as e:
            logger.warning("MoF JGB fetch error: %s", e)
            return {"yields": [], "curve": _empty_curve()}

    async def _fetch_uk(self, client: httpx.AsyncClient) -> dict:
        """Fetch UK Gilt yields from Bank of England."""
        try:
            codes = ",".join(s["series"] for s in BOE_GILT_SERIES)
            url = BOE_URL_TEMPLATE.format(codes=codes)
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning("BoE Gilts HTTP %d", resp.status_code)
                return {"yields": [], "curve": _empty_curve()}

            lines = resp.text.strip().split("\n")
            if len(lines) < 3:
                return {"yields": [], "curve": _empty_curve()}

            reader = csv.DictReader(io.StringIO(resp.text))
            rows = list(reader)
            if not rows:
                return {"yields": [], "curve": _empty_curve()}

            # Get last two rows
            latest = rows[-1]
            prev = rows[-2] if len(rows) > 1 else None

            yields = []
            for s in BOE_GILT_SERIES:
                try:
                    val_str = latest.get(s["series"], "").strip()
                    if not val_str:
                        yields.append({"name": s["name"], "maturity": s["maturity"], "value": None, "change": None})
                        continue
                    val = float(val_str)
                    chg = None
                    if prev:
                        try:
                            prev_str = prev.get(s["series"], "").strip()
                            if prev_str:
                                chg = round(val - float(prev_str), 3)
                        except (ValueError, TypeError):
                            pass
                    yields.append({"name": s["name"], "maturity": s["maturity"], "value": round(val, 3), "change": chg})
                except (ValueError, TypeError):
                    yields.append({"name": s["name"], "maturity": s["maturity"], "value": None, "change": None})

            return {"yields": yields, "curve": _build_curve(yields)}

        except Exception as e:
            logger.warning("BoE Gilts fetch error: %s", e)
            return {"yields": [], "curve": _empty_curve()}

    async def _fetch_euro(self, client: httpx.AsyncClient) -> dict:
        """Fetch Euro area yield curve from ECB Statistical Data Warehouse."""
        try:
            resp = await client.get(ECB_YC_URL)
            if resp.status_code != 200:
                logger.warning("ECB YC HTTP %d", resp.status_code)
                return {"yields": [], "curve": _empty_curve()}

            reader = csv.DictReader(io.StringIO(resp.text))
            rows = list(reader)

            # Group by tenor, get latest and previous values
            tenor_data = {}
            for row in rows:
                key = row.get("KEY", "")
                # Extract tenor from key (last segment like SR_10Y)
                parts = key.split(".")
                tenor = parts[-1] if parts else ""
                if tenor not in ECB_TENOR_MAP:
                    continue

                val_str = row.get("OBS_VALUE", "").strip()
                if not val_str:
                    continue
                val = float(val_str)

                if tenor not in tenor_data:
                    tenor_data[tenor] = []
                tenor_data[tenor].append(val)

            yields = []
            for tenor_key, meta in ECB_TENOR_MAP.items():
                values = tenor_data.get(tenor_key, [])
                if not values:
                    yields.append({"name": meta["name"], "maturity": meta["maturity"], "value": None, "change": None})
                    continue

                latest_val = values[-1]
                chg = round(latest_val - values[-2], 3) if len(values) > 1 else None
                yields.append({
                    "name": meta["name"],
                    "maturity": meta["maturity"],
                    "value": round(latest_val, 3),
                    "change": chg,
                })

            return {"yields": yields, "curve": _build_curve(yields)}

        except Exception as e:
            logger.warning("ECB YC fetch error: %s", e)
            return {"yields": [], "curve": _empty_curve()}


def _build_curve(yields: list[dict]) -> dict:
    """Build yield curve chart data from yield list."""
    maturities = []
    values = []
    labels = []
    for item in sorted(yields, key=lambda x: x.get("maturity", 0)):
        if item.get("value") is not None:
            maturities.append(item["maturity"])
            values.append(item["value"])
            labels.append(item["name"])
    return {"maturities": maturities, "yields": values, "labels": labels}


def _empty_curve() -> dict:
    return {"maturities": [], "yields": [], "labels": []}


def _calc_spreads(yields: list[dict]) -> list[dict]:
    """Calculate key yield curve spreads for any geography."""
    yield_map = {item["maturity"]: item.get("value") for item in yields if item.get("value") is not None}
    spreads = []

    # 2s10s — the universal curve shape measure
    if 2 in yield_map and 10 in yield_map:
        spreads.append({
            "label": "2s10s",
            "spread": round(yield_map[10] - yield_map[2], 3),
            "long": yield_map[10],
            "short": yield_map[2],
        })

    # 2s30s — long-end steepness (where 30Y exists)
    if 2 in yield_map and 30 in yield_map:
        spreads.append({
            "label": "2s30s",
            "spread": round(yield_map[30] - yield_map[2], 3),
            "long": yield_map[30],
            "short": yield_map[2],
        })

    # 5s30s — alternative long-end measure
    if 5 in yield_map and 30 in yield_map:
        spreads.append({
            "label": "5s30s",
            "spread": round(yield_map[30] - yield_map[5], 3),
            "long": yield_map[30],
            "short": yield_map[5],
        })

    # 3s10s — for Australia which has limited maturities
    if 3 in yield_map and 10 in yield_map and 2 not in yield_map:
        spreads.append({
            "label": "3s10s",
            "spread": round(yield_map[10] - yield_map[3], 3),
            "long": yield_map[10],
            "short": yield_map[3],
        })

    return spreads
