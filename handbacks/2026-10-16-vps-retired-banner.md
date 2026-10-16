---
project: market-dashboard
agent: claude
branch: docs/vps-retired-banner
merged: false
status: PR #6 open; docs-only change, awaiting review and merge
outstanding:
  - "to-do review and merge PR #6"
---

## What changed

Added a retirement comment and an early `exit 1` guard to `deploy/setup.sh`. The VPS was retired on 2026-05-29; the NAS runner runs every lane.

## Evidence

`bash -n` passes; running the script prints the message and exits 1. The repo tracks no tests.

## What's left

Merge PR #6. Nothing else changed; no decisions beyond the brief.
