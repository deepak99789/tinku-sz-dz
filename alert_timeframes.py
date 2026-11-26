"""Shared timeframe definitions and 5-minute OHLC resampling for Telegram scanners."""
import pandas as pd

from forex_data import FOREX_TICKERS

LEGACY_INTERVALS = ["5m", "15m", "30m", "60m", "90m", "1d", "5d", "1wk", "1mo", "3mo"]
INDIA_INTERVALS = LEGACY_INTERVALS + ["75m", "125m", "2h"]
US_INTERVALS = LEGACY_INTERVALS + ["75m", "125m", "2h"]
FOREX_INTERVALS = LEGACY_INTERVALS + [
    "10m", "75m", "125m", "2h", "4h", "6h", "8h", "10h", "12h", "16h"
]

CUSTOM_INTERVAL_MINUTES = {
    "10m": 10, "75m": 75, "125m": 125,
    "2h": 120, "4h": 240, "6h": 360, "8h": 480,
    "10h": 600, "12h": 720, "16h": 960,
}


def resample_custom_timeframe(df: pd.DataFrame, ticker: str, interval: str) -> pd.DataFrame:
    """Build session-aligned custom candles from real 5-minute OHLC data."""
    minutes = CUSTOM_INTERVAL_MINUTES.get(interval)
    if not minutes or df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    required = ["Open", "High", "Low", "Close"]
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    if not all(col in out.columns for col in required):
        return pd.DataFrame()
    out = out[required].dropna().sort_index()
    idx = pd.DatetimeIndex(out.index)

    if ticker in FOREX_TICKERS:
        tz_name, session_open, session_close, offset = "UTC", None, None, "0min"
    elif ticker.endswith((".NS", ".BO")):
        tz_name, session_open, session_close, offset = "Asia/Kolkata", "09:15", "15:30", "9h15min"
    else:
        tz_name, session_open, session_close, offset = "America/New_York", "09:30", "16:00", "9h30min"

    if idx.tz is None:
        idx = idx.tz_localize(tz_name)
    else:
        idx = idx.tz_convert(tz_name)
    out.index = idx

    if session_open:
        local_times = out.index.strftime("%H:%M")
        weekdays = out.index.weekday < 5
        out = out.loc[
            weekdays
            & (local_times >= session_open)
            & (local_times < session_close)
        ]
    if out.empty:
        return pd.DataFrame()

    try:
        result = out.resample(
            f"{minutes}min", origin="start_day", offset=offset,
            label="left", closed="left"
        ).agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last"
        }).dropna()
    except Exception:
        return pd.DataFrame()
    return result.dropna()
