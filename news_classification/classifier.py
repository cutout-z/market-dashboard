"""BaseClassifier ABC + KeywordWeighted classifier for news headline classification.

Mirrors signals/strategy.py — each classifier has tunable default_params,
a classify() method, and metadata() for the findings log.

Categories
----------
geopolitical — wars, sanctions, conflicts, military, NATO
macro        — Fed, rates, inflation, GDP, employment, central banks
trade        — tariffs, trade agreements, supply chains
earnings     — company results, revenue, guidance, EPS
tech         — AI, semiconductors, chips, tech companies
energy       — oil, OPEC, natural gas, renewables, utilities
crypto       — bitcoin, ethereum, blockchain, stablecoins
market       — default / general market moves

Autoresearch mutation surface
-----------------------------
Per-category weight multiplier (scales all keyword weights for that category):
    geo_weight, macro_weight, trade_weight, earnings_weight,
    tech_weight, energy_weight, crypto_weight

Per-category threshold (min weighted score to assign):
    geo_threshold, macro_threshold, trade_threshold, earnings_threshold,
    tech_threshold, energy_threshold, crypto_threshold

Global:
    confidence_floor — below this best-category score → "market" fallback
"""
from abc import ABC, abstractmethod
from typing import Any


CATEGORIES = [
    "geopolitical", "macro", "trade", "earnings",
    "tech", "energy", "crypto", "market",
]

# Keyword → weight per category.  Weights reflect specificity:
#   2.0 = highly specific (almost always this category)
#   1.5 = strong signal
#   1.0 = moderate signal
#   0.5 = weak / shared signal
CATEGORY_KEYWORDS: dict[str, dict[str, float]] = {
    "geopolitical": {
        "war ": 2.0, "warfare": 2.0, "invasion": 2.0, "invade": 2.0,
        "military": 1.5, "sanctions": 1.5, "sanction": 1.5,
        "missile": 2.0, "nuclear": 1.5, "conflict": 1.5, "nato": 2.0,
        "troops": 1.5, "ceasefire": 2.0, "escalation": 1.5, "escalat": 1.5,
        "drone strike": 2.0, "airstrike": 2.0, "air strike": 2.0,
        "geopolitic": 1.5, "territorial": 1.0, "annex": 1.5,
        "insurgent": 1.5, "rebel": 1.0, "militia": 1.5,
        "pentagon": 1.0, "defense minister": 1.0, "defence minister": 1.0,
        "arms deal": 1.5, "weapon": 1.0,
    },
    "macro": {
        "fed ": 2.0, "federal reserve": 2.0, "fomc": 2.0,
        "rate cut": 2.0, "rate hike": 2.0, "interest rate": 1.5,
        "inflation": 1.5, "cpi ": 2.0, "pce ": 2.0, "core cpi": 2.0,
        "gdp ": 1.5, "gdp growth": 2.0,
        "recession": 1.5, "soft landing": 1.5,
        "employment": 1.0, "unemployment": 1.5, "jobs report": 2.0,
        "nonfarm": 2.0, "non-farm": 2.0, "payroll": 1.5,
        "powell": 2.0, "yellen": 1.5, "central bank": 1.5,
        "monetary policy": 2.0, "quantitative": 1.5, "tightening": 1.0,
        "treasury yield": 1.5, "yield curve": 1.5, "basis point": 1.5,
        "ecb": 1.5, "bank of japan": 1.5, "boj": 1.5, "rba": 1.5,
    },
    "trade": {
        "tariff": 2.0, "trade war": 2.0, "trade deal": 2.0,
        "trade deficit": 1.5, "trade surplus": 1.5, "trade agreement": 1.5,
        "import duty": 1.5, "import ban": 1.5, "export ban": 1.5,
        "export control": 1.5, "supply chain": 1.5,
        "wto": 1.5, "trade policy": 1.5, "trade tension": 1.5,
        "protectionism": 1.5, "free trade": 1.0, "trade bloc": 1.0,
        "customs": 1.0, "dumping": 1.0,
    },
    "earnings": {
        "earnings": 1.5, "quarterly result": 2.0, "quarterly earnings": 2.0,
        "revenue beat": 2.0, "revenue miss": 2.0, "revenue": 1.0,
        "eps beat": 2.0, "eps miss": 2.0, "earnings beat": 2.0,
        "earnings miss": 2.0, "earnings season": 1.5,
        "profit": 1.0, "loss": 0.5, "surprise loss": 1.5,
        "guidance": 1.5, "raises guidance": 2.0, "forecast": 1.0,
        " q1": 1.0, " q2": 1.0, " q3": 1.0, " q4": 1.0,
        "fiscal year": 1.0, "annual report": 1.0,
        "buyback": 1.0, "share repurchase": 1.0,
        "dividend": 1.0, "ipo": 1.5, "merger": 1.0, "acquisition": 1.0,
    },
    "tech": {
        "artificial intelligence": 2.0, " ai ": 1.5, "ai model": 2.0,
        "machine learning": 1.5, "large language model": 2.0, "llm": 1.5,
        "chatgpt": 2.0, "openai": 2.0, "anthropic": 2.0, "google ai": 1.5,
        "nvidia": 1.5, "semiconductor": 2.0, "chip": 1.0, "chipmaker": 2.0,
        "tsmc": 2.0, "data center": 1.5, "data centre": 1.5,
        "cloud computing": 1.5, "cybersecurity": 1.0, "cyber": 1.0,
        "big tech": 1.5, "tech giant": 1.0, "silicon valley": 1.0,
    },
    "energy": {
        "oil price": 2.0, "crude oil": 2.0, "brent": 1.5, "wti": 1.5,
        "opec": 2.0, "opec+": 2.0, "natural gas": 1.5, "lng": 1.5,
        "energy crisis": 1.5, "energy price": 1.5,
        "gasoline": 1.0, "gas price": 1.0, "fuel price": 1.0,
        "oil output": 1.5, "oil production": 1.5, "barrel": 1.0,
        "refinery": 1.0, "pipeline": 1.0, "petroleum": 1.0,
        "renewable": 1.0, "solar": 0.5, "wind farm": 0.5,
        "nuclear energy": 1.0, "uranium": 1.0,
    },
    "crypto": {
        "bitcoin": 2.0, "btc": 1.5, "ethereum": 2.0, "eth ": 1.5,
        "crypto": 1.5, "cryptocurrency": 2.0, "blockchain": 1.5,
        "stablecoin": 2.0, "defi ": 2.0, "defi,": 2.0, "nft": 1.5,
        "binance": 1.5, "coinbase": 1.5, "sec crypto": 2.0,
        "digital asset": 1.5, "digital currency": 1.5,
        "token": 1.0, "altcoin": 1.5, "crypto regulation": 2.0,
        "crypto bill": 2.0, "crypto exchange": 1.5, "mining": 0.5,
    },
}


class BaseClassifier(ABC):
    """Abstract base for news classifiers evaluated by the autoresearch harness.

    Subclasses must set class attributes:
        name           — unique identifier, used as key in findings log
        version        — bump when default_params schema changes
        description    — one-line description for leaderboard
        default_params — dict of every tunable parameter with default value

    Subclasses must implement:
        classify(headline) — return (category, confidence)
    """

    name: str = "unnamed"
    version: str = "v1"
    description: str = ""
    default_params: dict[str, Any] = {}

    def __init__(self, **param_overrides: Any):
        self.params: dict[str, Any] = {**self.default_params, **param_overrides}

    @abstractmethod
    def classify(self, headline: str) -> tuple[str, float]:
        """Classify a headline → (category, confidence_score)."""
        ...

    def classify_batch(self, headlines: list[str]) -> list[tuple[str, float]]:
        """Classify multiple headlines. Override for batch-optimized classifiers."""
        return [self.classify(h) for h in headlines]

    def metadata(self) -> dict:
        return {
            "classifier": self.name,
            "version": self.version,
            "description": self.description,
            "params": dict(self.params),
        }


class KeywordWeighted(BaseClassifier):
    """Weighted keyword classifier with tunable per-category weights and thresholds.

    For each headline, computes a score per category by summing matched keyword
    weights × category weight multiplier. Assigns the highest-scoring category
    if it exceeds that category's threshold and the global confidence floor.

    Mutation surface (14 params):
        7 × category weight multiplier (scales keyword weights)
        7 × category threshold (min score to assign)
    """

    name = "KeywordWeighted"
    version = "v1"
    description = "Weighted keyword matching with per-category thresholds"

    default_params = {
        # Per-category weight multipliers
        "geo_weight": 1.0,
        "macro_weight": 1.0,
        "trade_weight": 1.0,
        "earnings_weight": 1.0,
        "tech_weight": 1.0,
        "energy_weight": 1.0,
        "crypto_weight": 1.0,
        # Per-category thresholds
        "geo_threshold": 1.5,
        "macro_threshold": 1.5,
        "trade_threshold": 1.5,
        "earnings_threshold": 1.5,
        "tech_threshold": 1.5,
        "energy_threshold": 1.5,
        "crypto_threshold": 1.5,
    }

    _WEIGHT_KEYS = {
        "geopolitical": "geo_weight",
        "macro": "macro_weight",
        "trade": "trade_weight",
        "earnings": "earnings_weight",
        "tech": "tech_weight",
        "energy": "energy_weight",
        "crypto": "crypto_weight",
    }
    _THRESHOLD_KEYS = {
        "geopolitical": "geo_threshold",
        "macro": "macro_threshold",
        "trade": "trade_threshold",
        "earnings": "earnings_threshold",
        "tech": "tech_threshold",
        "energy": "energy_threshold",
        "crypto": "crypto_threshold",
    }

    def classify(self, headline: str) -> tuple[str, float]:
        t = headline.lower()
        scores: dict[str, float] = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            weight_mul = self.params[self._WEIGHT_KEYS[category]]
            score = 0.0
            for kw, kw_weight in keywords.items():
                if kw in t:
                    score += kw_weight * weight_mul
            scores[category] = score

        if not scores:
            return ("market", 0.0)

        best_cat = max(scores, key=scores.get)
        best_score = scores[best_cat]
        threshold = self.params[self._THRESHOLD_KEYS[best_cat]]

        if best_score >= threshold:
            return (best_cat, round(best_score, 3))
        return ("market", round(best_score, 3))
