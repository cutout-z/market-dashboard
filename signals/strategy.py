"""BaseStrategy — abstract base for all autoresearch signal strategies."""
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseStrategy(ABC):
    """Abstract base for signal strategies evaluated by the autoresearch harness.

    Signal convention
    -----------------
    1  = long target asset
    0  = flat (cash)
    -1 = short target asset

    Subclasses must set class attributes:
        name           — unique identifier, used as key in findings log
        version        — bump when default_params schema changes
        description    — one-line description for SIGNALS.md leaderboard
        target_symbol  — Yahoo Finance symbol whose returns this signal predicts
        default_params — dict of every tunable parameter with its default value

    Subclasses must implement:
        required_symbols() — which parquet symbols the strategy reads
        generate_signals() — produce a daily signal Series from price data
    """

    name: str = "unnamed"
    version: str = "v1"
    description: str = ""
    target_symbol: str = "^GSPC"
    default_params: dict[str, Any] = {}

    def __init__(self, **param_overrides: Any):
        self.params: dict[str, Any] = {**self.default_params, **param_overrides}

    @abstractmethod
    def required_symbols(self) -> list[str]:
        """Return Yahoo Finance symbols this strategy needs from the parquet."""
        ...

    @abstractmethod
    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        """Return a daily signal Series (DatetimeIndex, dtype int: 1/0/-1).

        Parameters
        ----------
        prices : mapping of symbol → pd.Series(close, DatetimeIndex)
                 guaranteed to contain every symbol in required_symbols()
        """
        ...

    def metadata(self) -> dict:
        return {
            "strategy": self.name,
            "version": self.version,
            "description": self.description,
            "target_symbol": self.target_symbol,
            "params": dict(self.params),
        }
