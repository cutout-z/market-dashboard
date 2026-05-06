# Market Dashboard

Local-first market monitoring dashboard. Bloomberg morning stack (GMM/TOP/BTMM) concept built from free data sources.

## Architecture

- **FastAPI + HTMX + Jinja2** — multi-page with sidebar nav, per-panel auto-refresh
- **Plotly.js** — interactive charts (yield curve, etc.)
- **Tailwind CSS** — dark theme via CDN
- **Yahoo spark API** (primary) — async batch quotes/returns for 114 symbols in ~0.6s
- **yfinance** (secondary) — only for fundamentals (Ticker.info) and options chains
- Other: FRED API, Polymarket API, Google News RSS, ForexFactory JSON, central bank CSVs

## Running

```bash
cd market-dashboard
pip install -r requirements.txt
uvicorn app.main:app --port 8060 --reload
```

Dashboard at http://localhost:8060

## Pages

| Page | Route | Data Source | Refresh |
|------|-------|-------------|---------|
| Indices | /indices | Yahoo spark — world indices by region + S&P sectors + Defense indexes | 120s |
| Futures | /futures | Yahoo spark — 8 categories (ag, energy, metals, currency, indices, rates, livestock, fibres) | 120s |
| Forex | /forex | Yahoo spark — pairs table + NxN heatmap + 90-day pair correlations | 120s |
| Bonds | /bonds | Yahoo spark + FRED API — US yields, yield curve, spreads, MOVE index | 60s |
| Economy | /economy | Reference data + FRED historical charts (GDP, inflation, unemployment, rates) | hourly/6h |
| Macro Pulse | /pulse | Yahoo spark — HUD tiles, commodity ratios, sector rotation, correlation matrix | 120s |
| Commodities | /commodities | Yahoo spark — 36 commodities across 10 sectors with descriptions, market lens, forward curve, research panel | 120s |
| Mag 7 | /mag7 | Yahoo spark (prices) + yfinance (PE/EPS/fundamentals) | 120s |
| Movers | /movers | yfinance screener — top gainers, losers, most active | 5min |
| News | /news | Google News RSS + Polymarket API + ForexFactory economic calendar | 2-5min |
| AI Bubble Tracker | /bubble | Static reference — benchmarks (MMLU, GPQA, SWE-Bench), context windows, milestones | daily |
| Source Health | /api/sources | Live source freshness (21 sources), cache age, symbol coverage | 30s |

## Key Files

- `app/config.py` — all ticker lists, categories, refresh intervals, commodity drivers
- `app/sources/yahoo_quotes.py` — **core data fetcher** — async Yahoo spark API, batch quotes/returns
- `app/sources/` — one module per data domain (21 sources, base ABC + implementations)
- `app/sources/returns.py` — legacy yfinance returns module (kept for reference, no longer imported)
- `app/routes/pages.py` — page routes (one per section)
- `app/routes/partials.py` — HTMX partial endpoints (16 endpoints)
- `app/templates/base.html` — layout with sidebar navigation
- `app/templates/pages/` — page templates
- `app/templates/partials/` — HTMX partial templates
- `app/data/cache/` — JSON cache files (gitignored)

## Data Sources

| Source | Module | Status |
|--------|--------|--------|
| Yahoo spark API | yahoo_quotes.py → indices, futures, forex, bonds, pulse, commodities | Primary — 114 symbols in 0.6s |
| yfinance Ticker.info | mag7.py (fundamentals only) | Working — PE/EPS/market cap |
| yfinance options | options.py | Working — SPY IV skew |
| yfinance screener | movers.py | Working |
| FRED API | fred.py | Working — yield curve, economic indicators |
| ForexFactory JSON | calendar.py | Working (rate-limited API) |
| Google News RSS | news.py | Working |
| Polymarket API | polymarket.py | Working (direct API, DNS fallback) |
| Central bank CSVs | intl_bonds.py | Working — RBA, ECB, Japan MoF |

## Key Indicators

- **MOVE Index** (`^MOVE`) — bond market volatility, leads equity vol
- **2Y Yield** — via FRED DGS2 (yfinance 2YY=F delisted)
- **2s10s Spread** — 10Y minus 2Y, recession indicator
- **3M/10Y Spread** — alternative curve shape measure
- **DXY** (`DX-Y.NYB`) — US Dollar Index
- **Commodity Ratios** — Gold/Silver (risk), Copper/Gold (growth)

## Autoresearch Layers

Three autoresearch layers follow the Karpathy pattern: mutate params → evaluate → log → repeat.

| Layer | Directory | Mutation Surface | Evaluation Metric | CLI |
|-------|-----------|-----------------|-------------------|-----|
| 1. Signal Backtesting | `signals/` | Strategy params (thresholds, lookbacks, hold periods) | Sharpe ratio vs backtest | `python -m signals.autoresearch` |
| 2. News Classification | `news_classification/` | Per-category weight multipliers + thresholds (14 params) | Accuracy + weighted F1 vs labeled headlines | `python -m news_classification.autoresearch` |
| 3. Data Source Quality | `data_quality/` | Scorer weights (success, data, latency, streak) | Composite reliability score | `python -m data_quality.run_eval --snapshot` |

Layer 2 classifies news headlines into 8 categories: geopolitical, macro, trade, earnings, tech, energy, crypto, market. The dashboard (`app/sources/news.py`) auto-loads the best-known params from `news_classification/findings.jsonl`. Template color coding: red=geo, amber=macro, orange=trade, green=earnings, purple=tech, yellow=energy, cyan=crypto, blue=market.

## Performance Notes

- Refresh tasks staggered by 2s each at startup to avoid thundering herd
- Yahoo spark endpoint: 20 symbols/batch, all batches concurrent via asyncio.gather
- Return periods: 24h, 1W, 1M, 3M, 1Y, 5Y, 10Y (all 7 periods fetched via 10Y spark history)
- Cache safety: empty fetches don't overwrite good cached data
