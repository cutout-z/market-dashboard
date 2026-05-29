# Signals — Autoresearch Harness

Applies Karpathy's autoresearch pattern to the market dashboard: signal strategies are evaluated against 15+ years of historical data, scored, and iteratively improved.

## Architecture

```
market-dashboard/
├── signals/
│   ├── strategy.py          # BaseStrategy ABC — all strategies inherit from this
│   ├── evaluate.py          # Backtester — Sharpe, CAGR, hit rate, max drawdown
│   ├── findings.py          # FindingsLog — JSONL, one entry per evaluation run
│   ├── run_eval.py          # CLI — evaluate individual strategies
│   ├── autoresearch.py      # CLI — automated mutation-evaluate loop
│   └── strategies/
│       ├── risk_off.py          # RiskOffComposite (macro risk-off)
│       ├── vix_term.py          # VIXTermStructure (VIX backwardation)
│       ├── momentum_crossover.py # MomentumCrossover (dual SMA trend)
│       ├── btc_sma_trend.py      # BTC SMA trend filters (50D, 200D, 200W)
│       ├── mean_reversion.py    # MeanReversion (z-score filter)
│       └── gold_copper_momentum.py # GoldCopperMomentum (cross-asset growth)
└── SIGNALS.md               # This file
```

Historical data: `app/data/history/prices.parquet` — 138 symbols, daily OHLCV, ~2000–present.

## Running the Harness

```bash
cd market-dashboard

# Evaluate all strategies with defaults
python -m signals.run_eval

# Evaluate a specific strategy
python -m signals.run_eval --strategy RiskOffComposite

# Mutate params and evaluate
python -m signals.run_eval --strategy RiskOffComposite --params vix_threshold=25 hold_days=10

# Print current leaderboard
python -m signals.run_eval --summary

# Dry run (evaluate, don't write)
python -m signals.run_eval --dry-run --strategy RiskOffComposite
```

## Autoresearch Runner

Automated mutation-evaluate loop. Reads current best params from findings log, generates mutations using four strategies (perturbation, boundary, random, combo), evaluates each, and logs results.

```bash
cd market-dashboard

# Full sweep — 10 mutations per strategy (default)
python -m signals.autoresearch

# Single strategy, more mutations
python -m signals.autoresearch --strategy RiskOffComposite --mutations 20

# Report: analyse findings and suggest next mutations
python -m signals.autoresearch --report

# Reproducible sweep with fixed seed
python -m signals.autoresearch --mutations 15 --seed 42

# Dry run — evaluate but don't log
python -m signals.autoresearch --dry-run
```

### Mutation strategies

1. **Perturbation** — ±10-30% of current best value, 1 param at a time
2. **Boundary** — try edges of the defined mutation range
3. **Random uniform** — sample within the full range
4. **Combo** — mutate 2 params simultaneously

Winners (Sharpe > current best) are flagged with ★ in output.

## Findings Log

All evaluation results are appended to `signals/findings.jsonl` (one JSON object per line).

Each entry contains:
- `timestamp` — UTC ISO 8601
- `sharpe` — annualised Sharpe ratio (strategy)
- `hit_rate` — fraction of active days with positive returns
- `max_drawdown` — worst peak-to-trough as a fraction
- `cagr` — compound annual growth rate (strategy)
- `trade_count` — entries into non-flat positions
- `bh_sharpe` / `bh_cagr` — buy-and-hold benchmark over same period
- `eval_period` — `{start, end}` dates actually evaluated
- `metadata` — strategy name, version, params used

The leaderboard tracks the highest-Sharpe result per strategy name.

## Strategies

### RiskOffComposite (`signals/strategies/risk_off.py`) — v4

Long S&P 500 by default. Goes flat (cash) when ≥ `conditions_required` of:
1. VIX > `vix_threshold` (default: 17)
2. Copper/Gold `copper_gold_lookback`-day change < `copper_gold_change` (default: −5% / 6d)
3. DXY at or above `dxy_breakout_days`-day high (default: 21d)
4. VIX spot > VIX 3-Month (term structure inverted)

Flat position held for `hold_days` after each trigger.

**Best result**: Sharpe 0.855 (B&H 0.745), CAGR 10.3%, max DD −25.4%

**Mutation surface** (all via `--params`):

| Param | Default | Range to explore |
|---|---|---|
| `vix_threshold` | 17.0 | 15–30 |
| `copper_gold_lookback` | 6 | 3–15 |
| `copper_gold_change` | -0.05 | -0.01 to -0.07 |
| `dxy_breakout_days` | 21 | 5–30 |
| `conditions_required` | 2 | 1–4 |
| `hold_days` | 1 | 1–10 |

### MeanReversion (`signals/strategies/mean_reversion.py`) — v1

Long S&P 500 by default. Goes flat when the z-score (price deviation from rolling mean in standard deviations) exceeds the upper threshold — a defensive filter that removes exposure during statistically extended rallies.

**Best result**: Sharpe 0.759 (B&H 0.745), CAGR 12.2%, max DD −33.9%

**Mutation surface**:

| Param | Default | Range to explore |
|---|---|---|
| `lookback` | 50 | 20–200 |
| `z_upper` | 2.0 | 1.0–3.0 |
| `hold_days` | 1 | 1–10 |

### VIXTermStructure (`signals/strategies/vix_term.py`) — v2

Isolates one condition from RiskOffComposite. Goes flat when VIX spot > VIX 3-Month (backwardation) AND VIX is above `vix_floor`.

**Best result**: Sharpe 0.672 (B&H 0.745), CAGR 8.4%, max DD −35.5%

**Mutation surface**:

| Param | Default | Range to explore |
|---|---|---|
| `vix_floor` | 20.0 | 12–25 |
| `hold_days` | 3 | 1–10 |

### MomentumCrossover (`signals/strategies/momentum_crossover.py`) — v1

Classic dual SMA trend-following signal. Long when fast SMA > slow SMA (uptrend confirmed), flat when bearish crossover. Very low trade frequency.

**Best result**: Sharpe 0.648 (B&H 0.745), CAGR 7.0%, max DD −22.9%

**Mutation surface**:

| Param | Default | Range to explore |
|---|---|---|
| `fast_period` | 20 | 5–50 |
| `slow_period` | 100 | 50–250 |
| `hold_days` | 1 | 1–10 |

### BTC SMA Trend (`signals/strategies/btc_sma_trend.py`) — v1

Screenshot-inspired Bitcoin long/flat trend filters. Long BTC when `BTC-USD`
closes above the moving average, flat when it closes below. These are not
short strategies.

**Initial exact-rule results** (`BTC-USD`, 2014-09-17 to 2026-05-09):

| Strategy | Rule | Sharpe | B&H Sharpe | CAGR | Max DD | Trades |
|---|---|---:|---:|---:|---:|---:|
| `Btc50DaySmaTrend` | Above 50-day SMA | 1.159 | 0.835 | 46.4% | -58.0% | 107 |
| `Btc200DaySmaTrend` | Above 200-day SMA | 0.944 | 0.835 | 36.8% | -70.0% | 37 |
| `Btc200WeekSmaTrend` | Above 200-week SMA | 0.468 | 0.835 | 11.2% | -78.2% | 7 |

**Current autoresearch winners** after 20 seeded mutations per BTC SMA family:

| Strategy | Best params | Sharpe | B&H Sharpe | CAGR | Max DD | Trades |
|---|---|---:|---:|---:|---:|---:|
| `Btc50DaySmaTrend` | `ma_period=44`, `hold_days=1` | 1.302 | 0.835 | 54.1% | -48.7% | 113 |
| `Btc200DaySmaTrend` | `ma_period=175`, `hold_days=1` | 1.074 | 0.835 | 44.1% | -63.8% | 36 |
| `Btc200WeekSmaTrend` | `ma_weeks=100`, `hold_days=1` | 0.814 | 0.835 | 30.7% | -81.8% | 6 |

Note: the 200-week rule requires roughly 200 weeks of BTC history before the
average exists, so the current harness leaves the strategy flat during the
initial warm-up period.

**Mutation surface**:

| Strategy | Param | Default | Range to explore |
|---|---|---:|---|
| `Btc50DaySmaTrend` | `ma_period` | 50 | 10–100 |
| `Btc200DaySmaTrend` | `ma_period` | 200 | 100–300 |
| `Btc200WeekSmaTrend` | `ma_weeks` | 200 | 100–300 |
| all BTC SMA variants | `hold_days` | 1 | 1–10 daily / 1–28 weekly |

Example commands:

```bash
python -m signals.run_eval --strategy Btc50DaySmaTrend
python -m signals.run_eval --strategy Btc200DaySmaTrend
python -m signals.run_eval --strategy Btc200WeekSmaTrend
python -m signals.autoresearch --strategy Btc50DaySmaTrend --mutations 20
```

### GoldCopperMomentum (`signals/strategies/gold_copper_momentum.py`) — v1

Cross-asset growth signal. Copper/gold ratio is a macro barometer — rising = growth improving, falling = growth deteriorating. Goes flat when ratio's N-day rate of change falls below threshold.

**Best result**: Sharpe 0.615 (B&H 0.745), CAGR 6.5%, max DD −25.0%

**Mutation surface**:

| Param | Default | Range to explore |
|---|---|---|
| `lookback` | 10 | 3–30 |
| `roc_threshold` | -0.03 | -0.01 to -0.10 |
| `hold_days` | 3 | 1–15 |
| `smooth_period` | 1 | 1–10 |

## Adding New Strategies

1. Create `signals/strategies/my_strategy.py`, subclassing `BaseStrategy`
2. Set `name`, `version`, `description`, `target_symbol`, `default_params`
3. Implement `required_symbols()` and `generate_signals(prices)`
4. Add to `STRATEGY_REGISTRY` in both `run_eval.py` and `autoresearch.py`
5. Add mutation ranges to `MUTATION_RANGES` in `autoresearch.py`
6. Run `python -m signals.run_eval --strategy MyStrategy --dry-run` to verify
7. Run `python -m signals.autoresearch --strategy MyStrategy` to sweep

## Autoresearch Loop (Agent Instructions)

1. **Read findings log**: `python -m signals.autoresearch --report`
2. **Run sweep**: `python -m signals.autoresearch --mutations 15`
3. **Identify winners**: look for ★ markers in output
4. **Commit winners**: update `default_params` in the strategy file, bump `version`
5. **Repeat**: use `--report` to identify underexplored param ranges

Principle: change one thing at a time so improvement is attributable.

## Available Historical Symbols (Key)

| Symbol | Description | Available From |
|---|---|---|
| `^GSPC` | S&P 500 | 1927 |
| `^VIX` | CBOE Volatility Index | 1990 |
| `^VIX3M` | VIX 3-Month | 2006 |
| `^VIX9D` | VIX 9-Day | 2011 |
| `^TNX` | 10-Year Treasury Yield | 1962 |
| `DX-Y.NYB` | US Dollar Index (DXY) | 1971 |
| `GC=F` | Gold | 2000 |
| `HG=F` | Copper | 2000 |
| `ES=F` | S&P 500 E-mini Futures | 2000 |
| `BTC-USD` | Bitcoin | 2014 |
| All forex pairs, sector ETFs, commodities | — | ~2000–2014 |

Full list: `python -c "import pandas as pd; df=pd.read_parquet('app/data/history/prices.parquet'); print(sorted(df.symbol.unique()))"`
