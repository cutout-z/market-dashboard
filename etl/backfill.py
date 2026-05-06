"""Backfill historical OHLCV data for all tracked symbols.

Usage:
    python -m etl.backfill              # Full backfill (period=max)
    python -m etl.backfill --incremental  # Append since last update
    python -m etl.backfill --symbols AAPL MSFT  # Specific symbols only
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import all_tracked_symbols

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")

HISTORY_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "history"
PARQUET_PATH = HISTORY_DIR / "prices.parquet"
METADATA_PATH = HISTORY_DIR / "metadata.json"
BATCH_SIZE = 20
BATCH_PAUSE = 1.0  # seconds between batches


def _download_batch(symbols: list[str], period: str = "max", start: str | None = None) -> pd.DataFrame:
    """Download OHLCV for a batch of symbols, return long-format DataFrame."""
    tickers_str = " ".join(symbols)
    kwargs = {"group_by": "ticker", "threads": True, "progress": False}
    if start:
        kwargs["start"] = start
    else:
        kwargs["period"] = period

    raw = yf.download(tickers_str, **kwargs)
    if raw.empty:
        return pd.DataFrame()

    frames = []
    for sym in symbols:
        try:
            if len(symbols) == 1:
                df = raw.copy()
            else:
                df = raw[sym].copy()
            df = df.dropna(how="all")
            if df.empty:
                continue
            df = df.reset_index()
            # Normalise column names (yfinance may capitalise differently)
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            if "date" not in df.columns and "datetime" in df.columns:
                df = df.rename(columns={"datetime": "date"})
            df["symbol"] = sym
            # Keep only OHLCV columns
            keep = [c for c in ["date", "symbol", "open", "high", "low", "close", "volume"] if c in df.columns]
            frames.append(df[keep])
        except (KeyError, TypeError):
            logger.warning("No data for %s", sym)
            continue

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def backfill(symbols: list[str], incremental: bool = False) -> pd.DataFrame:
    """Download historical data for all symbols and save as Parquet."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    start_date = None
    if incremental and METADATA_PATH.exists():
        meta = json.loads(METADATA_PATH.read_text())
        start_date = meta.get("last_updated")
        if start_date:
            logger.info("Incremental mode: fetching from %s", start_date)

    # Batch downloads
    all_frames = []
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info("Batch %d/%d: %s", batch_num, total_batches, ", ".join(batch))

        df = _download_batch(batch, start=start_date)
        if not df.empty:
            all_frames.append(df)

        if i + BATCH_SIZE < len(symbols):
            time.sleep(BATCH_PAUSE)

    if not all_frames:
        logger.error("No data downloaded")
        return pd.DataFrame()

    new_data = pd.concat(all_frames, ignore_index=True)

    # Merge with existing data if incremental
    if incremental and PARQUET_PATH.exists():
        existing = pd.read_parquet(PARQUET_PATH)
        combined = pd.concat([existing, new_data], ignore_index=True)
        # Deduplicate on (date, symbol), keeping latest
        combined["date"] = pd.to_datetime(combined["date"])
        combined = combined.drop_duplicates(subset=["date", "symbol"], keep="last")
        combined = combined.sort_values(["symbol", "date"]).reset_index(drop=True)
    else:
        combined = new_data
        combined["date"] = pd.to_datetime(combined["date"])
        combined = combined.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Save
    combined.to_parquet(PARQUET_PATH, index=False, engine="pyarrow", compression="zstd")

    # Metadata
    meta = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "symbol_count": combined["symbol"].nunique(),
        "total_rows": len(combined),
        "date_range": {
            "start": str(combined["date"].min().date()),
            "end": str(combined["date"].max().date()),
        },
        "file_size_mb": round(PARQUET_PATH.stat().st_size / 1_048_576, 2),
    }
    METADATA_PATH.write_text(json.dumps(meta, indent=2))
    logger.info(
        "Saved %s rows for %s symbols (%s MB) — %s to %s",
        f"{meta['total_rows']:,}",
        meta["symbol_count"],
        meta["file_size_mb"],
        meta["date_range"]["start"],
        meta["date_range"]["end"],
    )
    return combined


def main():
    parser = argparse.ArgumentParser(description="Backfill historical OHLCV data")
    parser.add_argument("--incremental", action="store_true", help="Only fetch since last update")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols (default: all tracked)")
    args = parser.parse_args()

    symbols = args.symbols or all_tracked_symbols()
    logger.info("Backfilling %d symbols (%s)", len(symbols), "incremental" if args.incremental else "full")

    backfill(symbols, incremental=args.incremental)


if __name__ == "__main__":
    main()
