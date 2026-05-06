"""Fast batch quote + returns fetcher using Yahoo Finance v8 spark API.

Replaces yfinance for price/returns/sparkline needs. Batches of 20 symbols
per HTTP call, all async. ~116 symbols complete in under 2 seconds vs
60-90s with yfinance.
"""

import asyncio

import httpx
from app.sources.base import logger

_SPARK_URL = "https://query1.finance.yahoo.com/v8/finance/spark"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_TIMEOUT = 15
_BATCH_SIZE = 20  # Yahoo spark limit is ~20 symbols per call

# Trading-day offsets for each return period
PERIOD_DAYS = {
    "24h": 1,
    "1W": 5,
    "1M": 21,
    "3M": 63,
    "1Y": 252,
    "5Y": 1260,
    "10Y": 2500,  # spark returns ~2513 pts for 10y range
}

PERIOD_LABELS = list(PERIOD_DAYS.keys())


def _format_price(price: float | None) -> float | None:
    """Format price with appropriate decimal places."""
    if price is None:
        return None
    if price < 1:
        return round(price, 4)
    elif price < 10:
        return round(price, 3)
    return round(price, 2)


async def _fetch_spark_batch(client: httpx.AsyncClient, symbols: list[str],
                              time_range: str = "1y") -> dict[str, dict]:
    """Fetch spark data for a batch of up to 20 symbols."""
    try:
        resp = await client.get(_SPARK_URL, params={
            "symbols": ",".join(symbols),
            "range": time_range,
            "interval": "1d",
        })
        if resp.status_code != 200:
            logger.warning("Yahoo spark returned %d for %d symbols", resp.status_code, len(symbols))
            return {}

        data = resp.json()
        results = {}
        for sym, spark in data.items():
            if not isinstance(spark, dict):
                continue
            closes = spark.get("close") or []
            timestamps = spark.get("timestamp") or []
            if not closes:
                continue
            # Filter out None values but keep alignment
            if timestamps and len(timestamps) == len(closes):
                clean = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
                if clean:
                    ts_clean, close_clean = zip(*clean)
                    results[sym] = {
                        "closes": list(close_clean),
                        "timestamps": list(ts_clean),
                        "chart_prev_close": spark.get("chartPreviousClose"),
                    }
            else:
                # No timestamps, just use closes directly
                clean_closes = [c for c in closes if c is not None]
                if clean_closes:
                    results[sym] = {
                        "closes": clean_closes,
                        "timestamps": [],
                        "chart_prev_close": spark.get("chartPreviousClose"),
                    }
        return results
    except Exception as e:
        logger.warning("Yahoo spark batch failed: %s", e)
        return {}


async def fetch_all_spark(symbols: list[str], time_range: str = "1y") -> dict[str, dict]:
    """Fetch spark data for all symbols, batched into groups of 20, all concurrent."""
    if not symbols:
        return {}

    batches = [symbols[i:i + _BATCH_SIZE] for i in range(0, len(symbols), _BATCH_SIZE)]

    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
        tasks = [_fetch_spark_batch(client, batch, time_range) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

    merged = {}
    for result in batch_results:
        merged.update(result)
    return merged


def compute_returns_from_closes(closes: list[float]) -> dict[str, float | None]:
    """Compute multi-period returns from a daily close price series."""
    if len(closes) < 2:
        return {p: None for p in PERIOD_LABELS}

    current = closes[-1]
    returns = {}
    for label, days_back in PERIOD_DAYS.items():
        if len(closes) > days_back:
            past = closes[-(days_back + 1)]
            if past != 0:
                returns[label] = round(((current / past) - 1) * 100, 2)
            else:
                returns[label] = None
        else:
            returns[label] = None
    return returns


async def fetch_spot_prices(symbols: list[str]) -> dict[str, float | None]:
    """Fetch just the latest price for a list of symbols (cheap: 5d range)."""
    if not symbols:
        return {}
    spark_data = await fetch_all_spark(symbols, time_range="5d")
    return {
        sym: _format_price(data["closes"][-1]) if data.get("closes") else None
        for sym, data in spark_data.items()
    }


def _compute_sparkline(closes: list[float], period: str,
                        max_points: int = 50) -> list[float]:
    """Extract sparkline data for a given period, downsampled for rendering."""
    days_back = PERIOD_DAYS.get(period, 5)
    n = days_back + 1
    series = closes[-n:] if len(closes) >= n else closes[:]

    if len(series) > max_points:
        step = len(series) / max_points
        sampled = [series[int(i * step)] for i in range(max_points - 1)]
        sampled.append(series[-1])  # always include the latest point
        series = sampled

    return [round(c, 4) for c in series]


async def fetch_multi_period_returns_async(items: list[dict],
                                            symbol_key: str = "symbol") -> list[dict]:
    """Async replacement for the old sync fetch_multi_period_returns.

    Uses Yahoo spark API instead of yfinance. Returns enriched items with
    price, returns dict, sparkline, and sparklines (per-period dict).
    """
    symbols = list({i[symbol_key] for i in items})  # deduplicate
    if not symbols:
        return []

    spark_data = await fetch_all_spark(symbols, time_range="10y")

    results = []
    for entry in items:
        sym = entry[symbol_key]
        sd = spark_data.get(sym)

        if not sd or not sd["closes"]:
            results.append({
                **entry,
                "price": None,
                "returns": {p: None for p in PERIOD_LABELS},
                "sparkline": [],
                "sparklines": {p: [] for p in PERIOD_LABELS},
            })
            continue

        closes = sd["closes"]
        current_price = closes[-1]

        results.append({
            **entry,
            "price": _format_price(current_price),
            "returns": compute_returns_from_closes(closes),
            "sparkline": [round(c, 4) for c in closes[-6:]],
            "sparklines": {p: _compute_sparkline(closes, p) for p in PERIOD_LABELS},
        })

    return results
