"""Polymarket prediction market data via direct API.

Handles DNS resolution issues (Tailscale DNS can't resolve gamma-api.polymarket.com)
by falling back to curl with --resolve flag for proper SNI + IP override.
"""

import asyncio
import json

import httpx

from app.config import POLYMARKET_EVENT_LIMIT, REFRESH_POLYMARKET
from app.sources.base import BaseSource, logger

POLYMARKET_HOST = "gamma-api.polymarket.com"
POLYMARKET_API = f"https://{POLYMARKET_HOST}/events"


class PolymarketSource(BaseSource):
    cache_key = "polymarket_events"
    refresh_interval = REFRESH_POLYMARKET

    async def fetch(self) -> dict:
        # Try direct httpx first (works if DNS resolves)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(POLYMARKET_API, params={
                    "closed": "false",
                    "order": "volume",
                    "ascending": "false",
                    "limit": POLYMARKET_EVENT_LIMIT,
                })
                if resp.status_code == 200:
                    return self._parse_events(resp.json())
                return {"items": [], "error": f"HTTP {resp.status_code}"}
        except (httpx.ConnectError, OSError) as e:
            if "nodename" not in str(e) and "Name or service" not in str(e):
                logger.warning("Polymarket error: %s", e)
                return {"items": [], "error": str(e)}

        # DNS failed — fall back to curl with --resolve for proper SNI
        logger.info("Polymarket: DNS failed, using curl with --resolve fallback")
        return await self._fetch_via_curl()

    async def _fetch_via_curl(self) -> dict:
        """Use curl with --resolve to bypass DNS while keeping proper SNI/TLS."""
        try:
            # Resolve via Google DNS
            dig = await asyncio.create_subprocess_exec(
                "dig", "+short", POLYMARKET_HOST, "@8.8.8.8",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(dig.communicate(), timeout=5)
            ips = [l.strip() for l in stdout.decode().strip().split("\n")
                   if l.strip() and l[0].isdigit()]
            if not ips:
                return {"items": [], "error": "Could not resolve Polymarket API hostname"}

            ip = ips[0]
            url = f"{POLYMARKET_API}?closed=false&order=volume&ascending=false&limit={POLYMARKET_EVENT_LIMIT}"

            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "--resolve", f"{POLYMARKET_HOST}:443:{ip}", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)

            if proc.returncode != 0:
                return {"items": [], "error": f"curl error: {stderr.decode().strip()}"}

            raw = json.loads(stdout.decode())
            return self._parse_events(raw)

        except asyncio.TimeoutError:
            return {"items": [], "error": "Timeout"}
        except Exception as e:
            logger.warning("Polymarket curl fallback error: %s", e)
            return {"items": [], "error": str(e)}

    def _parse_events(self, raw: dict | list) -> dict:
        events = raw if isinstance(raw, list) else raw.get("events", raw.get("data", []))
        if not isinstance(events, list):
            return {"items": [], "error": "Unexpected response format"}

        items = []
        for event in events:
            markets = event.get("markets", [])
            odds_yes = None
            odds_no = None
            if markets:
                m = markets[0]
                odds_yes = m.get("outcomePrices", [None, None])
                if isinstance(odds_yes, list) and len(odds_yes) >= 2:
                    odds_no = odds_yes[1]
                    odds_yes = odds_yes[0]
                elif isinstance(odds_yes, str):
                    try:
                        odds_yes = float(odds_yes)
                    except (ValueError, TypeError):
                        odds_yes = None

            items.append({
                "title": event.get("title", "Unknown"),
                "slug": event.get("slug", ""),
                "volume": event.get("volume", 0),
                "liquidity": event.get("liquidity", 0),
                "odds_yes": self._to_pct(odds_yes),
                "odds_no": self._to_pct(odds_no),
                "num_markets": len(markets),
                "end_date": event.get("endDate"),
            })

        return {"items": items}

    def _to_pct(self, val) -> float | None:
        if val is None:
            return None
        try:
            v = float(val)
            if 0 <= v <= 1:
                return round(v * 100, 1)
            return round(v, 1)
        except (ValueError, TypeError):
            return None
