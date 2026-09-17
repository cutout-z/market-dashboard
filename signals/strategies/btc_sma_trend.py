"""BTC SMA trend filters.

Strategy logic
--------------
Long Bitcoin when spot BTC is above a moving average, flat when it is below.
This tests the screenshot claim directly for the 50-day SMA, plus slower
200-day and 200-week regime filters. Linear variants compare price to a
linear SMA. Log variants compare log price to a log-price SMA, which treats
equal percentage moves symmetrically.

All variants are long/flat, never short.
Target: Bitcoin (BTC-USD) daily returns.
"""
import numpy as np
import pandas as pd

from ..strategy import BaseStrategy


class _BtcSmaTrendBase(BaseStrategy):
    target_symbol = "BTC-USD"
    target_label = "Bitcoin (BTC-USD)"
    trade_long = "Hold long Bitcoin exposure."
    trade_flat = "Hold cash instead of Bitcoin exposure."
    trade_short = "No short leg; strategy is long/flat only."
    cadence = "Daily close"
    sizing_note = "Directional BTC regime filter; not a position-size recommendation."
    price_scale = "linear"

    default_params = {
        "hold_days": 1,
    }

    def required_symbols(self) -> list[str]:
        return []

    def _price_basis(self, close: pd.Series) -> pd.Series:
        if self.price_scale == "log":
            return np.log(close.where(close > 0))
        return close

    def _daily_signal(self, close: pd.Series, ma_period: int) -> pd.Series:
        basis = self._price_basis(close)
        ma = basis.rolling(ma_period, min_periods=ma_period).mean()
        return (basis > ma).astype(int)

    def _weekly_signal(self, close: pd.Series, ma_weeks: int) -> pd.Series:
        weekly_close = close.resample("W-SUN").last()
        weekly_basis = self._price_basis(weekly_close)
        weekly_ma = weekly_basis.rolling(ma_weeks, min_periods=ma_weeks).mean()
        weekly_signal = (weekly_basis > weekly_ma).astype(int)
        return weekly_signal.reindex(close.index, method="ffill").fillna(0).astype(int)

    def _apply_hold_days(self, signal: pd.Series) -> pd.Series:
        hold_days = int(self.params.get("hold_days", 1))
        if hold_days <= 1:
            return signal

        bearish_cross = (signal.diff() < 0).astype(int)
        extended_flat = bearish_cross.rolling(hold_days, min_periods=1).max()
        held_signal = signal.copy()
        held_signal[extended_flat > 0] = 0
        return held_signal


class Btc50DaySmaTrend(_BtcSmaTrendBase):
    name = "Btc50DaySmaTrend"
    version = "v1"
    description = "Long BTC when BTC-USD closes above its linear 50-day SMA; flat below."

    default_params = {
        "ma_period": 50,
        "hold_days": 1,
    }

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        close = prices[self.target_symbol]
        signal = self._daily_signal(close, int(self.params["ma_period"]))
        signal = self._apply_hold_days(signal).fillna(0).astype(int)
        signal.name = "signal"
        return signal


class Btc200DaySmaTrend(_BtcSmaTrendBase):
    name = "Btc200DaySmaTrend"
    version = "v1"
    description = "Long BTC when BTC-USD closes above its linear 200-day SMA; flat below."

    default_params = {
        "ma_period": 200,
        "hold_days": 1,
    }

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        close = prices[self.target_symbol]
        signal = self._daily_signal(close, int(self.params["ma_period"]))
        signal = self._apply_hold_days(signal).fillna(0).astype(int)
        signal.name = "signal"
        return signal


class Btc200WeekSmaTrend(_BtcSmaTrendBase):
    name = "Btc200WeekSmaTrend"
    version = "v1"
    description = "Long BTC when BTC-USD is above its linear 200-week SMA; flat below."
    cadence = "Weekly close, forward-filled to daily bars"

    default_params = {
        "ma_weeks": 200,
        "hold_days": 1,
    }

    def generate_signals(self, prices: dict[str, pd.Series]) -> pd.Series:
        close = prices[self.target_symbol]
        signal = self._weekly_signal(close, int(self.params["ma_weeks"]))
        signal = self._apply_hold_days(signal).fillna(0).astype(int)
        signal.name = "signal"
        return signal


class Btc50DayLogSmaTrend(Btc50DaySmaTrend):
    name = "Btc50DayLogSmaTrend"
    price_scale = "log"
    description = "Long BTC when log BTC-USD closes above its 50-day log-SMA; flat below."


class Btc200DayLogSmaTrend(Btc200DaySmaTrend):
    name = "Btc200DayLogSmaTrend"
    price_scale = "log"
    description = "Long BTC when log BTC-USD closes above its 200-day log-SMA; flat below."


class Btc200WeekLogSmaTrend(Btc200WeekSmaTrend):
    name = "Btc200WeekLogSmaTrend"
    price_scale = "log"
    description = "Long BTC when log BTC-USD is above its 200-week log-SMA; flat below."
