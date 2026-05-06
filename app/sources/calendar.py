"""Economic calendar via ForexFactory JSON feed."""

from datetime import datetime, timezone

import httpx

from app.config import REFRESH_CALENDAR, FOREXFACTORY_CALENDAR_URL
from app.sources.base import BaseSource, logger


class CalendarSource(BaseSource):
    cache_key = "economic_calendar"
    refresh_interval = REFRESH_CALENDAR

    async def fetch(self) -> dict:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                resp = await client.get(FOREXFACTORY_CALENDAR_URL)
                if resp.status_code != 200:
                    return {"events": [], "error": f"HTTP {resp.status_code}"}

                raw = resp.json()
                events = self._parse_events(raw)
                return {"events": events}

        except Exception as e:
            logger.warning("Calendar fetch error: %s", e)
            return {"events": [], "error": str(e)}

    def _parse_events(self, raw: list) -> list[dict]:
        """Parse FF calendar JSON into structured events."""
        now = datetime.now(timezone.utc)
        today = now.date()

        events = []
        for item in raw:
            try:
                # Parse date
                date_str = item.get("date", "")
                if not date_str:
                    continue

                # FF dates are like "2026-04-05T08:30:00-04:00"
                event_dt = datetime.fromisoformat(date_str)
                event_date = event_dt.date()

                # Include today and future events (up to 7 days out)
                days_until = (event_date - today).days
                if days_until < 0 or days_until > 7:
                    continue

                impact = item.get("impact", "").strip()
                country = item.get("country", "").strip()
                title = item.get("title", "").strip()
                forecast = item.get("forecast", "").strip()
                previous = item.get("previous", "").strip()

                if not title:
                    continue

                # Only include High and Medium impact events (+ Holiday)
                if impact not in ("High", "Medium", "Holiday"):
                    continue

                # Determine if event has passed
                is_past = event_dt.astimezone(timezone.utc) < now

                events.append({
                    "title": title,
                    "country": country,
                    "date": event_date.isoformat(),
                    "time": event_dt.strftime("%H:%M"),
                    "time_utc": event_dt.astimezone(timezone.utc).strftime("%H:%M"),
                    "impact": impact,
                    "forecast": forecast,
                    "previous": previous,
                    "is_today": days_until == 0,
                    "is_past": is_past,
                    "day_label": "Today" if days_until == 0 else (
                        "Tomorrow" if days_until == 1 else event_date.strftime("%a %d %b")
                    ),
                })
            except Exception as e:
                logger.debug("Calendar event parse error: %s", e)
                continue

        return events
