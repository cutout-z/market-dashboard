"""Historical macro shock database for analog pattern-matching.

Loads from app/data/shocks.json (curated from ZC_Mac_Vault/Macro Shock Studies/).
Provides analog matching: given a current event classification, returns the most
similar historical shocks with similarity reasoning.

Usage:
    source = HistoricalShocksSource()
    data = source.get_cached()  # returns full shock database

    matcher = ShockAnalogMatcher(data["shocks"])
    analogs = matcher.find_analogs(
        shock_type="supply",
        shock_subtype="geopolitical_energy",
        severity=4,
        cpi_elevated=True,
    )
"""

import json
import logging
from pathlib import Path

from .base import BaseSource

logger = logging.getLogger("market-dashboard")

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "shocks.json"

# Refresh daily — data is static/manually curated, not live-fetched
REFRESH_SHOCKS = 86400


class HistoricalShocksSource(BaseSource):
    """Loads the curated historical shock database from shocks.json."""

    cache_key = "historical_shocks"
    refresh_interval = REFRESH_SHOCKS

    async def fetch(self) -> dict:
        """Load from local JSON file (no network call needed)."""
        if not DATA_FILE.exists():
            logger.warning("shocks.json not found at %s", DATA_FILE)
            return {"shocks": [], "prediction_rules": [], "error": "shocks.json not found"}
        try:
            data = json.loads(DATA_FILE.read_text())
            logger.info("Loaded %d shocks from shocks.json", len(data.get("shocks", [])))
            return data
        except Exception as e:
            logger.error("Failed to load shocks.json: %s", e)
            return {"shocks": [], "prediction_rules": [], "error": str(e)}

    def _has_real_data(self, data: dict) -> bool:
        """Override — this source is valid if shocks list is non-empty."""
        return bool(data.get("shocks"))


class ShockAnalogMatcher:
    """Finds the closest historical analogs to a described current event.

    Example:
        matcher = ShockAnalogMatcher(shocks_list)
        results = matcher.find_analogs(
            shock_type="supply",
            shock_subtype="geopolitical_energy",
            severity=4,
            cpi_elevated=True,
            economy_weakening=False,
        )
        # Returns list of (shock_dict, score, reasoning) sorted by score desc
    """

    def __init__(self, shocks: list[dict]):
        self.shocks = [s for s in shocks if s.get("status") == "closed"]

    def find_analogs(
        self,
        shock_type: str,
        shock_subtype: str | None = None,
        severity: int | None = None,
        cpi_elevated: bool | None = None,
        economy_weakening: bool | None = None,
        credit_spreads_widening: bool | None = None,
        top_n: int = 3,
    ) -> list[dict]:
        """Score and rank historical shocks by analog similarity.

        Args:
            shock_type: "supply" | "demand" | "financial" | "policy"
            shock_subtype: e.g. "geopolitical_energy", "credit_systemic"
            severity: 1-5 estimate for current shock
            cpi_elevated: True if CPI currently above target
            economy_weakening: True if leading indicators deteriorating
            credit_spreads_widening: True if HY/IG spreads rising
            top_n: Number of analogs to return

        Returns:
            List of dicts: {shock, score, reasoning}
        """
        scored = []
        for shock in self.shocks:
            score = 0
            reasoning = []

            # Type match (highest weight)
            if shock.get("type") == shock_type:
                score += 40
                reasoning.append(f"Shock type match: {shock_type}")

            # Subtype match
            if shock_subtype and shock.get("subtype") == shock_subtype:
                score += 25
                reasoning.append(f"Subtype match: {shock_subtype}")
            elif shock_subtype and shock_subtype in str(shock.get("subtype", "")):
                score += 10
                reasoning.append(f"Partial subtype match")

            # Severity proximity
            if severity is not None and shock.get("severity") is not None:
                diff = abs(shock["severity"] - severity)
                sev_score = max(0, 15 - diff * 5)
                score += sev_score
                if diff == 0:
                    reasoning.append(f"Severity match: {severity}/5")
                elif diff <= 1:
                    reasoning.append(f"Severity close: {shock['severity']}/5 vs current ~{severity}/5")

            # Macro context modifiers
            if cpi_elevated is not None:
                if cpi_elevated and shock.get("cpi_peak_pct") and shock["cpi_peak_pct"] > 5:
                    score += 10
                    reasoning.append("Both have elevated CPI context")
                elif not cpi_elevated and (not shock.get("cpi_peak_pct") or shock["cpi_peak_pct"] < 4):
                    score += 5
                    reasoning.append("Both have low-inflation context")

            if credit_spreads_widening is not None:
                financial_shock = shock.get("type") == "financial"
                if credit_spreads_widening and financial_shock:
                    score += 10
                    reasoning.append("Both have credit spread widening")
                elif not credit_spreads_widening and not financial_shock:
                    score += 5

            if economy_weakening is not None:
                trough = shock.get("gdp_trough_pct")
                if economy_weakening and trough and trough < -1.0:
                    score += 5
                    reasoning.append(f"Both show economic deterioration (historical GDP trough: {trough}%)")

            scored.append({
                "shock": shock,
                "score": score,
                "reasoning": reasoning,
                "key_rule": shock.get("key_rule", ""),
                "recovery_shape": shock.get("recovery_shape", ""),
                "equity_bottom_signal": shock.get("equity_bottom_signal", ""),
                "sp500_trough_move_pct": shock.get("sp500_trough_move_pct"),
                "sp500_breakeven_months": shock.get("sp500_breakeven_months"),
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_n]

    def get_applicable_rules(
        self,
        shock_type: str,
        shock_subtype: str | None = None,
        cpi_elevated: bool | None = None,
        credit_stress: bool | None = None,
    ) -> list[dict]:
        """Return prediction rules most applicable to the current shock context.

        Caller should provide the full rules list from the shock database:
            matcher = ShockAnalogMatcher(shocks)
            rules = matcher.get_applicable_rules(...)
        """
        # This is meant to be extended; for now just return all rules
        # Future: filter rules based on context
        return []


def get_shock_summary(shock: dict) -> str:
    """Return a compact text summary of a shock for display in the dashboard."""
    name = shock.get("name", "Unknown")
    date = shock.get("date", "")[:4]
    s_type = shock.get("type", "")
    severity = shock.get("severity", "?")
    sp_trough = shock.get("sp500_trough_move_pct")
    breakeven = shock.get("sp500_breakeven_months")
    recovery = shock.get("recovery_shape", "")

    lines = [f"**{name} ({date})**"]
    lines.append(f"Type: {s_type} · Severity: {severity}/5 · Recovery: {recovery}")
    if sp_trough:
        lines.append(f"S&P 500 peak-to-trough: {sp_trough:+.1f}%")
    if breakeven:
        lines.append(f"Nominal breakeven: {breakeven} months")
    key_rule = shock.get("key_rule", "")
    if key_rule:
        lines.append(f"Key rule: {key_rule}")
    return "\n".join(lines)
