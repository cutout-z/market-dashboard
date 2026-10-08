# Market Dashboard

Local-first market monitoring dashboard. Bloomberg morning stack concept built from free data sources.

## Current Runtime

The private runtime is the owner's own server. The `deploy/*.service`, `deploy/*.timer`
and `deploy/setup.sh` files are kept only as VPS rollback artifacts; do not infer the
active scheduler from them. The public instance runs on Render (`render.yaml`).

**Live public dashboard:** https://market-dashboard-o8mh.onrender.com/

The dashboard is a FastAPI application deployed on Render. It is not a GitHub Pages static site, so `cutout-z.github.io/.../market-dashboard` links will 404.

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 9215 --reload
```

Local dashboard: http://localhost:9215 (8060 is the live instance)

## Health Check

```bash
curl https://market-dashboard-o8mh.onrender.com/api/sources
```

This returns source freshness and whether each data source currently has real data.
