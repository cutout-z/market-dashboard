"""Historical OHLCV data loader — reads Parquet into memory on startup."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger("market-dashboard")

HISTORY_DIR = Path(__file__).resolve().parent.parent / "data" / "history"
PARQUET_PATH = HISTORY_DIR / "prices.parquet"


class HistoricalData:
    """Singleton that loads the Parquet file once and serves DataFrame queries."""

    _df: pd.DataFrame | None = None

    @classmethod
    def load(cls):
        """Load Parquet into memory. Call once during app startup."""
        if not PARQUET_PATH.exists():
            logger.warning("No historical data at %s — skipping", PARQUET_PATH)
            return
        cls._df = pd.read_parquet(PARQUET_PATH)
        cls._df["date"] = pd.to_datetime(cls._df["date"])
        n_symbols = cls._df["symbol"].nunique()
        logger.info("Loaded historical data: %s rows, %d symbols", f"{len(cls._df):,}", n_symbols)

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._df is not None and not cls._df.empty

    @classmethod
    def symbols(cls) -> list[str]:
        """Return list of available symbols."""
        if not cls.is_loaded():
            return []
        return sorted(cls._df["symbol"].unique().tolist())

    @classmethod
    def get_series(
        cls, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return OHLCV for a single symbol, optionally filtered by date range."""
        if not cls.is_loaded():
            return pd.DataFrame()
        mask = cls._df["symbol"] == symbol
        if start:
            mask &= cls._df["date"] >= pd.Timestamp(start)
        if end:
            mask &= cls._df["date"] <= pd.Timestamp(end)
        return cls._df.loc[mask].copy().reset_index(drop=True)

    @classmethod
    def get_multi(
        cls,
        symbols: list[str],
        column: str = "close",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Return pivot table: date × symbols for a given column (default: close)."""
        if not cls.is_loaded():
            return pd.DataFrame()
        mask = cls._df["symbol"].isin(symbols)
        if start:
            mask &= cls._df["date"] >= pd.Timestamp(start)
        if end:
            mask &= cls._df["date"] <= pd.Timestamp(end)
        subset = cls._df.loc[mask, ["date", "symbol", column]]
        return subset.pivot_table(index="date", columns="symbol", values=column).sort_index()

    @classmethod
    def date_range(cls) -> tuple[str, str] | None:
        """Return (earliest, latest) date strings, or None if not loaded."""
        if not cls.is_loaded():
            return None
        return (
            str(cls._df["date"].min().date()),
            str(cls._df["date"].max().date()),
        )
