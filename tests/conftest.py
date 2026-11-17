"""Smoke-test fixtures: tmp cache/history dirs, no network, no lifespan."""

import ipaddress
import socket

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    real_connect = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else None
        if host is None or host == "localhost" or ipaddress.ip_address(host).is_loopback:
            return real_connect(self, address, *a, **k)
        raise RuntimeError(f"network blocked in tests: {address!r}")

    def no_dns(*a, **k):
        raise RuntimeError(f"DNS blocked in tests: {a!r}")

    monkeypatch.setattr(socket.socket, "connect", guarded)
    monkeypatch.setattr(socket, "getaddrinfo", no_dns)


@pytest.fixture(autouse=True)
def _tmp_data(monkeypatch, tmp_path):
    """Point cache and history paths at empty tmp dirs (cache miss = empty state)."""
    from app.sources import base, historical
    import app.routes.pages as pages

    cache = tmp_path / "cache"
    history = tmp_path / "history"
    cache.mkdir()
    history.mkdir()
    monkeypatch.setattr(base, "CACHE_DIR", cache)
    monkeypatch.setattr(historical, "HISTORY_DIR", history)
    monkeypatch.setattr(historical, "PARQUET_PATH", history / "prices.parquet")
    monkeypatch.setattr(pages, "HISTORY_DIR", history)
    monkeypatch.setattr(historical.HistoricalData, "_df", None, raising=False)
    return tmp_path


@pytest.fixture
def client():
    # Deliberately not a context manager: the lifespan (refresh loops) never starts.
    from app.main import app

    return TestClient(app)
