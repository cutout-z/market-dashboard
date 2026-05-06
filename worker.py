"""Autoresearch worker — runs all 3 layers on an hourly loop.

Layers:
  1. signals/          — signal strategy param optimisation (Sharpe vs backtest)
  2. news_classification/ — news classifier param optimisation (accuracy vs labeled set)
  3. data_quality/     — data source reliability snapshot

Each sweep runs all three layers sequentially, then sleeps for INTERVAL seconds.
Results are written to the respective findings.jsonl files in the project directory.

Usage:
  python worker.py                  # default 1h interval
  python worker.py --interval 1800  # 30min interval
  python worker.py --once           # single sweep then exit (useful for testing)
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s worker %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("worker")

DEFAULT_INTERVAL = 3600  # 1 hour
MUTATIONS_PER_SWEEP = 20  # mutations per strategy per sweep


def run_layer(label: str, module_args: list[str]) -> bool:
    """Run a Python module as a subprocess. Returns True on success."""
    cmd = [sys.executable, *module_args]
    log.info("  starting %s", label)
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        log.warning("  %s exited with code %d", label, result.returncode)
        return False
    log.info("  %s done", label)
    return True


def sweep() -> None:
    log.info("=== sweep start ===")
    start = time.monotonic()

    run_layer(
        "signals autoresearch",
        ["-m", "signals.autoresearch", "--mutations", str(MUTATIONS_PER_SWEEP)],
    )
    run_layer(
        "news_classification autoresearch",
        ["-m", "news_classification.autoresearch", "--mutations", str(MUTATIONS_PER_SWEEP)],
    )
    run_layer(
        "data_quality snapshot",
        ["-m", "data_quality.run_eval", "--snapshot", "--label", "worker"],
    )

    elapsed = time.monotonic() - start
    log.info("=== sweep complete in %.1fs ===", elapsed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Autoresearch hourly worker")
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL, metavar="SECONDS",
        help=f"Seconds between sweeps (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single sweep then exit",
    )
    args = parser.parse_args()

    log.info("Worker started — interval %ds, mutations %d per strategy",
             args.interval, MUTATIONS_PER_SWEEP)

    while True:
        try:
            sweep()
        except Exception:
            log.exception("Sweep failed — will retry next interval")

        if args.once:
            break

        next_at = datetime.fromtimestamp(time.time() + args.interval).strftime("%H:%M:%S")
        log.info("Next sweep at %s (sleeping %ds)", next_at, args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
