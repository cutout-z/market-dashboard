"""Scorer — compute per-source reliability metrics from the event log.

Metrics (all over the requested time window):
    success_rate   — fraction of refreshes that didn't raise an exception
    data_rate      — fraction of successful refreshes that returned real data
    p50_ms         — median fetch latency in milliseconds
    p95_ms         — 95th percentile fetch latency
    error_streak   — longest consecutive run of failures (current or historical)
    total_events   — number of refresh cycles observed

Composite reliability score (0–100):
    0.40 * success_rate
  + 0.30 * data_rate
  + 0.20 * latency_score   (100 if p95 < 2s, linear decay to 0 at 30s)
  + 0.10 * streak_score    (100 if no streak > 1, decays with streak length)

Autoresearch mutation surface
-----------------------------
The weights and thresholds above are the tunable parameters.  The agent
can propose different weights and re-score to find a composite that better
predicts user-facing data quality.
"""
from __future__ import annotations

from dataclasses import dataclass

from .collector import read_events


@dataclass
class SourceScore:
    source: str
    success_rate: float
    data_rate: float
    p50_ms: float
    p95_ms: float
    error_streak: int
    total_events: int
    composite: float

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "success_rate": round(self.success_rate, 4),
            "data_rate": round(self.data_rate, 4),
            "p50_ms": round(self.p50_ms, 1),
            "p95_ms": round(self.p95_ms, 1),
            "error_streak": self.error_streak,
            "total_events": self.total_events,
            "composite": round(self.composite, 1),
        }


def _percentile(values: list[float], pct: float) -> float:
    """Simple percentile — avoids numpy dependency."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (k - f) * (s[c] - s[f])


def _max_consecutive_failures(events: list[dict]) -> int:
    """Longest run of consecutive failures in chronological order."""
    max_streak = 0
    current = 0
    for e in events:
        if not e.get("ok"):
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def score_source(
    source: str,
    since: str | None = None,
    *,
    w_success: float = 0.40,
    w_data: float = 0.30,
    w_latency: float = 0.20,
    w_streak: float = 0.10,
    latency_good_ms: float = 2000,
    latency_bad_ms: float = 30000,
) -> SourceScore | None:
    """Compute reliability score for a single source.

    Returns None if no events found for the source.
    """
    events = read_events(source=source, since=since)
    if not events:
        return None

    # Sort by timestamp for streak calculation
    events.sort(key=lambda e: e.get("ts", ""))

    n = len(events)
    successes = sum(1 for e in events if e.get("ok"))
    data_hits = sum(1 for e in events if e.get("ok") and e.get("data"))
    latencies = [e["ms"] for e in events if e.get("ok") and "ms" in e]

    success_rate = successes / n if n else 0
    data_rate = data_hits / successes if successes else 0
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    streak = _max_consecutive_failures(events)

    # Sub-scores (0–100 scale)
    latency_score = max(0, min(100, 100 * (1 - (p95 - latency_good_ms) / (latency_bad_ms - latency_good_ms))))
    streak_score = max(0, 100 - streak * 20)  # each failure in streak costs 20 pts

    composite = (
        w_success * success_rate * 100
        + w_data * data_rate * 100
        + w_latency * latency_score
        + w_streak * streak_score
    )

    return SourceScore(
        source=source,
        success_rate=success_rate,
        data_rate=data_rate,
        p50_ms=p50,
        p95_ms=p95,
        error_streak=streak,
        total_events=n,
        composite=composite,
    )


def score_all(since: str | None = None, **kwargs) -> list[SourceScore]:
    """Score all sources that have events in the log."""
    events = read_events(since=since)
    sources = sorted(set(e["source"] for e in events if "source" in e))
    scores = []
    for src in sources:
        s = score_source(src, since=since, **kwargs)
        if s:
            scores.append(s)
    return sorted(scores, key=lambda s: s.composite)


def summary(since: str | None = None) -> str:
    """Markdown-formatted reliability scoreboard."""
    scores = score_all(since=since)
    if not scores:
        return "No events collected yet. Start the dashboard to begin collecting telemetry."

    rows = [
        "| Source | Score | Success | Data | P50 | P95 | Streak | Events |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in scores:
        rows.append(
            f"| {s.source} "
            f"| {s.composite:.0f} "
            f"| {s.success_rate * 100:.0f}% "
            f"| {s.data_rate * 100:.0f}% "
            f"| {s.p50_ms:.0f}ms "
            f"| {s.p95_ms:.0f}ms "
            f"| {s.error_streak} "
            f"| {s.total_events} |"
        )
    return "\n".join(rows)
