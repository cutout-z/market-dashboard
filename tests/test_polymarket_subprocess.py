"""A subprocess that overruns its timeout is killed and reaped, not leaked.

Regression for the Nov 2026 outage: hung curl children kept their pipes open in
the server until it hit the 256-descriptor limit and refused every connection.
"""

import asyncio
import os

import pytest

from app.sources.polymarket import _run


def _open_fds() -> int:
    return len(os.listdir("/dev/fd"))


def test_run_returns_output():
    code, out, _ = asyncio.run(_run("echo", "ok", timeout=5))
    assert code == 0 and out.strip() == b"ok"


def test_timeout_kills_and_reaps_child():
    async def main():
        before = _open_fds()
        for _ in range(5):
            with pytest.raises(asyncio.TimeoutError):
                await _run("sleep", "30", timeout=0.2)
        return before, _open_fds()

    before, after = asyncio.run(main())
    assert after <= before, f"descriptors leaked: {before} -> {after}"
