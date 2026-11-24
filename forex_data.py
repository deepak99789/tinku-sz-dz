"""
Shared free multi-source Forex OHLCV fetcher.
Primary: Yahoo Finance. Fallbacks: Twelve Data and Alpha Vantage.
Optional secrets:
  TWELVEDATA_API_KEY
  ALPHAVANTAGE_API_KEY
All providers are public/free-tier services; coverage and quotas can vary.
"""
import os
import logging
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)


def _get_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    # Streamlit Community Cloud secrets are not automatically exported as env vars.
    try:
        import streamlit as st
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


# Exactly 28 standard pairs: 7 USD majors + 21 crosses among the 8 major currencies.
FOREX_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
    "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY",
    "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "NZDCAD", "NZDCHF",
]
FOREX_TICKERS = [f"{pair}=X" for pair in FOREX_PAIRS]

TD_INTERVALS = {
    "5m": "5min", "15m": "15min", "30m": "30min", "60m": "1h",
    "1d": "1day", "1wk": "1week", "1mo": "1month",
}
AV_INTRADAY = {"5m": "5min", "15m": "15min", "30m": "30min", "60m": "60min"}


def _clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    rename = {str(c).strip().lower(): c for c in out.columns}
    required = ["open", "high", "low", "close"]
    if not all(k in rename for k in required):
        return pd.DataFrame()
    out = out[[rename[k] for k in required]].copy()
    out.columns = ["Open", "High", "Low", "Close"]
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna().sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def _yahoo(pair: str, interval: str, period: str) -> pd.DataFrame:
    ticker = f"{pair}=X"
    try:
        raw = yf.download(
            ticker, interval=interval, period=period, progress=False,
            auto_adjust=False, threads=False,
        )
        return _clean_ohlc(raw)
    except Exception as exc:
        logger.warning("Forex Yahoo failed %s %s: %s", pair, interval, exc)
        return pd.DataFrame()


def _twelve_data(pair: str, interval: str) -> pd.DataFrame:
    api_key = _get_secret("TWELVEDATA_API_KEY")
    td_interval = TD_INTERVALS.get(interval)
    if not api_key or not td_interval:
        return pd.DataFrame()
    try:
        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": f"{pair[:3]}/{pair[3:]}",
                "interval": td_interval,
                "outputsize": 5000,
                "timezone": "UTC",
                "apikey": api_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        values = payload.get("values") if isinstance(payload, dict) else None
        if not values:
            logger.warning("Twelve Data no candles for %s %s: %s", pair, interval,
                           payload.get("message", payload.get("status", "empty response")))
            return pd.DataFrame()
        frame = pd.DataFrame(values)
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True, errors="coerce")
        frame = frame.set_index("datetime")
        return _clean_ohlc(frame)
    except Exception as exc:
        logger.warning("Twelve Data failed %s %s: %s", pair, interval, exc)
        return pd.DataFrame()


def _alpha_vantage(pair: str, interval: str) -> pd.DataFrame:
    api_key = _get_secret("ALPHAVANTAGE_API_KEY")
    if not api_key:
        return pd.DataFrame()
    if interval in AV_INTRADAY:
        function = "FX_INTRADAY"
        extra = {"interval": AV_INTRADAY[interval], "outputsize": "compact"}
    elif interval == "1d":
        function, extra = "FX_DAILY", {"outputsize": "compact"}
    elif interval == "1wk":
        function, extra = "FX_WEEKLY", {}
    elif interval == "1mo":
        function, extra = "FX_MONTHLY", {}
    else:
        return pd.DataFrame()
    try:
        params = {
            "function": function,
            "from_symbol": pair[:3],
            "to_symbol": pair[3:],
            "apikey": api_key,
            **extra,
        }
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=25)
        response.raise_for_status()
        payload = response.json()
        series_key = next((k for k in payload if "Time Series" in k), None)
        if not series_key:
            message = payload.get("Note") or payload.get("Information") or payload.get("Error Message") or "empty response"
            logger.warning("Alpha Vantage no candles for %s %s: %s", pair, interval, message)
            return pd.DataFrame()
        frame = pd.DataFrame.from_dict(payload[series_key], orient="index")
        frame.index = pd.to_datetime(frame.index, utc=True, errors="coerce")
        frame = frame.rename(columns={
            "1. open": "Open", "2. high": "High",
            "3. low": "Low", "4. close": "Close",
        })
        return _clean_ohlc(frame)
    except Exception as exc:
        logger.warning("Alpha Vantage failed %s %s: %s", pair, interval, exc)
        return pd.DataFrame()


def fetch_forex_data(ticker: str, interval: str, period: str = "1mo") -> pd.DataFrame:
    """Fetch Forex candles with ordered free-source fallback and source metadata."""
    pair = ticker.upper().replace("=X", "").replace("/", "")
    if pair not in FOREX_PAIRS:
        logger.warning("Forex ticker is not in the configured 28-pair universe: %s", ticker)
        return pd.DataFrame()

    # Yahoo first; it is the only configured source for non-standard intervals
    # such as 90m, 5d and 3mo. Other providers are tried only when supported.
    candidates = []
    if interval == "3mo":
        yahoo_interval = "3mo"
    else:
        yahoo_interval = interval
    candidates.append(("Yahoo Finance", lambda: _yahoo(pair, yahoo_interval, period)))
    candidates.append(("Twelve Data", lambda: _twelve_data(pair, interval)))
    candidates.append(("Alpha Vantage", lambda: _alpha_vantage(pair, interval)))

    for source, fetch in candidates:
        data = fetch()
        if not data.empty:
            data.attrs["data_source"] = source
            logger.info("Forex data OK: %s %s via %s (%d candles)", pair, interval, source, len(data))
            return data

    logger.error(
        "FOREX DATA MISSING: %s %s. Check Yahoo availability and optional "
        "TWELVEDATA_API_KEY / ALPHAVANTAGE_API_KEY secrets.",
        pair, interval,
    )
    return pd.DataFrame()
