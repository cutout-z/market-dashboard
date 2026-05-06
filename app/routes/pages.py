"""Page routes — one per dashboard section."""

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.sources.historical import HistoricalData, HISTORY_DIR
from app.routes.partials import ALL_SOURCES, shocks_source

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _page(template: str):
    async def handler(request: Request):
        return templates.TemplateResponse(request, f"pages/{template}")
    return handler


# Asset pages
router.add_api_route("/",        _page("indices.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/indices", _page("indices.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/futures", _page("futures.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/forex",   _page("forex.html"),   methods=["GET"], response_class=HTMLResponse)

# Commodities
router.add_api_route("/commodities", _page("commodities.html"), methods=["GET"], response_class=HTMLResponse)

# Mag 7
router.add_api_route("/mag7", _page("mag7.html"), methods=["GET"], response_class=HTMLResponse)

# Fixed income
router.add_api_route("/bonds",   _page("bonds.html"),   methods=["GET"], response_class=HTMLResponse)

# Macro
router.add_api_route("/economy", _page("economy.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/pulse",   _page("pulse.html"),   methods=["GET"], response_class=HTMLResponse)

# Markets
router.add_api_route("/movers",  _page("movers.html"),  methods=["GET"], response_class=HTMLResponse)

# News
router.add_api_route("/news",    _page("news.html"),    methods=["GET"], response_class=HTMLResponse)

# Positioning
router.add_api_route("/positioning", _page("positioning.html"), methods=["GET"], response_class=HTMLResponse)


# Source Health
@router.get("/health", response_class=HTMLResponse)
async def page_health(request: Request):
    return templates.TemplateResponse(request, "pages/health.html", {
        "source_count": len(ALL_SOURCES),
    })


# Shock Analogs
@router.get("/shocks", response_class=HTMLResponse)
async def page_shocks(request: Request):
    data = shocks_source.get_cached() or {"shocks": []}
    shocks = [s for s in data.get("shocks", []) if s.get("status") == "closed"]
    return templates.TemplateResponse(request, "pages/shocks.html", {
        "shocks": shocks,
        "shock_count": len(shocks),
    })


# Signals
router.add_api_route("/signals", _page("signals.html"), methods=["GET"], response_class=HTMLResponse)


# Analysis (needs context data)
@router.get("/analysis", response_class=HTMLResponse)
async def page_analysis(request: Request):
    meta_path = HISTORY_DIR / "metadata.json"
    history_meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    return templates.TemplateResponse(request, "pages/analysis.html", {
        "symbols": HistoricalData.symbols(),
        "history_meta": history_meta,
    })
