"""httpx request logging: failures kept (keys redacted), successes dropped.

httpx logs every request at INFO, most of the service log (2026-11-19).
"""

import logging

import httpx

import app.main  # noqa: F401  installs the filter


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def test_only_failed_requests_logged_with_keys_redacted():
    cap = _Capture()
    log = logging.getLogger("httpx")
    log.addHandler(cap)
    old_level = log.level
    log.setLevel(logging.INFO)  # the service's level (basicConfig INFO); pytest may raise the root's
    try:
        def handler(request):
            path = request.url.path
            if path == "/limited":
                return httpx.Response(429)
            if path == "/badreq":
                return httpx.Response(400)
            if path == "/moved":
                return httpx.Response(302)
            return httpx.Response(500 if "bad" in path else 200)

        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            c.get("https://example.test/ok?api_key=SECRET1")
            c.get("https://example.test/bad?series=X&api_key=SECRET2&x=1")
            c.get("https://example.test/bad?apikey=SECRET3")
            c.get("https://example.test/limited?api_key=SECRET4")
            c.get("https://example.test/moved")
            c.get("https://example.test/badreq?apikey=SECRET5")
    finally:
        log.removeHandler(cap)
        log.setLevel(old_level)

    assert len(cap.lines) == 4, cap.lines  # two 500s, the 429 and the 400; the 200 and 302 dropped
    assert sum("500" in l for l in cap.lines) == 2
    assert any("429" in l for l in cap.lines) and any(" 400 " in l for l in cap.lines)
    joined = " ".join(cap.lines)
    assert "SECRET" not in joined and joined.count("REDACTED") == 4
    assert "series=X" in joined and "x=1" in joined
