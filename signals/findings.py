"""FindingsLog — JSONL-based findings log for tracking autoresearch iterations."""
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


def best_by_strategy() -> dict[str, dict]:
    """Return the highest-Sharpe result for each strategy name."""
    best: dict[str, dict] = {}
    for entry in read_all():
        name = entry.get("metadata", {}).get("strategy", "unknown")
        current_sharpe = entry.get("sharpe", float("-inf"))
        if name not in best or current_sharpe > best[name].get("sharpe", float("-inf")):
            best[name] = entry
    return best


def summary() -> str:
    """Return a markdown-formatted leaderboard of best results per strategy."""
    bests = best_by_strategy()
    if not bests:
        return "No findings yet. Run `python -m signals.run_eval` to populate."

    rows = [
        "| Strategy | Sharpe | B&H Sharpe | CAGR | Hit Rate | Max DD | Trades | Period |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, e in sorted(bests.items(), key=lambda x: x[1].get("sharpe", 0), reverse=True):
        p = e.get("eval_period", {})
        rows.append(
            f"| {name} "
            f"| {e.get('sharpe', float('nan')):.3f} "
            f"| {e.get('bh_sharpe', float('nan')):.3f} "
            f"| {e.get('cagr', 0) * 100:.1f}% "
            f"| {e.get('hit_rate', 0) * 100:.1f}% "
            f"| {e.get('max_drawdown', 0) * 100:.1f}% "
            f"| {e.get('trade_count', '?')} "
            f"| {p.get('start', '')}→{p.get('end', '')} |"
        )
    return "\n".join(rows)


def count() -> int:
    """Return total number of evaluation entries in the log."""
    return len(read_all())
