"""Base data source with JSON file caching."""

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("market-dashboard")


class BaseSource(ABC):
    """Abstract base for all data sources."""

    cache_key: str
    refresh_interval: int

    @abstractmethod
    async def fetch(self) -> dict:
        ...

    @property
    def cache_path(self) -> Path:
        return CACHE_DIR / f"{self.cache_key}.json"

    def get_cached(self) -> dict | None:
        if not self.cache_path.exists():
            return None
        try:
            return json.loads(self.cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def save_cache(self, data: dict):
        data["_cached_at"] = time.time()
        self.cache_path.write_text(json.dumps(data, default=str))

    def cache_age(self) -> float | None:
        cached = self.get_cached()
        if cached and "_cached_at" in cached:
            return time.time() - cached["_cached_at"]
        return None

    def _has_real_data(self, data: dict) -> bool:
        """Check if fetched data contains usable non-empty values."""

        def has_value(val) -> bool:
            if val is None:
                return False
            if isinstance(val, bool):
                return True
            if isinstance(val, (int, float)):
                return True
            if isinstance(val, str):
                return bool(val.strip())
            if isinstance(val, list):
                return any(has_value(item) for item in val)
            if isinstance(val, dict):
                return any(
                    has_value(v)
                    for k, v in val.items()
                    if not str(k).startswith("_") and k != "error"
                )
            return True

        return has_value(data)

    async def refresh(self) -> dict:
        t0 = time.time()
        success = False
        has_data = False
        error_msg = None
        try:
            data = await self.fetch()
            has_data = self._has_real_data(data)
            # Don't overwrite good cache with empty/null results
            if has_data:
                self.save_cache(data)
                logger.info("Refreshed %s", self.cache_key)
                success = True
            else:
                cached = self.get_cached()
                if cached and self._has_real_data(cached):
                    logger.warning("Skipping cache write for %s — fetch returned empty, keeping existing cache", self.cache_key)
                    success = True
                    return cached
                else:
                    # No existing good cache, save what we got
                    self.save_cache(data)
                    logger.warning("Refreshed %s with empty data (no prior cache)", self.cache_key)
                    success = True
            return data
        except Exception as e:
            error_msg = str(e)
            logger.warning("Failed to refresh %s: %s", self.cache_key, e)
            return self.get_cached() or {"error": str(e), "items": []}
        finally:
            elapsed_ms = (time.time() - t0) * 1000
            try:
                from data_quality.collector import log_event
                log_event(self.cache_key, success, elapsed_ms, has_data, error_msg)
            except Exception:
                pass  # telemetry must never break data refresh
