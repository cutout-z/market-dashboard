# Verify recipe: market-dashboard

The end-to-end check for this repo: it runs the real app and inspects what a user sees.
Run it before you call any change done (code, template, source, config or dependency).
`python3 -m pytest -q tests` alone is offline and starts no source, so it cannot tell you
whether a page still shows data.

## Run it

From the root of a working clone or worktree (never the live checkout, never port 8060):

```bash
/opt/anaconda3/bin/python scripts/verify.py
```

Options: `--port N` (a free port in 9200-9249; default 9215), `--keep` (keep the temp dir with
the app log, the fetched cache and one screenshot per page), `--no-browser` (skip step 6; it is
reported as a warning, so the run does not prove what a user sees), `--timeout S` (wait for the
first fetches, default 300).

Takes about 2 minutes: about 45 s for the 21 sources' first fetches (they start 2 s apart),
about 40 s for the browser pass. Needs the network, the FRED key the app already reads, and
`requirements-dev.txt` plus `python -m playwright install chromium` (both already present
under `/opt/anaconda3` on the Mac).

The script refuses (exit 2) port 8060, ports 9250-9259, a port already in use, and a path
inside the live checkout. It exits 0 when every check passes, 1 when any fails, and prints a
`RESULT:` line with the pass, warn and fail counts.

## Steps and what each must show

| # | Step | Passes when |
|---|------|-------------|
| 1 | Offline tests: `pytest -q tests` | exit 0 (66 passed on 2026-11-23) |
| 2 | Start the app from this checkout on the review port, with the cache redirected to a fresh temp dir | `/api/sources` answers within 60 s. The empty cache means every source is fetched by this checkout's code; an old cache cannot hide a broken fetch |
| 3 | Sources (`/api/sources`, `/api/status`) | all 21 sources fetched within the timeout, and each has real data, except the tolerated empties below |
| 4 | Currency: the newest date inside the data, not the cache age | FRED yields at most 10 days old, CFTC COT at most 14, the newest news item at most 3. The committed price history behind `/analysis` is reported as a warning when over 7 days old |
| 5 | Routes: every page and every HTMX partial, enumerated from the app | each answers 200, and no partial shows an empty-state text ("Loading ... data...", "No data available", "No news available") or a server error |
| 6 | Browser: headless Chromium loads every page and waits for HTMX to settle | no console error, page error or failed request (HTTP 4xx/5xx); every Plotly chart holds data; each page meets its floor in `PAGE_FLOORS` (charts, svgs, table rows, text length, set at about half of a healthy run) |
| - | App log | no Python traceback. Upstream 4xx/5xx responses (rate limits, retired FRED series) are listed as a warning |

Then look at the result yourself: run with `--keep` and open the screenshots in the kept
`screenshots/` folder for the pages your change touches, or start the app
(`uvicorn app.main:app --host 127.0.0.1 --port 9215`) and open them in a browser. A layout
that is broken but still full of data passes every scripted check.

## Known warnings (2026-11-23)

These come up on a healthy run. A new one is a finding:

- `economic_calendar` empty with `HTTP 429`: ForexFactory rate-limits, and the live service
  polls it too. Only a 429 is tolerated; any other error fails.
- `earnings` empty: FMP answers the earnings calendar with HTTP 403 (the live cache last had
  data in 2026-05). Any empty earnings result is tolerated, so the recipe cannot catch a broken
  earnings change.
- Price history ends 2026-05-11: `app/data/history/` is committed data written by
  `etl/backfill.py`, not refreshed since.
- Upstream errors: several OECD series on FRED answer HTTP 400 (retired), and repeated runs hit
  FRED's HTTP 429, which thins the `/economy` charts. If FRED is rate-limiting, wait a few
  minutes and re-run.

## What it does not cover

- Visual layout, colours and overlap: only your own look at the screenshots catches those.
- Interactions: tab and period switches, the `/analysis` symbol picker, HTMX auto-refresh after
  the first load.
- Correctness of the numbers against their source (it checks that data exists and is recent).
- The public Render deployment and the live service on 8060; the background ETL (`etl/`,
  `worker*.py`) and the autoresearch layers (`signals/`, `news_classification/`, `data_quality/`).
- Sources tolerated as empty above.

When you add a page, give it a row in `PAGE_FLOORS` in `scripts/verify.py` (the run fails until
you do, and prints the counts to start from).
