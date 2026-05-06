"""Futures data by category with multi-period returns."""

from app.config import REFRESH_FUTURES, FUTURES
from app.sources.base import BaseSource
from app.sources.yahoo_quotes import fetch_multi_period_returns_async


class FuturesSource(BaseSource):
    cache_key = "futures"
    refresh_interval = REFRESH_FUTURES

    async def fetch(self) -> dict:
        # Build flat list with category tags
        all_items = []
        for category, items in FUTURES.items():
            for item in items:
                all_items.append({**item, "category": category})

        # Fetch returns for all futures at once
        enriched = await fetch_multi_period_returns_async(all_items)

        # Re-group by category
        categories = {}
        for item in enriched:
            cat = item["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        return {"categories": categories}
