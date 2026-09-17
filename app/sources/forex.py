"""Forex pairs (multi-period returns), heatmap data, and correlations."""

from datetime import datetime
import math

from app.config import (
    REFRESH_FOREX, FOREX_PAIRS, FOREX_CURRENCIES,
    FOREX_USD_PAIRS, FOREX_USD_QUOTE, FOREX_USD_BASE,
    FOREX_HEATMAP_PERIODS,
)
from app.sources.base import BaseSource, logger
from app.sources.yahoo_quotes import PERIOD_DAYS, fetch_multi_period_returns_async, fetch_all_spark

# Key pairs for the correlation matrix
CORRELATION_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    "USDCAD=X", "USDCHF=X", "NZDUSD=X", "USDCNH=X",
]
CORRELATION_LABELS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD",
    "USD/CAD", "USD/CHF", "NZD/USD", "USD/CNH",
]

CORRELATION_PERIODS = {
    label: PERIOD_DAYS[label]
    for label in ["1W", "1M", "3M", "1Y", "5Y", "10Y"]
}


class ForexSource(BaseSource):
    cache_key = "forex"
    refresh_interval = REFRESH_FOREX

    async def fetch(self) -> dict:
        pairs = await fetch_multi_period_returns_async(FOREX_PAIRS)
        heatmaps = await self._fetch_heatmaps()
        correlations = await self._fetch_correlations()
        return {"pairs": pairs, "heatmaps": heatmaps, "correlations": correlations}

    async def _fetch_heatmaps(self) -> dict:
        usd_symbols = list(FOREX_USD_PAIRS.values())
        currencies = FOREX_CURRENCIES

        # Fetch 10Y of daily data once so every heatmap period can be calculated.
        spark_data = await fetch_all_spark(usd_symbols, time_range="10y")

        heatmaps = {}
        for period_label, period_config in FOREX_HEATMAP_PERIODS.items():
            try:
                matrix = self._calc_heatmap_from_spark(
                    spark_data, currencies, period_config
                )
                heatmaps[period_label] = {
                    "currencies": currencies,
                    "matrix": matrix,
                }
            except Exception as e:
                logger.debug("Heatmap %s error: %s", period_label, e)
                heatmaps[period_label] = {
                    "currencies": currencies,
                    "matrix": [[None] * len(currencies) for _ in currencies],
                }

        return heatmaps

    def _calc_heatmap_from_spark(self, spark_data: dict, currencies: list[str],
                                  period_config: dict) -> list[list]:
        days_back = period_config["days_back"]

        ccy_returns = {}
        for ccy in currencies:
            if ccy == "USD":
                continue
            pair_sym = FOREX_USD_PAIRS.get(ccy)
            if not pair_sym or pair_sym not in spark_data:
                continue

            sd = spark_data[pair_sym]
            closes = sd["closes"]
            if len(closes) < 2:
                continue

            # Invert if needed (USD is quote currency)
            if ccy in FOREX_USD_QUOTE:
                values = closes
            else:
                values = [1.0 / c if c != 0 else 0 for c in closes]

            if days_back is not None:
                idx = min(days_back, len(values) - 1)
                start_val = values[-(idx + 1)]
            else:
                start_idx = self._first_current_year_index(sd.get("timestamps", []), len(values))
                start_val = values[start_idx]

            end_val = values[-1]
            if start_val != 0:
                ret = (end_val / start_val - 1) * 100
                ccy_returns[ccy] = ret

        ccy_returns["USD"] = 0.0

        matrix = []
        for row_ccy in currencies:
            row = []
            for col_ccy in currencies:
                if row_ccy == col_ccy:
                    row.append(None)
                elif row_ccy in ccy_returns and col_ccy in ccy_returns:
                    val = round(ccy_returns[row_ccy] - ccy_returns[col_ccy], 2)
                    row.append(val)
                else:
                    row.append(None)
            matrix.append(row)

        return matrix

    @staticmethod
    def _first_current_year_index(timestamps: list[int], fallback_len: int) -> int:
        current_year = datetime.utcnow().year
        for idx, ts in enumerate(timestamps):
            if datetime.utcfromtimestamp(ts).year == current_year:
                return idx
        return max(0, fallback_len - 252)

    async def _fetch_correlations(self) -> dict:
        """Compute rolling correlation matrices for key FX pairs by lookback."""
        spark_data = await fetch_all_spark(CORRELATION_PAIRS, time_range="10y")

        correlations = {}
        for period_label, window in CORRELATION_PERIODS.items():
            pair_returns = {}
            for sym, label in zip(CORRELATION_PAIRS, CORRELATION_LABELS):
                sd = spark_data.get(sym)
                if not sd or len(sd["closes"]) < window + 1:
                    continue
                closes = sd["closes"][-(window + 1):]
                returns = [
                    (closes[i] / closes[i - 1] - 1)
                    for i in range(1, len(closes))
                    if closes[i - 1] != 0
                ]
                pair_returns[label] = returns

            labels = [l for l in CORRELATION_LABELS if l in pair_returns]
            correlations[period_label] = {
                "labels": labels,
                "matrix": self._correlation_matrix(labels, pair_returns),
                "window_days": window,
            }

        return correlations

    def _correlation_matrix(self, labels: list[str], pair_returns: dict[str, list[float]]) -> list[list]:
        matrix = []
        for i, row_label in enumerate(labels):
            row = []
            for j, col_label in enumerate(labels):
                if i == j:
                    row.append(1.0)
                else:
                    row.append(self._pearson(pair_returns[row_label], pair_returns[col_label]))
            matrix.append(row)
        return matrix

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float | None:
        """Pure-python Pearson correlation."""
        n = min(len(x), len(y))
        if n < 3:
            return None
        x, y = x[:n], y[:n]
        mx = sum(x) / n
        my = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return None
        return round(cov / (sx * sy), 3)
