"""Higher-timeframe autoresearch worker.

Run this separately from the hourly worker. Higher-timeframe strategies do not
benefit from hourly mutation against the same daily history, so the default
interval is daily.

Usage:
  python worker_htf.py
  python worker_htf.py --interval 604800  # weekly
  python worker_htf.py --once
"""
import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s worker_htf %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("worker_htf")

DEFAULT_INTERVAL = 86400
MUTATIONS_PER_SWEEP = 30


def sweep() -> None:
    log.info("=== HTF sweep start ===")
    start = time.monotonic()
    cmd = [
        sys.executable,
        "-m",
        "signals.htf_autoresearch",
        "--mutations",
        str(MUTATIONS_PER_SWEEP),
    ]
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        log.warning("HTF sweep exited with code %d", result.returncode)
    elapsed = time.monotonic() - start
    log.info("=== HTF sweep complete in %.1fs ===", elapsed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Higher-timeframe autoresearch worker")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Seconds between sweeps")
    parser.add_argument("--once", action="store_true", help="Run one sweep then exit")
    args = parser.parse_args()

    log.info("Worker started - interval %ds, mutations %d", args.interval, MUTATIONS_PER_SWEEP)
    while True:
        try:
            sweep()
        except Exception:
            log.exception("HTF sweep failed - will retry next interval")

        if args.once:
            break

        next_at = datetime.fromtimestamp(time.time() + args.interval).strftime("%H:%M:%S")
        log.info("Next HTF sweep at %s (sleeping %ds)", next_at, args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
