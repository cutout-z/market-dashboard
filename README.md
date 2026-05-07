# Market Dashboard

Live market dashboard and auto-research lab for cross-asset macro monitoring, tactical signal research, and higher-timeframe regime testing.

**Public Hetzner instance:** [http://116.203.146.144:8060](http://116.203.146.144:8060)

> This is a research dashboard, not financial advice. Signals are experimental model outputs and should be treated as decision-support context, not trade instructions.

## What It Does

Market Dashboard is a FastAPI + HTMX application that pulls together market, macro, positioning, news, and strategy-research views in one lightweight interface.

The app has three broad jobs:

1. **Monitor markets**
   - Indices, futures, commodities, forex, bonds, Mag 7 / AI names, movers, and volatility context.
   - Live-ish refresh loops run in the FastAPI process and cache source results.

2. **Track macro and event context**
   - FRED-backed yield curve, credit, policy-rate, inflation, and economic indicator views.
   - COT positioning via CFTC public data.
   - News and prediction-market panels for macro/event awareness.
   - Historical shock analogs for comparing active events against prior macro shocks.

3. **Run auto-research**
   - Tactical signal parameter sweeps run hourly.
   - Higher-timeframe signal sweeps run separately on a slower cadence.
   - News-classification and source-quality experiments are logged alongside market strategy research.

## Live Pages

The sidebar exposes the main sections:

| Section | Pages |
| --- | --- |
| Assets | Indices, Futures, Commodities, Forex |
| Fixed Income | Bonds |
| Macro | Economy, Macro Pulse |
| Markets | Mag 7 & AI, Movers |
| News & Events | News |
| Analysis | Historical, Positioning (COT), Shock Analogs, Signals |

The most research-heavy page is:

```text
/signals
```

Direct link:

[http://116.203.146.144:8060/signals](http://116.203.146.144:8060/signals)

## Signals And Trade Expressions

Signals use a simple convention:

| Signal | Meaning |
| --- | --- |
| `LONG` | Hold long exposure to the strategy's target asset. |
| `FLAT` | Hold cash / no directional exposure instead of the target asset. |
| `SHORT` | Hold short exposure to the target asset. Only some strategies can emit this. |

Each signal card now includes:

- **Target**: the market being expressed, such as S&P 500, gold, crude oil, copper, or AUD/USD.
- **Trade Expression**: plain-English translation of the current signal.
- **Cadence**: whether the signal is tactical/daily or higher-timeframe/monthly.
- **Sizing note**: how to interpret exposure metrics. In particular, historical `Exposure` is time-in-market, not a recommended portfolio weight.

Current strategy families include:

| Strategy | Target | Style |
| --- | --- | --- |
| `RiskOffComposite` | S&P 500 / SPY / ES beta | Tactical risk-on/risk-off composite using VIX, DXY, copper/gold, and VIX term structure. |
| `VIXTermStructure` | S&P 500 / SPY / ES beta | Tactical volatility-regime filter. |
| `MomentumCrossover` | S&P 500 / SPY / ES beta | Medium-term moving-average trend filter. |
| `MeanReversion` | S&P 500 / SPY / ES beta | Tactical overextension / z-score defensive filter. |
| `GoldCopperMomentum` | S&P 500 / SPY / ES beta | Cross-asset growth/risk overlay. |
| `AUDUSDRateShock` | AUD/USD spot / FXA / 6A futures | Tactical FX regime signal using US yield, DXY, VIX, and copper/gold rate-shock proxies. |
| `MonthlyTrendRegime` | S&P 500 / SPY / ES beta | Higher-timeframe monthly trend regime. |
| `GoldMonthlyTrend` | Gold / GLD / GC futures | Higher-timeframe monthly trend regime. |
| `CrudeMonthlyTrend` | WTI crude / USO / CL futures | Higher-timeframe monthly trend regime. |
| `CopperMonthlyTrend` | Copper / CPER / HG futures | Higher-timeframe monthly trend regime. |
| `AUDUSDMonthlyTrend` | AUD/USD spot / FXA / 6A futures | Higher-timeframe monthly AUD/USD trend regime. |

## Auto-Research Components

The auto-research loop is intentionally simple and inspectable. It keeps findings in JSONL logs and repeatedly mutates parameters, evaluates outcomes, and preserves the best-known configurations.

### Tactical Worker

Entrypoint:

```bash
python worker.py
```

What it runs:

```text
signals.autoresearch
news_classification.autoresearch
data_quality.run_eval --snapshot
```

Default cadence:

```text
Hourly
```

Main output files:

```text
signals/findings.jsonl
news_classification/findings.jsonl
data_quality/events.jsonl
data_quality/findings.jsonl
```

These generated logs are intentionally ignored for future commits.

### Higher-Timeframe Worker

Entrypoint:

```bash
python worker_htf.py
```

Docker override command:

```bash
python worker_htf.py --interval 604800
```

This worker is designed for slower monthly/weekly ideas where the goal is robustness, drawdown control, and parameter stability rather than frequent tactical mutation.

Higher-timeframe evaluation adds:

- composite objective score
- buy-and-hold max drawdown comparison
- exposure / time-in-market
- rolling walk-forward windows
- buy-and-hold beat-rate diagnostics

## Data Sources

The dashboard uses a mix of public APIs, market-data endpoints, and local historical files.

| Source | Used For |
| --- | --- |
| Yahoo Finance / Yahoo spark endpoints | Prices, returns, futures, FX, equities, options-derived views. |
| FRED | Treasury curve, breakevens, credit spreads, policy rates, US and global macro indicators. |
| Financial Modeling Prep (FMP) | Earnings calendar and related company data. |
| CFTC Socrata API | Commitment of Traders positioning. |
| Google News RSS | Macro/news monitoring. |
| Polymarket API | Prediction-market context. |
| Local Parquet history | Backtests and signal evaluation. |

## Configuration

Runtime secrets are expected as environment variables:

```bash
FRED_API_KEY=...
FMP_API_KEY=...
```

On the Hetzner deployment they live outside the repository at:

```bash
/etc/market-dashboard/env
```

The repo should not contain real API keys. `.env`, logs, cache data, and generated findings are ignored.

## Running Locally

Python 3.12 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8060
```

Then open:

```text
http://localhost:8060
```

Optional local environment:

```bash
export FRED_API_KEY=...
export FMP_API_KEY=...
```

Without API keys, pages that depend on FRED or FMP will degrade or show source errors, but many price/history views still work.

## Running With Docker Compose

```bash
docker compose up --build
```

The compose stack runs:

| Service | Purpose |
| --- | --- |
| `dashboard` | FastAPI web app on port `8060`. |
| `worker` | Hourly tactical autoresearch, news classification, and source-quality snapshots. |
| `htf_worker` | Higher-timeframe strategy sweeps, via `docker-compose.override.yml`. |

## Hetzner Deployment

The live instance is currently served from a Hetzner cloud server:

```text
http://116.203.146.144:8060
```

Fresh-server setup script:

```bash
sudo bash deploy/setup.sh
```

Expected layout on the server:

```text
/home/market/app/market-dashboard
/etc/market-dashboard/env
```

Systemd service:

```bash
market-dashboard.service
```

Useful server commands:

```bash
cd /home/market/app/market-dashboard
git pull
docker compose --env-file /etc/market-dashboard/env ps
systemctl restart market-dashboard
journalctl -u market-dashboard -f
```

## Repository Layout

```text
app/
  main.py                 FastAPI app
  routes/                 Page, partial, and API routes
  sources/                Data source adapters
  templates/              HTMX/Jinja templates
  data/history/           Historical parquet data used by signal tests

signals/
  strategy.py             Base strategy contract and metadata
  strategies/             Concrete strategies
  autoresearch.py         Tactical mutation/evaluation loop
  htf_autoresearch.py     Higher-timeframe robustness-first loop
  evaluate.py             Backtest harness
  robustness.py           Walk-forward/objective scoring helpers

news_classification/      Keyword-weighted news classifier experiments
data_quality/             Source reliability snapshots and scoring
etl/                      Historical data backfill tooling
deploy/                   Hetzner/systemd setup files
```

## Caveats

- The public Hetzner instance is unauthenticated HTTP.
- Signal performance is backtest/research output, not live trading validation.
- Some macro and pre-1990 shock data is reference-grade and should be verified before use in a formal report.
- `AUDUSDRateShock` uses market proxies for rate-decision shocks; it is not yet wired to actual RBA/Fed surprise data.
- Public data providers can throttle, revise, or temporarily fail.

## License

No explicit license has been selected yet.
