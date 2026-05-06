"""MonthlyTrendRegime — higher-timeframe monthly trend filter.

Strategy logic
--------------
Evaluates the target asset at month-end only. Goes long when the month-end
close is above its moving average and flat otherwise. The monthly decision is
forward-filled across daily bars for backtesting.

This is a low-turnover, bear-market avoidance baseline. It is intentionally
simple so other higher-timeframe strategies can be judged against it.

Autoresearch mutation surface
------------------------------
    ma_months          int    default 10  — monthly moving average length
    confirm_months     int    default 1   — consecutive positive months required
    defensive_buffer   float  default 0   — require close > MA * (1 + buffer)
    hold_months        int    default 1   — stay flat this many months after trigger
"""
import pandas as pd

from ..strategy import BaseStrategy


class MonthlyTrendRegime(BaseStrategy):
    name = "MonthlyTrendRegime"
    version = "v1"
    description = (
        "Higher-timeframe S&P 500 trend filter; long when monthly close is "
        "above its moving average, flat in monthly downtrends."
    )
    target_symbol = "^GSPC"

    default_params = {
        "ma_months": 10,
        "confirm_months": 1,
        "defensive_buffer": 0.0,
        "hold_months": 1,
    }

    def required_symbols(self) -> list[str]:
        return []

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        p = self.params
        close = prices[self.target_symbol].dropna()

        monthly_close = close.resample("ME").last()
        monthly_ma = monthly_close.rolling(
            int(p["ma_months"]),
            min_periods=int(p["ma_months"]),
        ).mean()

        threshold = monthly_ma * (1 + float(p["defensive_buffer"]))
        monthly_up = (monthly_close > threshold).astype(int)

        confirm_months = int(p["confirm_months"])
        if confirm_months > 1:
            confirmed_up = (
                monthly_up.rolling(confirm_months, min_periods=confirm_months).sum()
                >= confirm_months
            ).astype(int)
        else:
            confirmed_up = monthly_up

        risk_off = (1 - confirmed_up).astype(int)
        hold_months = int(p["hold_months"])
        if hold_months > 1:
            risk_off = risk_off.rolling(hold_months, min_periods=1).max()

        monthly_signal = (1 - risk_off).fillna(0).astype(int)
        daily_signal = monthly_signal.reindex(close.index, method="ffill").fillna(0).astype(int)
        daily_signal.name = "signal"
        return daily_signal
