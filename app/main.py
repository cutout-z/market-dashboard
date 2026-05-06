"""Market Dashboard — FastAPI + HTMX multi-page dashboard."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routes import pages, partials, api
from app.sources.base import BaseSource
from app.sources.historical import HistoricalData

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
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
