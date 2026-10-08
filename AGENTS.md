# Design-pass contract — market-dashboard

**Applies to every agent session in this repo** (Claude Code, Hermes, Codex, or a human).
Read it before changing anything. Read the Facts block at the bottom for this repo's specifics.

<!-- BEGIN agent-contracts:family -->
<!-- source: family/AGENTS.family.md sha256:116b1391e2bb — edit in cutout-z/agent-contracts, not here -->
## Family conventions (every repo, every agent)

*Generated from `agent-contracts/family/AGENTS.family.md`. Edit it there, never here: a drift check
reports any local edit.* These apply to every agent (Hermes, Claude Code, Codex or any other),
whatever app drives it. Where this repo's own rules (above or below this block) are stricter, they
win. Machine-specific conventions (which checkout is which, the lane runtime, where memory lives)
are in the owner's private contract, which reaches agents through their user-level instructions
where a harness supports it.

### Branches, concurrency, cleanup

- Work in a working clone, on a branch, never in a live or serving checkout: a live checkout is what
  serves or publishes, so an edit there goes out unreviewed. Merge to `main` only if this repo's
  contract says the agent may; otherwise push the branch and hand back for review.
- Other agents may be working in this repo right now. Fetch before you act. If a branch moved
  unexpectedly, or files you didn't touch changed, stop and report rather than reconcile.
- Use a worktree for parallel work, not a second clone. The exception is a live checkout: use a
  separate clone, because adding a worktree writes into the live checkout's `.git`. At session end,
  remove the worktrees you created and leave each checkout on the branch it was on when you arrived:
  a leftover worktree pins its branch, and a checkout left on your branch changes what the next
  agent, or a server running from it, sees.
- Push every branch you want kept. An unpushed branch is one disk failure from gone.

### Instructions and automation

- **`AGENTS.md` is the only instruction file.** `CLAUDE.md`, or any other harness-specific file, holds
  just a comment line and `@AGENTS.md`. Other harnesses never read those files, so a rule or fact put
  there reaches only one agent.
- **Nothing you depend on lives only in one harness or app.** Hooks, slash commands, plugins, app
  quick actions and app-scheduled tasks may speed things up. The only copy of any automation or rule
  goes in this repo (scripts, `AGENTS.md`) or the owner's scheduler, because the harness or app may be
  swapped.
- **Name the tier, not the model.** Briefs, skills and procedures say a tier and an effort (tier 0
  mechanical, 1 routine, 2 standard, 3 hard or review, 4 vision); `agent-contracts/tiers.yaml` maps
  each tier to a model per harness. Models change often, so a name in a skill goes stale.
- **A fact other agents need goes where they load it**: this repo's `AGENTS.md` Facts, with source
  and date. If it applies across repos, propose it for the shared facts block in your handback. Your
  own memory or skills are invisible to the other agents.

### What needs the owner's yes

An explicit instruction from the owner in the current session covers that action only, not similar
later ones: the yes was for what the owner saw, not for what follows. A repo contract may record a
standing permission from the owner (e.g. "the agent merges to `main` once `check.sh` is green"). It
counts as the owner's yes only for the actions and the agents it names, only in the repo whose
contract records it, and only as that text stands on `origin/main` when you start. It never covers
adding, widening or rewording a standing permission, or any change to `AGENTS.md` or this block:
those always need the owner's yes in the current session. Without either, declare these and wait
for a yes:

- **Publishing**: anything that changes what other people can see (`main` on a published repo,
  Pages, public data files).
- **Data and ETL**: data files, pipeline code, data contracts (columns, keys, paths, schemas).
  Lanes, dashboards and other repos read them, and a change breaks them silently.
- **The instruments**: `check.sh`, guard tests, audit and verify scripts. They are how anyone,
  including you, knows a change works. Never weaken one to make something pass. If one is wrong,
  say so and leave it.
- **Infra**: ports, scheduled jobs, servers, publish pipelines. Other jobs, and the owner, rely on
  them running as they are.
- **Another agent's state**: another agent's memory, config or notes. With the owner's yes any agent
  may change them; no agent is the only writer. The owning agent can't see your edit, so commit it
  where it's visible, and edit the source rather than a generated copy.

Never read, quote or commit secrets (`.env`, auth files, keys, tokens): repos, transcripts and
handback notes get copied and published.

### Verification standard

- A change is done when you have seen the evidence yourself: tests run (exact counts, failures
  named, pre-existing failures shown to exist on `main`), and for UI, a real browser render, or a
  plain statement that it wasn't rendered and why. A reviewer can check evidence, not belief.
- For a fix, show its test fails with the fix reverted and passes with it applied; otherwise nothing
  shows the test exercises the fix.
- Don't relay another agent's or subagent's numbers. Re-run or read the evidence yourself: a relayed
  number can't be traced, and you are the one signing the handback.

### Attribution and handback

- **Every commit names its agent** in a trailer, so audits and the owner's digest can tell which agent
  made each change, whatever app drove it: `Co-Authored-By: <Agent> <model> <email>`, e.g.
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. `<Agent>` is one word (`Claude`,
  `Codex`, `Hermes`, …); `<model>` is the model name without a provider prefix (e.g. `Opus 5.5`,
  `deepseek-v4.1-flash`). The email goes in angle brackets: Claude `noreply@anthropic.com`, Hermes
  `noreply@nousresearch.com` (as in existing commits), any other agent `<agent>@agents.invalid`.
  Audits match the key case-insensitively and the first word of the value.
- **Commit with the repo's configured identity.** Never set or override `user.name` or `user.email`,
  and never pass `--author`: on a public repo, author fields are published.
- **End every piece of work with a handback note.** It is the durable record; app session lists and
  an agent's memory are not, and both may be swapped. Use the repo's own path and branch convention
  if it has one; it wins, including whether notes merge. Otherwise use
  `handbacks/<YYYY-MM-DD>-<topic>.md`. On a repo whose `main` is published (a public repo, or one that
  deploys or builds a site from `main`), commit the note on its own branch, `handback/<your-branch>`:
  push it, and never merge or delete it, so the record survives the work branch's merge without
  landing on `main`. On a public repo every pushed branch is public too, so keep notes there free of
  private details. The frontmatter goes above the first line of any repo template:

  ```yaml
  ---
  project: <project name as on the owner's dashboard>
  agent: <the trailer's Agent, lowercase: claude, codex, hermes, …>
  branch: <branch>
  merged: false
  status: <one line>
  outstanding:
    - "to-do [mac-local] <item>"   # [mac-local] = only actionable on the owner's Mac
  ---
  ```

  Then cover what changed, the evidence, what's left, and any decision the brief didn't cover.
<!-- END agent-contracts:family -->

## The five hard rules

1. **Branch, never main.** Do design/UI work on `design/<topic>`. `main` stays deployable:
   here a push to `main` can redeploy the public site (Facts). If the work isn't finished and verified,
   it stays on the branch.
2. **Presentation only — never touch a data contract.** No changes to CSV columns, JSON keys,
   DB schemas, file paths, or anything an ETL job / lane / monitor reads or writes. If a design
   change seems to require a data change, stop and write it in the handback note instead.
3. **No secrets, no private artifacts in the repo.** Never commit `.env`, keys, tokens,
   credentials, or private snapshots. Secrets live outside the repo, never in plaintext. `.gitignore`d private files stay ignored.
4. **Never invent data.** Every number rendered must trace to a real, named source (API,
   filing, report, the repo's own data files). No interpolation, no estimates presented as
   facts, no placeholder values that could be mistaken for real ones.
5. **Verify, then push.** Run this repo's tests (below) green, and confirm the change renders
   in a real browser/UI. An HTTP 200 or a green grep proves nothing about a visual change.

## Finishing a design pass (the handback)

End every session with **all four**:

- [ ] Working tree clean; all work committed **on the branch**.
- [ ] Branch pushed: `git push -u origin design/<topic>`.
- [ ] `docs/design-pass-<YYYY-MM-DD>.md` written — what changed (files + visual summary),
      how it was verified, what was deliberately **not** touched, and any invariant you
      suspect you bent. This file is how the next agent (or the owner) reconstructs intent
      without the session transcript.
- [ ] If the change needs the live service restarted, say so in the handback; restarting it needs the owner's yes.

If you run out of time mid-change: commit what works, leave the branch pushed, and say
clearly in the handback note what is half-done. **Never leave a half-finished change
uncommitted in the working tree** — an end-session sweep will commit it as one opaque blob.

## Working alongside Hermes

This repo is worked by more than one agent. Rules that keep that safe:

- The branch convention above is the boundary — two agents editing the same *files* on
  different branches is fine; on the same branch it is not.
- Don't delete or rewrite the other agent's files to make room for yours; extend instead.
- `AGENTS.md` is the one contract for every agent; `CLAUDE.md` only imports it (`@AGENTS.md`).
  Put rules and repo facts here, never in `CLAUDE.md`.
- Read `docs/design-pass-*.md` before starting — it is the record of what changed last time.

## Facts — market-dashboard

| | |
|---|---|
| Default branch | main |
| Remote | https://github.com/cutout-z/market-dashboard.git |
| Served / deployed by | **public:** Render (`render.yaml`; README "Current Runtime"). **private:** the owner's own server plus a local service on port 8060 (`app/config.py` `PORT`, `Dockerfile`). VERIFY which is live before restarting anything. |
| Push semantics | treat `main` as **PUBLISHED**: a push can redeploy the public Render site (`render.yaml` does not set `autoDeploy`, and Render's default is to deploy on every push; check in Render) and is pulled by the private runtime (unverified: not in this repo). `deploy/*` (`market-backfill.service`, `market-backfill.timer`, `market-dashboard.service`, `setup.sh`) are rollback artifacts only (README "Current Runtime"); container build present (`Dockerfile` / `docker-compose.yml`) — a change may need a rebuild, not just a restart |
| Tests (run before commit) | **none** — the repo tracks no test files (`git ls-files` matches no `test` path) and no test config; verify by running the app on a review port and checking it in a browser |
| Preview locally | `uvicorn app.main:app --host 127.0.0.1 --port 9215` — 8060 is the live instance. Run the design copy on a free port in **9200–9249** (9215 is the default here; pick another in that range if it is taken; never 9250–9259); never restart the live service to test a design change. |
| Data contracts you must not change | `app/data/` (.json, .parquet) |
| Automated writers | the private runtime (unverified: not in this repo); an end-session sweep that commits and pushes dirty repos has been reported (unverified: not in this repo), so leave nothing uncommitted |

### What it is

Market monitoring dashboard: a Bloomberg morning-stack (GMM/TOP/BTMM) concept built from free data sources.
Install dependencies with `pip install -r requirements.txt`; the app is `app.main:app` (see Preview locally above).

- **FastAPI + HTMX + Jinja2** — multi-page with sidebar nav, per-panel auto-refresh
- **Plotly.js** — interactive charts (yield curve, etc.)
- **Tailwind CSS** — dark theme; Tailwind, HTMX and Plotly are vendored under `app/static/vendor/`
- **Yahoo spark API** (primary) — async batch quotes/returns
- **yfinance** (secondary) — fundamentals (`Ticker.info`), options chains, the movers screener, and the `etl/backfill.py` history backfill
- Other: FRED API, Polymarket API, Google News RSS, ForexFactory JSON, central bank CSVs

### Pages

| Page | Route | Data Source | Refresh |
|------|-------|-------------|---------|
| Indices | /indices | Yahoo spark — world indices by region + S&P sectors + Defense indexes | 120s |
| Futures | /futures | Yahoo spark — 4 categories (currency, world indices, interest rates, shipping) | 120s |
| Forex | /forex | Yahoo spark — pairs table + NxN heatmap + 90-day pair correlations | 120s |
| Bonds | /bonds | Yahoo spark + FRED API — US yields, yield curve, spreads, MOVE index | 60s |
| Economy | /economy | Reference data + FRED historical charts (GDP, inflation, unemployment, rates) | hourly/6h |
| Macro Pulse | /pulse | Yahoo spark — HUD tiles, commodity ratios, sector rotation, correlation matrix | 120s |
| Commodities | /commodities | Yahoo spark — 36 commodities across 10 sectors with descriptions, market lens, forward curve, research panel | 120s |
| Mag 7 | /mag7 | Yahoo spark (prices) + yfinance (PE/EPS/fundamentals) | 120s |
| Movers | /movers | yfinance screener — top gainers, losers, most active | 5min |
| News | /news | Google News RSS + Polymarket API + ForexFactory economic calendar | 2-5min |
| AI Bubble Tracker | /bubble | Static reference — benchmarks (MMLU, GPQA, SWE-Bench), context windows, milestones | daily |
| Source Health | /api/sources | Live source freshness (21 sources), cache age, symbol coverage | 30s |

Also routed (see `app/routes/pages.py`): `/positioning`, `/health`, `/shocks`, `/signals`, `/analysis`.

### Key files

- `app/config.py` — all ticker lists, categories, refresh intervals, commodity drivers
- `app/sources/yahoo_quotes.py` — **core data fetcher** — async Yahoo spark API, batch quotes/returns
- `app/sources/` — one module per data domain (21 sources, base ABC + implementations)
- `app/sources/returns.py` — legacy yfinance returns module (kept for reference, no longer imported)
- `app/routes/pages.py` — page routes (one per section)
- `app/routes/partials.py` — HTMX partial endpoints
- `app/templates/base.html` — layout with sidebar navigation
- `app/templates/pages/` — page templates
- `app/templates/partials/` — HTMX partial templates
- `app/data/cache/` — JSON cache files (gitignored)

### Data sources

| Source | Module | Notes |
|--------|--------|-------|
| Yahoo spark API | yahoo_quotes.py → indices, futures, forex, bonds, pulse, commodities | Primary |
| yfinance Ticker.info | mag7.py (fundamentals only) | PE/EPS/market cap |
| yfinance options | options.py | SPY IV skew |
| yfinance screener | movers.py | |
| FRED API | fred.py | yield curve, economic indicators |
| ForexFactory JSON | calendar.py | rate-limited API |
| Google News RSS | news.py | |
| Polymarket API | polymarket.py | direct API, DNS fallback |
| Central bank CSVs | intl_bonds.py | RBA, ECB, Japan MoF |

Live per-source status: `/api/sources`.

### Key indicators

- **MOVE Index** (`^MOVE`) — bond market volatility, leads equity vol
- **2Y Yield** — via FRED DGS2 (yfinance 2YY=F delisted)
- **2s10s Spread** — 10Y minus 2Y, recession indicator
- **3M/10Y Spread** — alternative curve shape measure
- **DXY** (`DX-Y.NYB`) — US Dollar Index
- **Commodity Ratios** — Gold/Silver (risk), Copper/Gold (growth)

### Autoresearch layers

Three autoresearch layers follow the Karpathy pattern: mutate params → evaluate → log → repeat.

| Layer | Directory | Mutation Surface | Evaluation Metric | CLI |
|-------|-----------|-----------------|-------------------|-----|
| 1. Signal Backtesting | `signals/` | Strategy params (thresholds, lookbacks, hold periods) | Sharpe ratio vs backtest | `python -m signals.autoresearch` |
| 2. News Classification | `news_classification/` | Per-category weight multipliers + thresholds (14 params) | Accuracy + weighted F1 vs labeled headlines | `python -m news_classification.autoresearch` |
| 3. Data Source Quality | `data_quality/` | Scorer weights (success, data, latency, streak) | Composite reliability score | `python -m data_quality.run_eval --snapshot` |

Layer 2 classifies news headlines into 8 categories: geopolitical, macro, trade, earnings, tech, energy, crypto,
market. The dashboard (`app/sources/news.py`) auto-loads the best-known params from
`news_classification/findings.jsonl` (gitignored; defaults apply when it is absent). Template color coding:
red=geo, amber=macro, orange=trade, green=earnings, purple=tech, yellow=energy, cyan=crypto, blue=market.

### Performance notes

- Refresh tasks staggered by 2s each at startup to avoid thundering herd
- Yahoo spark endpoint: 20 symbols/batch, all batches concurrent via asyncio.gather
- Return periods: 24h, 1W, 1M, 3M, 1Y, 5Y, 10Y (all 7 periods fetched via 10Y spark history)
- Cache safety: empty fetches don't overwrite good cached data

### Notes

- `CLAUDE.md` is a two-line `@AGENTS.md` import (2026-10-08); Claude Code loads this contract through it.
- Existing docs worth reading first: `README.md`

