"""Economy indicators — reference data with live rate overlay."""

import asyncio
import json
from pathlib import Path

from app.config import REFRESH_ECONOMY, ECONOMY_COUNTRIES, ECONOMY_INDICATORS
from app.sources.base import BaseSource, logger

# Reference data file for economic indicators
REF_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "economy_ref.json"

# Default reference data (approximate as of early 2026)
DEFAULT_ECONOMY_DATA = {
    "USA":       {"GDP ($T)": "28.8", "GDP Growth": "2.3%", "Budget/GDP": "-6.2%", "Govt Debt/GDP": "123%", "Interest Rate": "5.25%", "Inflation Rate": "2.8%", "Unemployment": "4.1%", "Current Acct/GDP": "-3.0%", "Industrial Prod Y/Y": "1.2%"},
    "China":     {"GDP ($T)": "18.5", "GDP Growth": "4.8%", "Budget/GDP": "-3.8%", "Govt Debt/GDP": "84%",  "Interest Rate": "3.10%", "Inflation Rate": "0.3%", "Unemployment": "5.1%", "Current Acct/GDP": "1.5%",  "Industrial Prod Y/Y": "5.8%"},
    "EU":        {"GDP ($T)": "16.6", "GDP Growth": "0.9%", "Budget/GDP": "-3.5%", "Govt Debt/GDP": "82%",  "Interest Rate": "3.65%", "Inflation Rate": "2.4%", "Unemployment": "6.4%", "Current Acct/GDP": "2.8%",  "Industrial Prod Y/Y": "-1.2%"},
    "Germany":   {"GDP ($T)": "4.5",  "GDP Growth": "0.1%", "Budget/GDP": "-2.1%", "Govt Debt/GDP": "64%",  "Interest Rate": "3.65%", "Inflation Rate": "2.2%", "Unemployment": "5.9%", "Current Acct/GDP": "6.2%",  "Industrial Prod Y/Y": "-4.5%"},
    "Japan":     {"GDP ($T)": "4.2",  "GDP Growth": "1.1%", "Budget/GDP": "-5.6%", "Govt Debt/GDP": "254%", "Interest Rate": "0.50%", "Inflation Rate": "3.2%", "Unemployment": "2.5%", "Current Acct/GDP": "3.5%",  "Industrial Prod Y/Y": "-0.8%"},
    "India":     {"GDP ($T)": "3.9",  "GDP Growth": "6.5%", "Budget/GDP": "-5.8%", "Govt Debt/GDP": "83%",  "Interest Rate": "6.50%", "Inflation Rate": "5.1%", "Unemployment": "7.8%", "Current Acct/GDP": "-1.8%", "Industrial Prod Y/Y": "4.2%"},
    "UK":        {"GDP ($T)": "3.4",  "GDP Growth": "0.6%", "Budget/GDP": "-4.5%", "Govt Debt/GDP": "97%",  "Interest Rate": "4.75%", "Inflation Rate": "3.0%", "Unemployment": "4.3%", "Current Acct/GDP": "-3.2%", "Industrial Prod Y/Y": "-0.5%"},
    "France":    {"GDP ($T)": "3.1",  "GDP Growth": "0.7%", "Budget/GDP": "-5.5%", "Govt Debt/GDP": "112%", "Interest Rate": "3.65%", "Inflation Rate": "2.1%", "Unemployment": "7.5%", "Current Acct/GDP": "-0.7%", "Industrial Prod Y/Y": "-1.8%"},
    "Canada":    {"GDP ($T)": "2.2",  "GDP Growth": "1.2%", "Budget/GDP": "-1.4%", "Govt Debt/GDP": "107%", "Interest Rate": "4.50%", "Inflation Rate": "2.7%", "Unemployment": "5.8%", "Current Acct/GDP": "-0.4%", "Industrial Prod Y/Y": "0.3%"},
    "Australia": {"GDP ($T)": "1.8",  "GDP Growth": "1.5%", "Budget/GDP": "-1.8%", "Govt Debt/GDP": "45%",  "Interest Rate": "4.10%", "Inflation Rate": "3.5%", "Unemployment": "4.0%", "Current Acct/GDP": "1.2%",  "Industrial Prod Y/Y": "1.8%"},
}


class EconomySource(BaseSource):
    cache_key = "economy"
    refresh_interval = REFRESH_ECONOMY

    async def fetch(self) -> dict:
        return await asyncio.to_thread(self._load_data)

    def _load_data(self) -> dict:
        # Try to load from reference file, fall back to defaults
        data = DEFAULT_ECONOMY_DATA
        if REF_DATA_PATH.exists():
            try:
                data = json.loads(REF_DATA_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        # Build table structure
        rows = []
        for country in ECONOMY_COUNTRIES:
            if country in data:
                row = {"country": country}
                for indicator in ECONOMY_INDICATORS:
                    row[indicator] = data[country].get(indicator, "—")
                rows.append(row)

        return {
            "countries": ECONOMY_COUNTRIES,
            "indicators": ECONOMY_INDICATORS,
            "rows": rows,
        }
