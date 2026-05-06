"""FindingsLog — JSONL-based findings log for data quality optimization experiments.

Each entry records a configuration snapshot (batch sizes, timeouts, refresh
intervals) and the composite reliability scores observed under that config.
The autoresearch agent compares entries to find configurations that improve
overall reliability.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

FINDINGS_PATH = Path(__file__).resolve().parent / "findings.jsonl"


def append(result: dict) -> None:
    """Append an optimization experiment result to the findings log."""
    entry = {"timestamp": datetime.now(tz=timezone.utc).isoformat(), **result}
    with FINDINGS_PATH.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def read_all() -> list[dict]:
    """Return all findings sorted by timestamp descending."""
    if not FINDINGS_PATH.exists():
        return []
    findings = []
    with FINDINGS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return sorted(findings, key=lambda x: x.get("timestamp", ""), reverse=True)


def count() -> int:
    return len(read_all())
