"""Data quality evaluation CLI — score source reliability and log optimization experiments.

Usage
-----
# Print current reliability scores for all sources
python -m data_quality.run_eval

# Score with a time window (ISO timestamp)
python -m data_quality.run_eval --since 2026-04-29

# Show event counts per source
python -m data_quality.run_eval --counts

# Print optimization findings log
python -m data_quality.run_eval --summary

# Snapshot current scores as a findings entry (for before/after comparison)
python -m data_quality.run_eval --snapshot --label "baseline"

Autoresearch agent notes
------------------------
- events.jsonl is the raw telemetry — one line per refresh cycle
- Composite score weights are tunable: w_success, w_data, w_latency, w_streak
- Mutation surface: batch_size, timeout, refresh_interval, stagger_delay, retry_count
- Run dashboard for N minutes, then score, then compare to findings baseline
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_quality import collector, findings, scorer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Data quality evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--since", metavar="ISO_DATE",
                        help="Only consider events after this timestamp")
    parser.add_argument("--counts", action="store_true",
                        help="Print event counts per source and exit")
    parser.add_argument("--summary", action="store_true",
                        help="Print optimization findings log and exit")
    parser.add_argument("--snapshot", action="store_true",
                        help="Save current scores as a findings entry")
    parser.add_argument("--label", default="",
                        help="Label for --snapshot entry")
    args = parser.parse_args()

    if args.counts:
        events = collector.read_events(since=args.since)
        counts = Counter(e.get("source", "?") for e in events)
        for src, n in counts.most_common():
            print(f"  {src:30s} {n:5d} events")
        print(f"\n  Total: {len(events)} events")
        return

    if args.summary:
        all_findings = findings.read_all()
        if not all_findings:
            print("No findings yet. Run --snapshot to create baseline.")
            return
        for f in all_findings:
            print(json.dumps(f, indent=2, default=str))
            print()
        print(f"Total entries: {findings.count()}")
        return

    # Default: print reliability scoreboard
    print(scorer.summary(since=args.since))
    print(f"\nTotal events in log: {collector.event_count()}")

    if args.snapshot:
        scores = scorer.score_all(since=args.since)
        if not scores:
            print("\nNo events to snapshot.")
            return
        entry = {
            "label": args.label or "snapshot",
            "event_window_since": args.since,
            "scores": [s.to_dict() for s in scores],
            "mean_composite": round(
                sum(s.composite for s in scores) / len(scores), 1
            ),
            "weakest_source": scores[0].source if scores else None,
            "weakest_composite": scores[0].composite if scores else None,
        }
        findings.append(entry)
        print(f"\n→ Snapshot saved to findings log ({findings.count()} total entries)")


if __name__ == "__main__":
    main()
