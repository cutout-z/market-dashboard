"""Shared multi-period return calculation for asset price sources."""

import time

import yfinance as yf
from app.sources.base import logger

# Trading-day offsets for each return period
PERIOD_DAYS = {
    "24h": 1,
    "1W": 5,
    "1M": 21,
    "3M": 63,
    "1Y": 252,
    "5Y": 1260,
    "10Y": 2520,
}

PERIOD_LABELS = list(PERIOD_DAYS.keys())

# Max symbols per yfinance batch to avoid rate limiting on cloud hosts
_BATCH_SIZE = 5
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds, doubles each retry


def _download_batch(symbols: list[str], period: str = "2y", retries: int = _MAX_RETRIES):
    """Download a single batch with retry + exponential backoff."""
    delay = _RETRY_DELAY
    for attempt in range(retries):
        try:
            data = yf.download(
                symbols, period=period, progress=False,
                auto_adjust=True, threads=False,
            )
            if not data.empty:
                return data
            logger.warning("yfinance empty for %s period=%s (attempt %d)", symbols, period, attempt + 1)
        except Exception as e:
            logger.warning("yfinance error for %s period=%s (attempt %d): %s", symbols, period, attempt + 1, e)

        if attempt < retries - 1:
            time.sleep(delay)
            delay *= 2

    return None


def _download_with_retry(symbols: list[str], period: str = "2y"):
    """Download symbols in small batches with retry and backoff."""
    import pandas as pd

    all_frames = []
    batches = [symbols[i:i + _BATCH_SIZE] for i in range(0, len(symbols), _BATCH_SIZE)]

    for batch in batches:
        result = _download_batch(batch, period=period)
        if result is not None:
            all_frames.append(result)

        # Small pause between batches
        if len(batches) > 1:
            time.sleep(1)

    if not all_frames:
        return pd.DataFrame()

    if len(all_frames) == 1:
        return all_frames[0]

    return pd.concat(all_frames, axis=1)


def fetch_multi_period_returns(items: list[dict], symbol_key: str = "symbol") -> list[dict]:
    """Fetch current price + multi-period % returns for a list of assets.

    Uses a 2-year download for core data (24h through 1Y returns).
    5Y and 10Y returns are attempted separately with a longer period.
    """
    symbols = [i[symbol_key] for i in items]
    if not symbols:
        return []

    # Primary download: 2y covers 24h through 1Y returns reliably
    data = _download_with_retry(symbols, period="2y")

    if data.empty:
        logger.warning("All downloads returned empty for %d symbols", len(symbols))
        return [_empty_item(i) for i in items]

    # Handle single vs multi-symbol DataFrames
    if len(symbols) == 1:
        close = data[["Close"]].copy()
        close.columns = [symbols[0]]
    else:
        close = data["Close"]

    # Try extended history for 5Y/10Y (best-effort, won't block core data)
    extended_close = None
    try:
        ext_data = _download_with_retry(symbols, period="10y")
        if not ext_data.empty:
            if len(symbols) == 1:
                extended_close = ext_data[["Close"]].copy()
                extended_close.columns = [symbols[0]]
            else:
                extended_close = ext_data["Close"]
    except Exception as e:
        logger.debug("Extended history fetch failed (non-critical): %s", e)

    results = []
    for entry in items:
        sym = entry[symbol_key]
        try:
            if sym not in close.columns:
                results.append(_empty_item(entry))
                continue

            series = close[sym].dropna()
            if len(series) < 2:
                results.append(_empty_item(entry))
                continue

            current_price = float(series.iloc[-1])

            # Use extended series for long-term returns if available
            ext_series = None
            if extended_close is not None and sym in extended_close.columns:
                ext_series = extended_close[sym].dropna()

            # Calculate returns for each period
            returns = {}
            for period_label, days_back in PERIOD_DAYS.items():
                # Use extended data for 5Y/10Y if available
                s = ext_series if ext_series is not None and days_back > 252 else series

                if s is not None and len(s) > days_back:
                    past_price = float(s.iloc[-(days_back + 1)])
                    if past_price != 0:
                        ret = ((current_price / past_price) - 1) * 100
                        returns[period_label] = round(ret, 2)
                    else:
                        returns[period_label] = None
                else:
                    returns[period_label] = None

            # Determine decimal places based on price magnitude
            if current_price < 1:
                price_fmt = round(current_price, 4)
            elif current_price < 10:
                price_fmt = round(current_price, 3)
            else:
                price_fmt = round(current_price, 2)

            # Sparkline: last 6 close prices (5 segments)
            spark_count = min(6, len(series))
            sparkline = [round(float(v), 4) for v in series.iloc[-spark_count:].tolist()]

            results.append({
                **entry,
                "price": price_fmt,
                "returns": returns,
                "sparkline": sparkline,
            })
        except Exception as e:
            logger.debug("Returns calc error for %s: %s", sym, e)
            results.append(_empty_item(entry))

    return results


def _empty_item(entry: dict) -> dict:
    return {
        **entry,
        "price": None,
        "returns": {p: None for p in PERIOD_LABELS},
        "sparkline": [],
    }
