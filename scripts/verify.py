#!/usr/bin/env python3
"""End-to-end verify: run the real app on a review port and inspect what a user sees.

Steps (docs/verify.md explains each one and its expected result):
  1. offline tests     python -m pytest -q tests
  2. start the app     uvicorn on a review port, with a fresh empty cache in a temp dir,
                       so every source is fetched live by this checkout's code
  3. sources           every source has real data (/api/sources, /api/status)
  4. currency          the newest FRED yield, COT report and news item are recent
  5. routes            every page and HTMX partial answers 200 with no empty-state text
  6. browser           headless Chromium loads every page: no console errors, no failed
                       requests, every Plotly chart holds data, a screenshot per page

Exit 0 when every check passes, 1 when any fails, 2 on a usage error.
Run from the repo root of a working clone or worktree, never the live checkout:
    /opt/anaconda3/bin/python scripts/verify.py [--port 9215] [--no-browser]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIVE_PORT = 8060
REVIEW_PORTS = range(9200, 9250)  # the review band (AGENTS.md Facts); 9250-9259 stay reserved

# Sources allowed to come back empty, each with the reason it is known to and the
# condition under which it is tolerated. Anything else empty is a failure.
KNOWN_EMPTY = {
    # FMP answered the earnings calendar with HTTP 403 on 2026-11-23 and the source
    # then returns an empty list with no error; the live cache last had data in 2026-05.
    # Only that error-free empty is tolerated ("No FMP API key" fails), so a broken
    # earnings change still passes: docs/verify.md lists it under what is not covered.
    "earnings": ("FMP earnings calendar empty, no error (FMP answered HTTP 403 on 2026-11-23)",
                 lambda cache: not cache.get("error")),
    # ForexFactory rate-limits; the live service polls it too, so a second instance
    # often gets HTTP 429. Only a 429 is tolerated: any other error fails.
    "economic_calendar": ("ForexFactory rate limit (HTTP 429)",
                          lambda cache: str(cache.get("error", "")).startswith("HTTP 429")),
}
# Empty-state text a partial renders when its source has nothing; keyed by the
# source whose emptiness is tolerated above, so its own placeholder is allowed.
EMPTY_STATE = {
    "Loading volatility skew...": None,
    "Loading Fed rate data...": None,
    "No data available": None,
    "Loading rotation data...": None,
    "Loading correlation data...": None,
    "Loading COT positioning data...": None,
    "No news available": None,
    "Loading heatmap data...": None,
    "Loading VIX term structure...": None,
    "Loading earnings calendar...": "earnings",
    "Loading historical data...": None,
    "No prediction market data": None,
    ">No data<": None,
    "No yield data available": None,
    "CHAT holdings data unavailable.": None,
    "No calendar events": "economic_calendar",
    "Internal Server Error": None,
    "Traceback": None,
}
# Empty-state texts a healthy main shows today, with how many times each may appear.
# More than that fails. Each is a live defect, not a design choice; remove the entry
# when it is fixed.
KNOWN_GAPS = {
    # /bonds UK Gilt curve: every UK yield from intl_bonds is null (live too, 2026-11-23).
    "No yield data available": 1,
}
# Value fields a quote source fills with a number; a fetch that fails still echoes the
# configured names and symbols with these as null, which has_data counts as data.
VALUE_KEYS = ("price", "value")
MIN_VALUE_SHARE = 0.5  # at least half of them must be numbers, per source
# Currency: (source, how to find its newest date, max age in days).
MAX_AGE_DAYS = {"fred_yields": 10, "cot": 14, "news_alerts": 3}
# What each page must show at least, in the browser after HTMX settles:
# (Plotly charts, svgs in <main>, table rows in <main>, characters of text in <main>).
# Set to about half of a healthy run's counts (2026-11-23), so a panel that renders
# nothing fails while day-to-day variation passes; /economy's chart count swings with
# FRED rate limits, hence a floor of 1. A new page needs a row here.
PAGE_FLOORS: dict[str, tuple[int, int, int, int]] = {
    "/":            (0, 18, 21, 1600),
    "/indices":     (0, 18, 21, 1600),
    "/analysis":    (4, 6, 0, 900),
    "/bonds":       (3, 6, 21, 1200),
    "/commodities": (0, 17, 23, 2100),
    "/economy":     (1, 1, 5, 1300),
    "/forex":       (0, 0, 21, 1400),
    "/futures":     (0, 8, 10, 700),
    "/health":      (0, 0, 11, 600),
    "/mag7":        (2, 6, 22, 2100),
    "/movers":      (0, 0, 16, 800),
    "/news":        (0, 0, 0, 2000),
    "/positioning": (0, 0, 8, 700),
    "/pulse":       (1, 3, 9, 1400),
    "/shocks":      (0, 0, 8, 1800),
    "/signals":     (0, 0, 28, 2300),
}
# The committed price history behind /analysis (etl/backfill.py writes it). Reported,
# not failed: it was already 6 months old when this recipe was written.
HISTORY_META = REPO / "app" / "data" / "history" / "metadata.json"
HISTORY_MAX_AGE_DAYS = 7
# Partials that need a query parameter to run their handler.
PARTIAL_QUERY = {"/partials/commodity-research": "?symbol=GC=F"}

results: list[tuple[str, str, str]] = []  # (status, check, detail)


def record(ok: bool | None, check: str, detail: str = "") -> None:
    status = "PASS" if ok else ("WARN" if ok is None else "FAIL")
    results.append((status, check, detail))
    print(f"  {status}  {check}" + (f": {detail}" if detail else ""), flush=True)


def get(url: str, timeout: float = 30) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


LAUNCHER = """
import sys
from pathlib import Path
cache = Path(sys.argv[1])
import app.sources.base as base
base.CACHE_DIR = cache
import data_quality.collector as collector
collector.EVENTS_PATH = cache / "events.jsonl"
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="info")
"""


def step_tests() -> None:
    print("1. offline tests", flush=True)
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=REPO,
                       capture_output=True, text=True)
    tail = [l for l in p.stdout.strip().splitlines() if l.strip()][-1:] or ["(no output)"]
    record(p.returncode == 0, "pytest -q tests", tail[0])


def start_app(port: int, workdir: Path) -> subprocess.Popen:
    print(f"2. start the app on 127.0.0.1:{port} (fresh cache {workdir / 'cache'})", flush=True)
    (workdir / "cache").mkdir()
    log = open(workdir / "app.log", "w")
    # Own process group, so stop_app takes uvicorn and anything it spawned with it.
    return subprocess.Popen([sys.executable, "-c", LAUNCHER, str(workdir / "cache"), str(port)],
                            cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)


def wait_ready(proc: subprocess.Popen, port: int, workdir: Path) -> bool:
    for _ in range(60):
        if proc.poll() is not None:
            break
        try:
            if get(f"http://127.0.0.1:{port}/api/sources", timeout=2)[0] == 200:
                record(True, "app answers", f"pid {proc.pid}")
                return True
        except OSError:
            pass
        time.sleep(1)
    record(False, "app answers", f"no answer in 60s; see {workdir / 'app.log'}")
    return False


def stop_app(proc: subprocess.Popen) -> None:
    """Stop the app on every exit path: a leftover instance keeps polling every upstream."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=15)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


def live_checkout() -> Path | None:
    """The working directory of whatever listens on the live port, if anything does."""
    try:
        pids = subprocess.run(["lsof", "-nP", f"-iTCP:{LIVE_PORT}", "-sTCP:LISTEN", "-t"],
                              capture_output=True, text=True, timeout=10).stdout.split()
        for pid in pids:
            out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                                 capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                if line.startswith("n"):
                    return Path(line[1:]).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def step_sources(base: str, timeout: int) -> dict:
    print(f"3. sources (waiting up to {timeout}s for every source's first fetch)", flush=True)
    t0 = time.time()
    while True:
        sources = json.loads(get(f"{base}/api/sources")[1])
        pending = [k for k, v in sources.items() if v["cache_age_seconds"] is None]
        if not pending or time.time() - t0 > timeout:
            break
        time.sleep(3)
    record(not pending, "every source fetched",
           f"{len(sources) - len(pending)}/{len(sources)} in {time.time() - t0:.0f}s"
           + (f"; never fetched: {', '.join(pending)}" if pending else ""))
    status = json.loads(get(f"{base}/api/status")[1])
    empty_ok = set()
    for name, info in sources.items():
        if name in pending:
            continue
        if info["has_data"]:
            continue
        cache = status.get(name) or {}
        known = KNOWN_EMPTY.get(name)
        if known and known[1](cache):
            empty_ok.add(name)
            record(None, f"source {name} empty (tolerated)", known[0])
        else:
            record(False, f"source {name} has no data", str(cache.get("error") or cache)[:200])
    with_data = sum(1 for v in sources.values() if v["has_data"])
    record(with_data + len(empty_ok) == len(sources), "sources with real data",
           f"{with_data}/{len(sources)}, {len(empty_ok)} tolerated empty")
    thin, checked = [], 0
    for name, cache in status.items():
        filled, total = _value_counts(cache)
        if total:
            checked += 1
            if filled < total * MIN_VALUE_SHARE:
                thin.append(f"{name} {filled}/{total}")
    record(not thin, "quote values are numbers",
           f"{checked} sources with price/value fields, each at least {MIN_VALUE_SHARE:.0%} filled"
           + (f"; mostly null: {', '.join(thin)}" if thin else ""))
    return {"status": status, "empty_ok": empty_ok}


def _value_counts(node) -> tuple[int, int]:
    """(numeric, total) over every price/value field anywhere in a source's cache."""
    filled = total = 0
    if isinstance(node, dict):
        for key, val in node.items():
            if key in VALUE_KEYS:
                total += 1
                filled += isinstance(val, (int, float)) and not isinstance(val, bool)
            f, t = _value_counts(val)
            filled, total = filled + f, total + t
    elif isinstance(node, list):
        for item in node:
            f, t = _value_counts(item)
            filled, total = filled + f, total + t
    return filled, total


def _newest(name: str, cache: dict) -> datetime | None:
    if name == "news_alerts":
        stamps = []
        for item in cache.get("items", []):
            try:
                stamps.append(parsedate_to_datetime(item["timestamp"]))
            except (KeyError, TypeError, ValueError):
                pass
        return max(stamps) if stamps else None
    if name == "fred_yields":
        # The stalest of the Treasury series, so one fresh series can't hide the rest.
        dates = [y.get("date") for y in cache.get("yields", [])]
        if not dates or not all(dates):
            return None
        return datetime.fromisoformat(min(dates)).replace(tzinfo=timezone.utc)
    dates = re.findall(r'"(20\d\d-\d\d-\d\d)', json.dumps(cache))
    today = datetime.now(timezone.utc).date().isoformat()
    past = [d for d in dates if d <= today]
    return datetime.fromisoformat(max(past)).replace(tzinfo=timezone.utc) if past else None


def step_currency(status: dict) -> None:
    print("4. currency (newest observation in the data, not the cache age)", flush=True)
    now = datetime.now(timezone.utc)
    for name, max_days in MAX_AGE_DAYS.items():
        newest = _newest(name, status.get(name) or {})
        if newest is None:
            record(False, f"{name} newest date", "no dated observation found")
            continue
        age = (now - newest).total_seconds() / 86400
        record(age <= max_days, f"{name} newest date",
               f"{newest.date()} ({age:.1f} days old, limit {max_days})")
    try:
        end = json.loads(HISTORY_META.read_text())["date_range"]["end"]
        age = (now.date() - datetime.fromisoformat(end).date()).days
        record(True if age <= HISTORY_MAX_AGE_DAYS else None, "price history (/analysis) ends",
               f"{end} ({age} days old; warn over {HISTORY_MAX_AGE_DAYS}; refreshed by etl/backfill.py)")
    except (OSError, KeyError, ValueError) as e:
        record(False, "price history metadata readable", str(e))


def _routes() -> tuple[list[str], list[str]]:
    sys.path.insert(0, str(REPO))
    from fastapi.routing import APIRoute
    from app.main import app
    paths = sorted(r.path for r in app.routes if isinstance(r, APIRoute) and "GET" in r.methods)
    pages = [p for p in paths if not p.startswith(("/api", "/partials"))]
    partials = [p + PARTIAL_QUERY.get(p, "") for p in paths if p.startswith("/partials")]
    return pages, partials


def _empty_text_in(body: str, empty_ok: set) -> list[str]:
    return [t for t, src in EMPTY_STATE.items()
            if body.count(t) > KNOWN_GAPS.get(t, 0) and src not in empty_ok]


def step_routes(base: str, empty_ok: set) -> list[str]:
    pages, partials = _routes()
    print(f"5. routes ({len(pages)} pages, {len(partials)} partials)", flush=True)
    bad = []
    for path in pages + partials:
        code, body = get(base + path)
        found = _empty_text_in(body, empty_ok) if path.startswith("/partials") else []
        if code != 200 or found:
            bad.append(f"{path} -> {code}" + (f" shows {found}" if found else ""))
    record(not bad, "every page and partial renders with data",
           f"{len(pages) + len(partials) - len(bad)}/{len(pages) + len(partials)} ok"
           + ("; " + "; ".join(bad) if bad else ""))
    return pages


BROWSER_PROBE = """() => {
  const plots = [...document.querySelectorAll('.js-plotly-plot')];
  // A trace holds data when its value axis has a non-null entry: y (or z, values, r)
  // when it has one, else x (histograms); dates on x with all-null y count as empty.
  const filled = a => a != null && Array.prototype.some.call(a, v => v !== null && v !== undefined && v !== '');
  const traceHasData = t => {
    for (const k of ['y', 'z', 'values', 'r', 'lat']) if (t[k] != null) return filled(t[k]);
    return filled(t.x);
  };
  const emptyPlots = plots.filter(p => !(p.data || []).some(traceHasData));
  return {plots: plots.length, emptyPlots: emptyPlots.length,
          svgs: document.querySelectorAll('main svg').length,
          rows: document.querySelectorAll('main tr').length,
          chars: document.querySelector('main') ? document.querySelector('main').innerText.length : 0,
          text: document.querySelector('main') ? document.querySelector('main').innerText : ''};
}"""


def step_browser(base: str, pages: list[str], empty_ok: set, shots: Path) -> None:
    print(f"6. browser (headless Chromium, {len(pages)} pages, screenshots in {shots})", flush=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record(False, "playwright importable",
               "pip install -r requirements-dev.txt && python -m playwright install chromium")
        return
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in pages:
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            errors: list[str] = []
            page.on("console", lambda m: errors.append(f"console: {m.text[:150]}")
                    if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:150]}"))
            page.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}")
                    if r.status >= 400 else None)
            page.on("requestfailed", lambda r: errors.append(f"failed {r.url}"))
            try:
                page.goto(base + path, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(1500)  # let HTMX swaps and Plotly draws finish
                probe = page.evaluate(BROWSER_PROBE)
                shot = (path.strip("/").replace("/", "_") or "root") + ".png"
                page.screenshot(path=str(shots / shot), full_page=True)
            except Exception as e:  # a page that never settles is a failure, not a crash
                record(False, f"browser {path}", f"load failed: {str(e)[:200]}")
                page.close()
                continue
            found = _empty_text_in(probe["text"], empty_ok)
            problems = errors + ([f"{probe['emptyPlots']}/{probe['plots']} Plotly charts empty"]
                                 if probe["emptyPlots"] else []) + \
                       ([f"shows {found}"] if found else [])
            floor = PAGE_FLOORS.get(path)
            if floor is None:
                problems.append("no floor in PAGE_FLOORS: add one from this run's counts")
            else:
                for key, low in zip(("plots", "svgs", "rows", "chars"), floor):
                    if probe[key] < low:
                        problems.append(f"{key} {probe[key]} < floor {low}")
            record(not problems, f"browser {path}",
                   f"{probe['plots']} charts, {probe['svgs']} svgs, {probe['rows']} rows, "
                   f"{probe['chars']} chars"
                   + ("; " + "; ".join(problems[:5]) if problems else ""))
            page.close()
        browser.close()


def finish(workdir: Path) -> int:
    log = (workdir / "app.log").read_text() if (workdir / "app.log").exists() else ""
    tracebacks = log.count("Traceback")
    if log:
        record(tracebacks == 0, "app log has no tracebacks",
               f"{tracebacks} tracebacks, {log.count(' WARNING ')} warnings; log {workdir / 'app.log'}")
        upstream = re.findall(r'HTTP Request: GET https?://([^/?]+)[^"]*"HTTP/[\d.]+ (4\d\d|5\d\d)', log)
        if upstream:
            counts: dict[str, int] = {}
            for host, code in upstream:
                counts[f"{host} {code}"] = counts.get(f"{host} {code}", 0) + 1
            record(None, "upstream errors (rate limits, retired series)",
                   ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())))
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    passes = len(results) - len(fails) - len(warns)
    print(f"\nRESULT: {'FAIL' if fails else 'PASS'}  {passes} passed, {len(warns)} warned, "
          f"{len(fails)} failed")
    for status, check, detail in fails:
        print(f"  FAIL {check}: {detail}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=9215, help="review port, 9200-9249 (default 9215)")
    ap.add_argument("--timeout", type=int, default=300,
                    help="seconds to wait for every source's first fetch (default 300)")
    ap.add_argument("--no-browser", action="store_true", help="skip step 6 (reported as a warning)")
    ap.add_argument("--keep", action="store_true", help="keep the temp dir (log, cache, screenshots)")
    args = ap.parse_args()

    if args.port not in REVIEW_PORTS:
        print(f"refused: port {args.port} is outside the review band; use 9200-9249")
        return 2
    live = live_checkout()
    if live is None:
        print(f"note: nothing listens on {LIVE_PORT}, so the live-checkout guard had nothing to compare")
    elif live == REPO:
        print(f"refused: {REPO} is the checkout the live service on {LIVE_PORT} runs from; "
              "run from a working clone or worktree")
        return 2
    if not port_free(args.port):
        print(f"refused: port {args.port} is in use; pick another in 9200-9249 with --port")
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="market-dashboard-verify-"))
    print(f"verify {REPO} (HEAD {subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()}), work dir {workdir}\n")
    step_tests()
    base = f"http://127.0.0.1:{args.port}"
    proc = start_app(args.port, workdir)
    try:
        if wait_ready(proc, args.port, workdir):
            state = step_sources(base, args.timeout)
            step_currency(state["status"])
            pages = step_routes(base, state["empty_ok"])
            if args.no_browser:
                record(None, "browser check skipped", "--no-browser: nothing checked what a user sees")
            else:
                step_browser(base, pages, state["empty_ok"], workdir / "screenshots")
    except Exception as e:  # a crash mid-run is a failed check, reported through finish()
        record(False, "recipe ran to the end", f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        stop_app(proc)
    code = finish(workdir)
    if not args.keep and code == 0:
        shutil.rmtree(workdir, ignore_errors=True)
        print("(temp dir removed; pass --keep to keep the log and screenshots)")
    else:
        print(f"kept {workdir} (app.log, cache/, screenshots/)")
    return code


if __name__ == "__main__":
    sys.exit(main())
