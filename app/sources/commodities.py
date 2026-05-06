"""Commodities data by sector with multi-period returns and forward curve shape."""

from app.config import REFRESH_COMMODITIES, COMMODITIES, COMMODITY_FORWARD_MAP, get_forward_symbol
from app.sources.base import BaseSource
from app.sources.yahoo_quotes import fetch_multi_period_returns_async, fetch_spot_prices


class CommoditiesSource(BaseSource):
    cache_key = "commodities"
    refresh_interval = REFRESH_COMMODITIES

    async def fetch(self) -> dict:
        all_items = []
        for sector, sector_data in COMMODITIES.items():
            for item in sector_data["items"]:
                all_items.append({**item, "sector": sector})

        enriched = await fetch_multi_period_returns_async(all_items)

        # Build forward symbol map: fwd_symbol → base_symbol
        forward_map: dict[str, str] = {}
        for item in all_items:
            base = item["symbol"]
            if base in COMMODITY_FORWARD_MAP:
                prefix, exchange = COMMODITY_FORWARD_MAP[base]
                fwd = get_forward_symbol(prefix, exchange)
                forward_map[fwd] = base

        fwd_prices = await fetch_spot_prices(list(forward_map.keys()))

        # Map back: base_symbol → forward_price
        fwd_by_base = {base: fwd_prices.get(fwd) for fwd, base in forward_map.items()}

        # Enrich each item with curve shape (contango/backwardation %)
        for item in enriched:
            spot = item.get("price")
            fwd = fwd_by_base.get(item["symbol"])
            if spot and fwd and spot > 0:
                curve_pct = round((fwd - spot) / spot * 100, 2)
                item["curve_pct"] = curve_pct
                # Positive = contango (fwd > spot), negative = backwardation (fwd < spot)
                item["curve_dir"] = "contango" if curve_pct > 0 else "backwardation"
            else:
                item["curve_pct"] = None
                item["curve_dir"] = None

        sectors: dict[str, list] = {}
        for item in enriched:
            sec = item["sector"]
            if sec not in sectors:
                sectors[sec] = []
            sectors[sec].append(item)

        sector_meta = {
            name: {"description": data["description"], "market_lens": data["market_lens"]}
            for name, data in COMMODITIES.items()
        }

        return {"sectors": sectors, "sector_meta": sector_meta}
