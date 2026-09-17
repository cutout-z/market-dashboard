# Market Dashboard

Local-first market monitoring dashboard. Bloomberg morning stack concept built from free data sources.

## Current Runtime

As of the NAS cutover on 2026-05-29, the active private runtime is the QNAP NAS
runner, not the old Hetzner/VPS deployment files in `deploy/`.

- Private dashboard: `znas.tail104fa2.ts.net:8060`
- NAS web service: `ai-wif-market-dashboard`
- NAS autoresearch worker: `ai-wif-market-worker`
- NAS higher-timeframe worker: `ai-wif-market-htf-worker`
- NAS dispatcher: `/share/AI_Wif_Brain_Work/runner-stack/scripts/qnap-run-job`

The historical `deploy/*.service`, `deploy/*.timer`, and `deploy/setup.sh`
files are retained only as VPS migration/rollback artifacts. Do not infer the
active scheduler from those files; use `tools/nas-runner/compose.yml`,
`tools/nas-runner/scripts/nas-job`, and
`tools/nas-runner/WORKFLOW_REMAP.md`.

**Live public dashboard:** https://market-dashboard-o8mh.onrender.com/

The dashboard is a FastAPI application deployed on Render. It is not a GitHub Pages static site, so `cutout-z.github.io/.../market-dashboard` links will 404.

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8060 --reload
```

Local dashboard: http://localhost:8060

## Health Check

```bash
curl https://market-dashboard-o8mh.onrender.com/api/sources
```

This returns source freshness and whether each data source currently has real data.
