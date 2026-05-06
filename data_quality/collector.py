"""Event collector — append-only JSONL log of every source refresh cycle.

Each event records: source key, success/failure, latency, whether the fetch
returned real data, and any error message.  The scorer reads this file to
compute per-source reliability metrics over arbitrary time windows.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("data_quality.collector")

EVENTS_PATH = Path(__file__).resolve().parent / "events.jsonl"


def log_event(
    source: str,
    success: bool,
    latency_ms: float,
    has_real_data: bool,
    error: str | None = None,
) -> None:
    """Append a single refresh event to the events log.

    Called from BaseSource.refresh() — must never raise, since a telemetry
    failure should not break a data refresh.
    """
    try:
        entry = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "source": source,
            "ok": success,
            "ms": round(latency_ms, 1),
            "data": has_real_data,
            "err": error,
        }
        with EVENTS_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        logger.debug("Failed to write data quality event", exc_info=True)


def read_events(
    source: str | None = None,
    since: str | None = None,
) -> list[dict]:
    """Read events, optionally filtered by source and/or start timestamp.

    Parameters
    ----------
    source : filter to a single source key (e.g. "indices")
    since  : ISO timestamp — only return events after this time
    """
    if not EVENTS_PATH.exists():
        return []
    events = []
    with EVENTS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if source and e.get("source") != source:
                continue
            if since and e.get("ts", "") < since:
                continue
            events.append(e)
    return events


def event_count() -> int:
    """Total number of events in the log."""
    if not EVENTS_PATH.exists():
        return 0
    with EVENTS_PATH.open() as f:
        return sum(1 for line in f if line.strip())
