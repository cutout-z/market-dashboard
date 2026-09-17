# Data Quality — Autoresearch Layer 3

Source reliability telemetry and optimization harness. Instruments every `BaseSource.refresh()` cycle and scores sources on success rate, data completeness, and latency.

## Architecture

```
market-dashboard/
├── data_quality/
│   ├── collector.py       # Instruments refresh cycles → events.jsonl
│   ├── scorer.py          # Computes per-source reliability scores (0–100)
│   ├── findings.py        # Optimization experiment log
│   ├── run_eval.py        # CLI entry point
│   └── events.jsonl       # Raw telemetry (append-only, one line per refresh)
├── app/sources/base.py    # BaseSource.refresh() emits events via collector
└── DATA_QUALITY.md        # This file
```

## Running the Harness

```bash
cd market-dashboard

# Print current reliability scores
python -m data_quality.run_eval

# Scores since a specific date
python -m data_quality.run_eval --since 2026-04-29

# Event counts per source
python -m data_quality.run_eval --counts

# Snapshot current scores as a findings entry (for before/after comparison)
python -m data_quality.run_eval --snapshot --label "baseline"

# View optimization findings log
python -m data_quality.run_eval --summary
```

## Event Schema

Each line in `events.jsonl`:
```json
{
  "ts": "2026-04-29T10:00:00+00:00",
  "source": "indices",
  "ok": true,
  "ms": 2183.4,
  "data": true,
  "err": null
}
```

## Composite Score (0–100)

```
0.40 × success_rate  (did the fetch complete without exception?)
0.30 × data_rate     (did _has_real_data() return true?)
0.20 × latency_score (100 if P95 < 2s, linear decay to 0 at 30s)
0.10 × streak_score  (100 if no consecutive failures, -20 per streak length)
```

## Known Limitations

- **Historical data-rate telemetry**: events logged before 2026-05-06 may undercount non-price sources because the old validator only recognised price fields. New refresh events use the recursive structured-data validator.
- **Single-pass telemetry**: Events are only logged during live refresh cycles. To build a meaningful dataset, the dashboard needs to run for hours/days. Quick burst tests give latency data but not reliability trends.

## Mutation Surface

Parameters the autoresearch agent can experiment with:

| Parameter | Location | Current | Range |
|---|---|---|---|
| `_BATCH_SIZE` | `yahoo_quotes.py` | 20 | 5–30 |
| `_TIMEOUT` | `yahoo_quotes.py` | 15s | 5–30s |
| `refresh_interval` | each source class | varies (60s–3600s) | source-dependent |
| stagger delay | `main.py:_refresh_loop` | 2s | 0.5–5s |
| retry count | `BaseSource.refresh()` | 0 (no retries) | 0–3 |
| retry backoff | not implemented | — | 1–10s exponential |

## Autoresearch Loop (Agent Instructions)

1. **Read current scores**: `python -m data_quality.run_eval`
2. **Identify weakest source**: lowest composite score
3. **Propose mutation**: change one parameter (e.g., increase timeout for slow sources)
4. **Apply change**: edit the relevant source file
5. **Collect telemetry**: run dashboard or burst-test refresh cycles
6. **Snapshot**: `python -m data_quality.run_eval --snapshot --label "after_timeout_change"`
7. **Compare**: read findings log, compare mean_composite to baseline
8. **Commit winners**: if composite improved, commit the change

Priority optimizations:
- Add retry logic to `BaseSource.refresh()` for transient failures
- Tune refresh_interval per source based on actual data change frequency
- Add connection pooling / session reuse for FRED API calls
