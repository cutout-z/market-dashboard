"""Smoke tests: every GET route answers (non-5xx) from an empty cache."""

import re

import pytest
from fastapi.routing import APIRoute

from app.main import app

SAMPLE = {"symbol": "SPY"}


def _get_routes():
    return sorted(
        r.path for r in app.routes if isinstance(r, APIRoute) and "GET" in r.methods
    )


def _fill(path):
    return re.sub(r"\{(\w+)\}", lambda m: SAMPLE.get(m.group(1), "x"), path)


def test_route_enumeration_found_routes():
    routes = _get_routes()
    assert len(routes) > 40
    assert "/" in routes and "/api/status" in routes and "/partials/indices" in routes


def test_no_refresh_or_network_on_requests(client, monkeypatch):
    """Lifespan is not entered and no GET triggers a fetch."""
    from app.sources.base import BaseSource

    async def boom(self):
        raise AssertionError("source refresh/fetch called during a smoke test")

    monkeypatch.setattr(BaseSource, "refresh", boom)
    assert client.get("/api/status").status_code == 200
    assert client.get("/partials/indices").status_code < 500


def test_network_guard_blocks_external():
    import socket

    s = socket.socket()
    with pytest.raises(RuntimeError, match="network blocked"):
        s.connect(("93.184.216.34", 80))
    s.close()


@pytest.mark.parametrize("path", _get_routes())
def test_get_route_not_5xx(client, path):
    resp = client.get(_fill(path))
    assert resp.status_code < 500, f"{path} -> {resp.status_code}: {resp.text[:200]}"


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
