"""Smoke-test fixtures: tmp cache/history/log/vault paths, no source I/O, no lifespan."""

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
    """Re-root every path a route reads or writes at tmp, except the committed
    signals parquet (``signals.evaluate.PARQUET_PATH``), which is read as is.

    Cache miss and empty history = empty state; the Obsidian vault is an empty dir.
    """
    from app.sources import base, historical
    import app.routes.pages as pages
    import app.routes.partials as partials
    import data_quality.collector as collector
    import data_quality.findings as dq_findings
    import news_classification.findings as news_findings
    import signals.findings as sig_findings

    cache = tmp_path / "cache"
    history = tmp_path / "history"
    cache.mkdir()
    history.mkdir()
    monkeypatch.setattr(base, "CACHE_DIR", cache)
    monkeypatch.setattr(historical, "HISTORY_DIR", history)
    monkeypatch.setattr(historical, "PARQUET_PATH", history / "prices.parquet")
    monkeypatch.setattr(pages, "HISTORY_DIR", history)
    monkeypatch.setattr(historical.HistoricalData, "_df", None, raising=False)
    vault = tmp_path / "vault" / "Commodities"
    vault.mkdir(parents=True)
    monkeypatch.setattr(partials, "COMMODITY_NOTES_DIR", vault)
    monkeypatch.setattr(collector, "EVENTS_PATH", tmp_path / "events.jsonl")
    monkeypatch.setattr(dq_findings, "FINDINGS_PATH", tmp_path / "dq_findings.jsonl")
    monkeypatch.setattr(news_findings, "FINDINGS_PATH", tmp_path / "news_findings.jsonl")
    monkeypatch.setattr(sig_findings, "FINDINGS_PATH", tmp_path / "signals_findings.jsonl")
    return tmp_path


class SourceIOForbidden(BaseException):
    """Not an Exception: ``except Exception`` in BaseSource.refresh and the
    handlers cannot swallow it, so a route that reaches source I/O fails loudly."""


def _all_subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


@pytest.fixture
def source_io_calls(monkeypatch):
    """Forbid every route-reachable source refresh/fetch and HTTP client call.

    Patches refresh/fetch on BaseSource and on every subclass that defines its own,
    plus the transports sources use (httpx, requests, curl_cffi which yfinance uses).
    Calls are recorded and raise SourceIOForbidden. Yields the list of calls.
    """
    import importlib
    import pkgutil

    import app.sources

    for m in pkgutil.iter_modules(app.sources.__path__):
        importlib.import_module(f"app.sources.{m.name}")
    from app.sources.base import BaseSource

    calls = []

    def make(label):
        async def forbidden_async(self, *a, **k):
            calls.append(label)
            raise SourceIOForbidden(label)

        return forbidden_async

    def make_sync(label):
        def forbidden(self, *a, **k):
            calls.append(label)
            raise SourceIOForbidden(label)

        return forbidden

    for cls in [BaseSource, *_all_subclasses(BaseSource)]:
        for name in ("refresh", "fetch"):
            if name in vars(cls):
                monkeypatch.setattr(cls, name, make(f"{cls.__name__}.{name}"))

    import httpx
    import requests

    # Transports, not Client.send: TestClient is an httpx.Client with its own in-process transport.
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", make("httpx.AsyncHTTPTransport"))
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", make_sync("httpx.HTTPTransport"))
    monkeypatch.setattr(requests.Session, "request", make_sync("requests.Session.request"))
    try:
        from curl_cffi import requests as cffi_requests

        monkeypatch.setattr(cffi_requests.Session, "request", make_sync("curl_cffi.Session.request"))
        monkeypatch.setattr(cffi_requests.AsyncSession, "request", make("curl_cffi.AsyncSession.request"))
    except ImportError:
        pass
    return calls


@pytest.fixture
def client(source_io_calls):
    # Deliberately not a context manager: the lifespan (refresh loops) never starts.
    from app.main import app

    yield TestClient(app)
    assert source_io_calls == [], f"a route reached source I/O: {source_io_calls}"
