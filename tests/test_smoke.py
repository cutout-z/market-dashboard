"""Smoke tests: every GET route answers 200 from an empty cache, with no source I/O."""

import re

import pytest
from fastapi.routing import APIRoute

from app.main import app

SAMPLE = {"symbol": "SPY"}
# Required query params, so the handler runs instead of failing validation (422).
QUERY = {
    "/api/correlation": "?symbols=SPY,QQQ",
    "/partials/commodity-research": "?symbol=GC=F",
}
# Routes allowed to answer something other than 200: none today.
ALLOWED_STATUS: dict[str, set[int]] = {}


def _get_routes():
    return sorted(
        r.path for r in app.routes if isinstance(r, APIRoute) and "GET" in r.methods
    )


def _fill(path):
    filled = re.sub(r"\{(\w+)\}", lambda m: SAMPLE.get(m.group(1), "x"), path)
    return filled + QUERY.get(path, "")


def test_route_enumeration_found_routes():
    routes = _get_routes()
    assert len(routes) > 40
    assert "/" in routes and "/api/status" in routes and "/partials/indices" in routes


def test_source_io_guard_fires(source_io_calls):
    """The guard behind every route test raises something refresh() cannot swallow."""
    import asyncio

    from app.sources.indices import IndicesSource
    from conftest import SourceIOForbidden

    with pytest.raises(SourceIOForbidden):
        asyncio.run(IndicesSource().refresh())
    with pytest.raises(SourceIOForbidden):
        asyncio.run(IndicesSource().fetch())
    assert len(source_io_calls) == 2
    source_io_calls.clear()


def test_network_guard_blocks_external():
    import socket

    s = socket.socket()
    with pytest.raises(RuntimeError, match="network blocked"):
        s.connect(("93.184.216.34", 80))
    s.close()


@pytest.mark.parametrize("path", _get_routes())
def test_get_route_status(client, path):
    resp = client.get(_fill(path))
    allowed = ALLOWED_STATUS.get(path, {200})
    assert resp.status_code in allowed, f"{path} -> {resp.status_code}: {resp.text[:200]}"


def test_main_page_renders_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "<title>" in body and "Market Dashboard" in body
    assert "<nav" in body and "nav-item" in body


def test_api_status_shape(client):
    data = client.get("/api/status").json()
    assert isinstance(data, dict) and data
    assert all(v == {} for v in data.values())  # empty cache


def test_api_sources_shape(client):
    data = client.get("/api/sources").json()
    assert data
    for entry in data.values():
        assert set(entry) == {"refresh_interval", "cache_age_seconds", "has_data"}
        assert entry["has_data"] is False


def test_api_history_symbols_empty_state(client):
    data = client.get("/api/history/symbols").json()
    assert data["symbols"] == [] and "error" in data


def test_api_history_unknown_symbol(client):
    data = client.get("/api/history/SPY").json()
    assert data["symbol"] == "SPY" and data["data"] == []


def test_api_correlation_runs_handler(client):
    data = client.get("/api/correlation?symbols=SPY,QQQ").json()
    assert data["error"] == "Insufficient data"  # empty history, handler ran


def test_commodity_research_runs_handler(client):
    resp = client.get("/partials/commodity-research?symbol=GC=F")
    assert resp.status_code == 200 and "GC=F" in resp.text
