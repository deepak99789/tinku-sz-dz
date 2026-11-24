"""Free multi-provider OHLCV data access with a normalized DataFrame contract.

Provider selection:
- Binance public klines for Binance-listed crypto pairs (no API key).
- Yahoo Finance as the general free fallback.
- Optional Twelve Data fallback when TWELVEDATA_API_KEY is configured.
All returned frames use Open/High/Low/Close[/Volume] and a DatetimeIndex.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from timeframe_builder import build_timeframe

log = logging.getLogger(__name__)
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
TWELVE_URL = "https://api.twelvedata.com/time_series"

PERIOD_TO_YF = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
    "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y",
    "10y": "10y", "max": "max",
}
YF_BASE_INTERVAL = {"5m": "5m", "1D": "1d", "1W": "1wk"}

def _market_for_ticker(ticker: str, market: Optional[str] = None) -> str:
    if market:
        return market.lower()
    t = ticker.upper()
    if t.endswith(".NS") or t.endswith(".BO"):
        return "india"
    if t.endswith("-USD") or t.endswith("USDT") or t.endswith("BUSD"):
        return "crypto"
    if t.endswith("=X"):
        return "forex"
    if t.endswith("=F"):
        return "commodity"
    if t.startswith("^"):
        return "index"
    return "us"

def _clean_yahoo(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep].dropna(subset=["Open", "High", "Low", "Close"])

def _fetch_yahoo(ticker: str, interval: str, period: str) -> pd.DataFrame:
    yf_interval = YF_BASE_INTERVAL.get(interval, interval)
    yf_period = PERIOD_TO_YF.get(period, period)
    try:
        return _clean_yahoo(yf.download(
            ticker, interval=yf_interval, period=yf_period,
            progress=False, auto_adjust=False, threads=False,
        ))
    except Exception as exc:
        log.warning("Yahoo fetch failed for %s %s: %s", ticker, interval, exc)
        return pd.DataFrame()

def _binance_symbol(ticker: str) -> str:
    value = ticker.upper().replace("-", "")
    if value.endswith("USD") and not value.endswith("USDT"):
        value = value[:-3] + "USDT"
    return value

def _fetch_binance(ticker: str, period: str) -> pd.DataFrame:
    # Binance public spot API offers 1m/3m/5m/15m/30m/1h/2h/4h/6h/8h/12h/1d/1w.
    try:
        response = requests.get(
            BINANCE_KLINES,
            params={"symbol": _binance_symbol(ticker), "interval": "5m", "limit": 1000},
            timeout=12,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows, columns=[
            "open_time", "Open", "High", "Low", "Close", "Volume",
            "close_time", "quote_volume", "trades", "taker_base",
            "taker_quote", "ignore",
        ])
        frame.index = pd.to_datetime(frame.pop("open_time"), unit="ms", utc=True)
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception as exc:
        log.warning("Binance fetch failed for %s: %s", ticker, exc)
        return pd.DataFrame()

def _fetch_twelve_data(ticker: str, timeframe: str, outputsize: int = 5000) -> pd.DataFrame:
    key = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not key:
        return pd.DataFrame()
    interval_map = {
        "5m": "5min", "15m": "15min", "30m": "30min", "1H": "1h",
        "1D": "1day", "1W": "1week",
    }
    interval = interval_map.get(timeframe, "5min")
    symbol = ticker.replace("=X", "").replace(".NS", "")
    try:
        response = requests.get(TWELVE_URL, params={
            "symbol": symbol, "interval": interval, "outputsize": outputsize,
            "apikey": key, "format": "JSON",
        }, timeout=15)
        response.raise_for_status()
        payload = response.json()
        values = payload.get("values", []) if isinstance(payload, dict) else []
        if not values:
            return pd.DataFrame()
        frame = pd.DataFrame(values)
        frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
        frame = frame.set_index("datetime").sort_index()
        for col in ["open", "high", "low", "close", "volume"]:
            if col in frame:
                frame[col.title()] = pd.to_numeric(frame[col], errors="coerce")
        cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in frame]
        return frame[cols].dropna(subset=["Open", "High", "Low", "Close"])
    except Exception as exc:
        log.warning("Twelve Data fetch failed for %s: %s", ticker, exc)
        return pd.DataFrame()

def fetch_ohlcv(ticker: str, timeframe: str, period: str = "1mo",
                market: Optional[str] = None) -> pd.DataFrame:
    """Fetch provider candles and build the requested interval."""
    market_type = _market_for_ticker(ticker, market)
    tf = str(timeframe).upper()
    custom_intraday = tf not in {"1D", "1W"} and tf.endswith(("M", "H"))
    # For custom intervals use 5-minute source bars; for native daily/weekly use Yahoo.
    source_interval = "5m" if custom_intraday else ("1d" if tf == "1D" else "1wk")
    frames = []
    if market_type == "crypto":
        crypto = _fetch_binance(ticker, period)
        if not crypto.empty:
            frames.append(crypto)
    yahoo = _fetch_yahoo(ticker, source_interval, period)
    if not yahoo.empty:
        frames.append(yahoo)
    if not frames:
        td = _fetch_twelve_data(ticker, timeframe)
        if not td.empty:
            frames.append(td)
    for frame in frames:
        built = build_timeframe(frame, timeframe, market=market_type)
        if not built.empty:
            return built
    return pd.DataFrame()
