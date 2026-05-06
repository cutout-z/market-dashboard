"""World indices and S&P sector data with multi-period returns."""

from app.config import REFRESH_INDICES, WORLD_INDICES, SP_SECTORS, DEFENSE_INDEXES
from app.sources.base import BaseSource, logger
from app.sources.yahoo_quotes import fetch_multi_period_returns_async, fetch_all_spark


class IndicesSource(BaseSource):
    cache_key = "indices"
    refresh_interval = REFRESH_INDICES

    async def fetch(self) -> dict:
        world = await fetch_multi_period_returns_async(WORLD_INDICES)
        sectors = await fetch_multi_period_returns_async(SP_SECTORS)
        defense = await fetch_multi_period_returns_async(DEFENSE_INDEXES)
        treemap = await self._fetch_sector_treemap()
        return {"world": world, "sectors": sectors, "defense": defense, "sector_treemap": treemap}

    async def _fetch_sector_treemap(self) -> list[dict]:
        """Fetch market cap and daily change for sector ETFs for treemap."""
        symbols = [s["symbol"] for s in SP_SECTORS]
        spark_data = await fetch_all_spark(symbols, time_range="5d")

        results = []
        for sector in SP_SECTORS:
            sym = sector["symbol"]
            sd = spark_data.get(sym)
            if sd and sd["closes"] and len(sd["closes"]) >= 2:
                price = sd["closes"][-1]
                prev = sd["closes"][-2]
                change_pct = round((price / prev - 1) * 100, 2) if prev else 0.0
                results.append({
                    "name": sector["name"],
                    "symbol": sym,
                    "market_cap": 1e9,  # spark doesn't provide market cap
                    "change_pct": change_pct,
                    "price": round(float(price), 2),
                })
            else:
                results.append({
                    "name": sector["name"],
                    "symbol": sym,
                    "market_cap": 1e9,
                    "change_pct": 0,
                    "price": None,
                })
        return results
