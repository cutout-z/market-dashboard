"""Market Dashboard — FastAPI + HTMX multi-page dashboard."""

import asyncio
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routes import pages, partials, api
from app.sources.base import BaseSource
from app.sources.historical import HistoricalData

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


class _HttpxFailuresOnly(logging.Filter):
    """httpx logs every request at INFO, the bulk of the service log (2026-11-19).

    Keep only responses with status >= 400, with API keys in the URL redacted
    (FRED and FMP put them in the query string); drop the rest.
    """

    _KEY = re.compile(r"((?:api_?key|apikey)=)[^&\s\"]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not (isinstance(args, tuple) and len(args) == 5 and isinstance(args[3], int)):
            return True
        if args[3] < 400:
            return False
        record.args = (args[0], self._KEY.sub(r"\1REDACTED", str(args[1])), *args[2:])
        return True


logging.getLogger("httpx").addFilter(_HttpxFailuresOnly())
logger = logging.getLogger("market-dashboard")


async def _refresh_loop(source: BaseSource, initial_delay: float = 0):
    """Background loop: fetch data for a single source at its configured interval."""
    if initial_delay > 0:
        await asyncio.sleep(initial_delay)
    await source.refresh()
    while True:
        await asyncio.sleep(source.refresh_interval)
        await source.refresh()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background refresh tasks, staggered to avoid thundering herd."""
    from app.routes.partials import ALL_SOURCES

    # Load historical Parquet into memory (fast — <100ms)
    HistoricalData.load()

    # Stagger starts by 2s each so not all sources hit APIs simultaneously
    tasks = [
        asyncio.create_task(_refresh_loop(s, initial_delay=i * 2))
        for i, s in enumerate(ALL_SOURCES)
    ]
    logger.info("Started %d background refresh tasks (staggered 2s each)", len(tasks))

    yield

    for t in tasks:
        t.cancel()
    logger.info("Cancelled background refresh tasks")


app = FastAPI(title="Market Dashboard", lifespan=lifespan)

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routes
app.include_router(pages.router)
app.include_router(partials.router)
app.include_router(api.router)
