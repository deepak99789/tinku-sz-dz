"""Build supported custom OHLCV intervals from provider candles.

Intraday aggregation is anchored to the market session where known. Source
candles are never forward-filled; incomplete final buckets are dropped.
"""
from __future__ import annotations

import pandas as pd

SUPPORTED_TIMEFRAMES = [
    "5m", "15m", "30m", "45m", "75m", "125m",
    "1H", "2H", "4H", "5H", "6H", "8H", "10H", "16H",
    "1D", "1W",
]

def _minutes(value: str) -> int | None:
    value = str(value).strip().upper()
    if value.endswith("M") and value[:-1].isdigit():
        return int(value[:-1])
    if value.endswith("H") and value[:-1].isdigit():
        return int(value[:-1]) * 60
    return None

def build_timeframe(df: pd.DataFrame, timeframe: str, market: str | None = None) -> pd.DataFrame:
    """Return OHLCV data in requested timeframe; input index must be datetime."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close"]
    if any(c not in out.columns for c in required):
        return pd.DataFrame()
    out = out[required + (["Volume"] if "Volume" in out.columns else [])].dropna(subset=required)
    out.index = pd.to_datetime(out.index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    tf = str(timeframe).strip().upper()
    if tf in {"5M", "5MIN"}:
        return out
    rule_minutes = _minutes(tf)
    if rule_minutes is not None:
        # NSE cash session starts at 09:15 IST. US equities start at 09:30
        # New York time. Forex/crypto use UTC-aligned buckets.
        if market == "india":
            if out.index.tz is None:
                out.index = out.index.tz_localize("Asia/Kolkata")
            else:
                out.index = out.index.tz_convert("Asia/Kolkata")
            origin, offset = "start_day", "9h15min"
        elif market == "us":
            if out.index.tz is None:
                out.index = out.index.tz_localize("America/New_York")
            else:
                out.index = out.index.tz_convert("America/New_York")
            origin, offset = "start_day", "9h30min"
        else:
            if out.index.tz is None:
                out.index = out.index.tz_localize("UTC")
            else:
                out.index = out.index.tz_convert("UTC")
            origin, offset = "start_day", "0min"
        rule = f"{rule_minutes}min"
        agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        if "Volume" in out.columns:
            agg["Volume"] = "sum"
        result = out.resample(rule, origin=origin, offset=offset, label="left", closed="left").agg(agg)
        # A bucket is valid only when all OHLC fields exist. Missing source
        # candles are not fabricated; incomplete last buckets are discarded.
        result = result.dropna(subset=required)
        if not result.empty:
            expected = max(1, rule_minutes // 5)
            counts = out["Close"].resample(rule, origin=origin, offset=offset, label="left", closed="left").count()
            result = result[counts.reindex(result.index).fillna(0) >= expected]
        return result
    if tf in {"1D", "D", "1DAY"}:
        rule = "1D"
    elif tf in {"1W", "W", "1WK", "1WEEK"}:
        rule = "W-MON"
    else:
        return pd.DataFrame()
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in out.columns:
        agg["Volume"] = "sum"
    return out.resample(rule, label="left", closed="left").agg(agg).dropna(subset=required)
