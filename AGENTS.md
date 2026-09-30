# Design-pass contract — market-dashboard

**Applies to every agent session in this repo** (Claude Code, Hermes, Codex, or a human).
Read it before changing anything. Read the Facts block at the bottom for this repo's specifics.

## The five hard rules

1. **Branch, never main.** Do design/UI work on `design/<topic>`. `main` stays deployable —
   in some of these repos a push to main *is* a deploy. If the work isn't finished and verified,
   it stays on the branch.
2. **Presentation only — never touch a data contract.** No changes to CSV columns, JSON keys,
   DB schemas, file paths, or anything an ETL job / lane / monitor reads or writes. If a design
   change seems to require a data change, stop and write it in the handback note instead.
3. **No secrets, no private artifacts in the repo.** Never commit `.env`, keys, tokens,
   credentials, or private snapshots. Secrets live in macOS Keychain (or Bitwarden for the
   agent-facing path) — never in plaintext. `.gitignore`d private files stay ignored.
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
      suspect you bent. This file is how the next agent (or Zalen) reconstructs intent
      without the session transcript.
- [ ] Live service restarted if the change needs it (see Facts), and the restart verified.

If you run out of time mid-change: commit what works, leave the branch pushed, and say
clearly in the handback note what is half-done. **Never leave a half-finished change
uncommitted in the working tree** — an end-session sweep will commit it as one opaque blob.

## Working alongside Hermes

This repo is worked by more than one agent. Rules that keep that safe:

- The branch convention above is the boundary — two agents editing the same *files* on
  different branches is fine; on the same branch it is not.
- Don't delete or rewrite the other agent's files to make room for yours; extend instead.
- `AGENTS.md` = Hermes' contract, `CLAUDE.md` = Claude Code's contract. Keep the shared
  rules identical in both; repo facts live in one place and the other points at it.
- Read `docs/design-pass-*.md` before starting — it is the record of what changed last time.

## Facts — market-dashboard

| | |
|---|---|
| Default branch | main |
| Remote | https://github.com/cutout-z/market-dashboard.git |
| Served / deployed by | `com.zalen.market-dashboard` (port 8060) |
| Push semantics | a push to main changes what the local service serves (it runs from this directory); `deploy/` present (`market-backfill.service`, `market-backfill.timer`, `market-dashboard.service`, `setup.sh`) — read before assuming a push is inert; container build present (`Dockerfile` / `docker-compose.yml`) — a change may need a rebuild, not just a restart |
| Tests (run before commit) | **none detected** — VERIFY: add the real command here |
| Preview locally | `/opt/anaconda3/bin/uvicorn app.main:app --host 127.0.0.1 --port 92NN` — the live instance runs from this directory on port 8060. Start the design copy on a free port in the **9200 review band** (`worktree-setup.sh` prints the allocated one); never restart the live service to test a design change. |
| Data contracts you must not change | `app/data/` (.json, .parquet) |
| Automated writers | a LaunchAgent runs it locally; the Hermes/Codex end-session sweep (commits + pushes dirty repos) |

### Notes

- `CLAUDE.md` already exists — the pointer line was **not** inserted; add it by hand at the top so Claude Code loads this contract.
- Existing docs worth reading first: `README.md`, `CLAUDE.md`

