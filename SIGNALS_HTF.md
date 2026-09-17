# Higher-Timeframe Signals

Higher-timeframe autoresearch is the slower, robustness-first companion to the
daily signal harness.

## Commands

```bash
# Dry run
python -m signals.htf_autoresearch --dry-run --mutations 10

# Run and append to signals/findings.jsonl
python -m signals.htf_autoresearch --mutations 30

# Report higher-timeframe findings
python -m signals.htf_autoresearch --report

# Daily worker
python worker_htf.py

# Weekly worker
python worker_htf.py --interval 604800
```

## Current Strategies

### MonthlyTrendRegime

Classic monthly trend filter:

- Resamples S&P 500 closes to month-end.
- Computes a moving average over `ma_months`.
- Goes long when month-end close is above the moving average.
- Goes flat when monthly trend is down.
- Forward-fills the monthly regime across daily bars for backtesting.

`MonthlyTrendRegime` computes the rule on linear prices. `MonthlyLogTrendRegime`
uses the same rule on log prices, so the moving-average comparison is based on
percentage compounding rather than raw index points.

Mutation surface:

| Parameter | Default | Range |
|---|---:|---:|
| `ma_months` | 10 | 6-15 |
| `confirm_months` | 1 | 1-3 |
| `defensive_buffer` | 0.0 | -0.03 to 0.05 |
| `hold_months` | 1 | 1-4 |

Both monthly variants use the same mutation surface.

## Scoring

The HTF runner still records normal signal metrics, but ranks winners by a
composite objective:

```text
Sharpe
+ drawdown improvement vs buy-and-hold
+ CAGR improvement vs buy-and-hold
- turnover penalty
```

Each run also stores a 5-year rolling walk-forward check:

- mean rolling-window Sharpe
- rate of positive Sharpe windows
- rate of windows beating buy-and-hold Sharpe
- rate of windows improving buy-and-hold drawdown

The goal is to promote stable parameter regions rather than one-off full-period
Sharpe winners.
