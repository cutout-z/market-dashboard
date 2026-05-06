"""Market movers — top gainers, losers, most active via yfinance screener."""

import asyncio

from app.config import REFRESH_MOVERS, MOVERS_LIMIT, MOVERS_EXCHANGES
from app.sources.base import BaseSource, logger


class MoversSource(BaseSource):
    cache_key = "market_movers"
    refresh_interval = REFRESH_MOVERS

    async def fetch(self) -> dict:
        return await asyncio.to_thread(self._fetch_all)

    def _fetch_all(self) -> dict:
        results = {}
        for region, meta in MOVERS_EXCHANGES.items():
            exchange = meta["exchange"]
            if exchange is None:
                # US — use predefined screens
                results[region] = {
                    "gainers": self._fetch_predefined("day_gainers"),
                    "losers": self._fetch_predefined("day_losers"),
                    "active": self._fetch_predefined("most_actives"),
                }
            else:
                results[region] = {
                    "gainers": self._fetch_exchange_movers(exchange, direction="gain"),
                    "losers": self._fetch_exchange_movers(exchange, direction="loss"),
                    "active": self._fetch_exchange_movers(exchange, direction="active"),
                }
        return results

    def _fetch_predefined(self, screen_id: str) -> list[dict]:
        try:
            from yfinance.screener import screen
            resp = screen(screen_id, count=MOVERS_LIMIT)
            return self._parse_quotes(resp.get("quotes", []))
        except Exception as e:
            logger.warning("Screener %s error: %s", screen_id, e)
            return []

    def _fetch_exchange_movers(self, exchange: str, direction: str) -> list[dict]:
        try:
            from yfinance.screener import EquityQuery, screen

            if direction == "gain":
                query = EquityQuery("and", [
                    EquityQuery("gt", ["percentchange", 2]),
                    EquityQuery("eq", ["exchange", exchange]),
                ])
                resp = screen(query, count=MOVERS_LIMIT, sortField="percentchange", sortAsc=False)
            elif direction == "loss":
                query = EquityQuery("and", [
                    EquityQuery("lt", ["percentchange", -2]),
                    EquityQuery("eq", ["exchange", exchange]),
                ])
                resp = screen(query, count=MOVERS_LIMIT, sortField="percentchange", sortAsc=True)
            else:  # active
                query = EquityQuery("and", [
                    EquityQuery("gt", ["dayvolume", 500000]),
                    EquityQuery("eq", ["exchange", exchange]),
                ])
                resp = screen(query, count=MOVERS_LIMIT, sortField="dayvolume", sortAsc=False)

            return self._parse_quotes(resp.get("quotes", []))
        except Exception as e:
            logger.warning("Exchange screener %s/%s error: %s", exchange, direction, e)
            return []

    def _parse_quotes(self, quotes: list) -> list[dict]:
        items = []
        for q in quotes[:MOVERS_LIMIT]:
            items.append({
                "symbol": q.get("symbol", ""),
                "name": q.get("shortName", q.get("longName", "")),
                "price": q.get("regularMarketPrice"),
                "change": round(q.get("regularMarketChange", 0), 2),
                "change_pct": round(q.get("regularMarketChangePercent", 0), 2),
                "volume": q.get("regularMarketVolume"),
                "market_cap": q.get("marketCap"),
            })
        return items
