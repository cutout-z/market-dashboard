"""BTC SMA trend filters.

Strategy logic
--------------
Long Bitcoin when spot BTC is above a moving average, flat when it is below.
This tests the screenshot claim directly for the 50-day SMA, plus slower
200-day and 200-week regime filters.

All variants are long/flat, never short.
Target: Bitcoin (BTC-USD) daily returns.
"""
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

    default_params = {
        "hold_days": 1,
    }

    def required_symbols(self) -> list[str]:
        return []

    def _daily_signal(self, close: pd.Series, ma_period: int) -> pd.Series:
        ma = close.rolling(ma_period, min_periods=ma_period).mean()
        return (close > ma).astype(int)

    def _weekly_signal(self, close: pd.Series, ma_weeks: int) -> pd.Series:
        weekly_close = close.resample("W-SUN").last()
        weekly_ma = weekly_close.rolling(ma_weeks, min_periods=ma_weeks).mean()
        weekly_signal = (weekly_close > weekly_ma).astype(int)
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
    description = "Long BTC when BTC-USD closes above its 50-day SMA; flat below."

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
    description = "Long BTC when BTC-USD closes above its 200-day SMA; flat below."

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
    description = "Long BTC when BTC-USD is above its 200-week SMA; flat below."
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
