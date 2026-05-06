"""JSON API endpoints — status, sources, and historical data."""

from fastapi import APIRouter, Query

import numpy as np
import pandas as pd

from app.routes.partials import ALL_SOURCES
from app.sources.historical import HistoricalData

router = APIRouter(prefix="/api")


@router.get("/status")
async def api_status():
    return {
        s.cache_key: s.get_cached() or {}
        for s in ALL_SOURCES
    }


@router.get("/sources")
async def api_sources():
    result = {}
    for s in ALL_SOURCES:
        age = s.cache_age()
        result[s.cache_key] = {
            "refresh_interval": s.refresh_interval,
            "cache_age_seconds": round(age, 1) if age else None,
            "has_data": s.get_cached() is not None,
        }
    return result


# ─── Historical Data API ───


@router.get("/history/symbols")
async def api_history_symbols():
    """List all available historical symbols with date ranges."""
    if not HistoricalData.is_loaded():
        return {"symbols": [], "error": "Historical data not loaded"}
    return {
        "symbols": HistoricalData.symbols(),
        "date_range": HistoricalData.date_range(),
    }


@router.get("/history/{symbol}")
async def api_history(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
):
    """OHLCV time series for a single symbol."""
    df = HistoricalData.get_series(symbol, start=start, end=end)
    if df.empty:
        return {"symbol": symbol, "data": [], "error": "No data found"}
    records = df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records")
    return {"symbol": symbol, "count": len(records), "data": records}


@router.get("/history/{symbol}/ma")
async def api_history_ma(
    symbol: str,
    periods: str = "50,200",
    ma_type: str = "sma",
    start: str | None = None,
    end: str | None = None,
):
    """Price series with moving average overlays."""
    df = HistoricalData.get_series(symbol, start=start, end=end)
    if df.empty:
        return {"symbol": symbol, "data": [], "error": "No data found"}

    result = {
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "close": df["close"].tolist(),
        "moving_averages": {},
    }

    for p in periods.split(","):
        p = int(p.strip())
        if ma_type == "ema":
            ma = df["close"].ewm(span=p, adjust=False).mean()
        else:
            ma = df["close"].rolling(window=p, min_periods=p).mean()
        result["moving_averages"][f"{ma_type.upper()}{p}"] = [
            None if pd.isna(v) else round(v, 4) for v in ma
        ]

    return {"symbol": symbol, **result}


@router.get("/correlation")
async def api_correlation(
    symbols: str = Query(description="Comma-separated symbols"),
    lookback: int = Query(default=90, description="Lookback window in trading days"),
    start: str | None = None,
    end: str | None = None,
):
    """Rolling correlation matrix for selected symbols."""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if len(sym_list) < 2:
        return {"error": "Need at least 2 symbols"}

    closes = HistoricalData.get_multi(sym_list, column="close", start=start, end=end)
    if closes.empty or len(closes) < lookback:
        return {"error": "Insufficient data", "rows_available": len(closes)}

    # Use returns for correlation (more stationary than prices)
    returns = closes.pct_change().dropna()
    corr = returns.tail(lookback).corr()

    labels = corr.columns.tolist()
    matrix = [
        [None if pd.isna(v) else round(v, 3) for v in row]
        for row in corr.values.tolist()
    ]
    return {"labels": labels, "lookback": lookback, "matrix": matrix}


@router.get("/drawdown/{symbol}")
async def api_drawdown(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
):
    """Drawdown series from peak for a symbol."""
    df = HistoricalData.get_series(symbol, start=start, end=end)
    if df.empty:
        return {"symbol": symbol, "data": [], "error": "No data found"}

    cummax = df["close"].cummax()
    drawdown = (df["close"] - cummax) / cummax

    max_dd = drawdown.min()
    max_dd_idx = drawdown.idxmin()
    max_dd_date = df.loc[max_dd_idx, "date"].strftime("%Y-%m-%d") if pd.notna(max_dd_idx) else None

    return {
        "symbol": symbol,
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "close": df["close"].tolist(),
        "drawdown": [round(v, 4) for v in drawdown.tolist()],
        "max_drawdown": round(max_dd, 4) if pd.notna(max_dd) else None,
        "max_drawdown_date": max_dd_date,
    }


@router.get("/volatility/{symbol}")
async def api_volatility(
    symbol: str,
    window: int = Query(default=21, description="Rolling window in trading days"),
    start: str | None = None,
    end: str | None = None,
):
    """Rolling annualised volatility for a symbol."""
    df = HistoricalData.get_series(symbol, start=start, end=end)
    if df.empty or len(df) < window + 1:
        return {"symbol": symbol, "error": "Insufficient data"}

    returns = df["close"].pct_change()
    rolling_vol = returns.rolling(window=window).std() * np.sqrt(252) * 100  # annualised %

    return {
        "symbol": symbol,
        "window": window,
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "volatility": [None if pd.isna(v) else round(v, 2) for v in rolling_vol.tolist()],
        "current_vol": round(rolling_vol.iloc[-1], 2) if pd.notna(rolling_vol.iloc[-1]) else None,
    }


@router.get("/returns-distribution/{symbol}")
async def api_returns_distribution(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
):
    """Daily return distribution with percentile ranks."""
    df = HistoricalData.get_series(symbol, start=start, end=end)
    if df.empty or len(df) < 30:
        return {"symbol": symbol, "error": "Insufficient data"}

    returns = df["close"].pct_change().dropna() * 100  # as percentage

    # Current drawdown percentile
    cummax = df["close"].cummax()
    current_dd = ((df["close"].iloc[-1] - cummax.iloc[-1]) / cummax.iloc[-1]) * 100

    percentiles = [5, 10, 25, 50, 75, 90, 95]
    pct_values = {str(p): round(float(np.percentile(returns, p)), 2) for p in percentiles}

    # Histogram bins
    hist_counts, hist_edges = np.histogram(returns, bins=50)

    return {
        "symbol": symbol,
        "mean": round(float(returns.mean()), 4),
        "std": round(float(returns.std()), 4),
        "skew": round(float(returns.skew()), 4),
        "kurtosis": round(float(returns.kurtosis()), 4),
        "percentiles": pct_values,
        "current_drawdown_pct": round(float(current_dd), 2),
        "hist_counts": hist_counts.tolist(),
        "hist_edges": [round(float(e), 3) for e in hist_edges.tolist()],
        "total_days": len(returns),
    }
