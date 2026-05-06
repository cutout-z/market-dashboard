"""FindingsLog — JSONL-based findings log for news classification autoresearch."""
import json
from datetime import datetime, timezone
from pathlib import Path

FINDINGS_PATH = Path(__file__).resolve().parent / "findings.jsonl"


def append(result: dict) -> None:
    """Append an evaluation result to the findings log."""
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


def best_by_classifier() -> dict[str, dict]:
    """Return the highest-accuracy result for each classifier name."""
    best: dict[str, dict] = {}
    for entry in read_all():
        name = entry.get("metadata", {}).get("classifier", "unknown")
        current_acc = entry.get("accuracy", 0.0)
        if name not in best or current_acc > best[name].get("accuracy", 0.0):
            best[name] = entry
    return best


def summary() -> str:
    """Return a markdown-formatted leaderboard of best results per classifier."""
    bests = best_by_classifier()
    if not bests:
        return "No findings yet. Run `python -m news_classification.run_eval` to populate."

    rows = [
        "| Classifier | Accuracy | W-F1 | Labeled | Correct | Errors |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, e in sorted(bests.items(), key=lambda x: x[1].get("accuracy", 0), reverse=True):
        rows.append(
            f"| {name} "
            f"| {e.get('accuracy', 0) * 100:.1f}% "
            f"| {e.get('weighted_f1', 0) * 100:.1f}% "
            f"| {e.get('total', '?')} "
            f"| {e.get('correct', '?')} "
            f"| {e.get('errors', '?')} |"
        )
    return "\n".join(rows)


def count() -> int:
    """Return total number of evaluation entries in the log."""
    return len(read_all())
