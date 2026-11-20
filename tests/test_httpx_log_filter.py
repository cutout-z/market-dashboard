"""httpx request logging: failures kept (keys redacted), successes dropped.

httpx logs every request at INFO; on 2026-11-19 that was 85% of the service log.
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
            return httpx.Response(500 if "bad" in request.url.path else 200)

        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            c.get("https://example.test/ok?api_key=SECRET1")
            c.get("https://example.test/bad?series=X&api_key=SECRET2&x=1")
            c.get("https://example.test/bad?apikey=SECRET3")
    finally:
        log.removeHandler(cap)
        log.setLevel(old_level)

    assert len(cap.lines) == 2, cap.lines
    assert all("500" in l for l in cap.lines)
    joined = " ".join(cap.lines)
    assert "SECRET" not in joined and joined.count("REDACTED") == 2
    assert "series=X" in joined and "x=1" in joined
