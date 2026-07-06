"""
app.py - Demand & Supply Dashboard (Streamlit port)
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import io
import wave
import struct
import base64
import math
import datetime as dt

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS

st.set_page_config(page_title="Demand & Supply Dashboard", layout="wide")

# --------------------------------------------------------------------------
# 🔥 UPDATED PRESETS - COMPLETE FOREX (MAJOR + MINOR + CROSS, NO EXOTICS)
# --------------------------------------------------------------------------
MARKET_PRESETS = {
    "Indian Stocks (NSE)": {
        "suffix_hint": "e.g. RELIANCE.NS, TCS.NS",
        "tickers": [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
            "BAJFINANCE.NS", "HINDUNILVR.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS",
            "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS",
            "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "COALINDIA.NS", "BHARTIARTL.NS",
            "TATACONSUM.NS", "PIDILITIND.NS", "DIVISLAB.NS", "DRREDDY.NS", "GRASIM.NS",
            "JSWSTEEL.NS", "TECHM.NS", "TITAN.NS", "HDFCLIFE.NS", "SBILIFE.NS",
            "BRITANNIA.NS", "HINDALCO.NS", "EICHERMOT.NS", "BAJAJFINSV.NS", "ADANIGREEN.NS",
            "ADANIENT.NS", "VEDL.NS", "TATASTEEL.NS", "JINDALSTEL.NS", "M&M.NS",
            "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "INDUSINDBK.NS", "YESBANK.NS",
            "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "AUBANK.NS",
            "MPHASIS.NS", "MINDTREE.NS", "COFORGE.NS", "LTI.NS", "LTTS.NS",
            "CIPLA.NS", "GLENMARK.NS", "AUROPHARMA.NS", "LUPIN.NS", "TORNTPHARM.NS",
            "APOLLOHOSP.NS", "FORTIS.NS", "MAXHEALTH.NS",
            "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "ESCORTS.NS",
            "NESTLEIND.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "EMAMILTD.NS",
            "TATAPOWER.NS", "ADANIPOWER.NS", "GAIL.NS", "PETRONET.NS", "IOC.NS", "BPCL.NS",
            "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS",
            "HAL.NS", "BEL.NS", "BHEL.NS", "SIEMENS.NS", "ABB.NS",
            "SUZLON.NS", "TATACHEM.NS", "UPL.NS", "SRTRANSFIN.NS",
        ],
    },
    "US Stocks": {
        "suffix_hint": "e.g. AAPL, TSLA, NVDA",
        "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "NFLX", "ADBE", "CRM", "ORCL", "IBM", "CSCO", "INTC",
            "AMD", "QCOM", "TXN", "AVGO", "MU",
            "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "PYPL",
            "BLK", "AXP", "USB", "PNC",
            "JNJ", "PFE", "MRK", "UNH", "CVS", "ABBV", "LLY",
            "GILD", "BIIB", "AMGN", "VRTX", "MRNA",
            "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "SBUX",
            "NKE", "DIS", "UPS", "FDX", "TGT",
            "XOM", "CVX", "COP", "SLB", "EOG", "OXY",
            "GE", "CAT", "BA", "RTX", "LMT", "HON", "UNP",
            "T", "VZ", "TMUS", "CMCSA",
            "COIN", "MSTR", "RIOT", "MARA",
            "^GSPC", "^DJI", "^IXIC",
        ],
    },
    "Forex - Major + Minor + Cross": {
        "suffix_hint": "e.g. EURUSD=X, GBPJPY=X",
        "tickers": [
            # --- MAJOR PAIRS ---
            "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", 
            "USDCAD=X", "USDCHF=X", "NZDUSD=X",
            # --- MINOR PAIRS (Euro Crosses) ---
            "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURCAD=X", 
            "EURAUD=X", "EURNZD=X",
            # --- MINOR PAIRS (Pound Crosses) ---
            "GBPJPY=X", "GBPCHF=X", "GBPCAD=X", "GBPAUD=X", "GBPNZD=X",
            # --- MINOR PAIRS (Yen Crosses) ---
            "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X",
            # --- MINOR PAIRS (Other Crosses) ---
            "AUDCAD=X", "AUDCHF=X", "AUDNZD=X", "CADCHF=X", 
            "NZDCAD=X", "NZDCHF=X",
            # --- Indian Rupee Pairs ---
            "USDINR=X", "EURINR=X", "GBPINR=X", "JPYINR=X",
        ],
    },
    "Commodities": {
        "suffix_hint": "e.g. GC=F (Gold), CL=F (Crude)",
        "tickers": [
            "GC=F", "SI=F", "HG=F", "PL=F", "PA=F",
            "CL=F", "BZ=F", "NG=F", "RB=F", "HO=F",
            "ZC=F", "ZS=F", "ZW=F", "ZM=F", "ZL=F",
            "CT=F", "SB=F", "KC=F", "CC=F",
            "LE=F", "HE=F", "GF=F",
        ],
    },
    "Crypto": {
        "suffix_hint": "e.g. BTC-USD",
        "tickers": ["BTC-USD"],
    },
}

# 🔥 ALL TIMEFRAMES
INTERVAL_OPTIONS = [
    "5m", "15m", "30m", "45m", "60m", "75m", "125m",
    "2h", "4h", "5h", "6h", "8h", "10h", "12h", "16h",
    "1d", "1wk"
]

PERIOD_OPTIONS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]

# 🔥 yfinance interval mapping
YF_INTERVAL_MAP_APP = {
    "5m": "5m", "15m": "15m", "30m": "30m", "45m": "30m",
    "60m": "60m", "75m": "60m", "125m": "60m",
    "2h": "60m", "4h": "60m", "5h": "60m", "6h": "60m",
    "8h": "60m", "10h": "60m", "12h": "1d", "16h": "1d",
    "1d": "1d", "1wk": "1wk"
}

STATUS_LABELS = {
    "Fresh Zone": "active",
    "SL Zone": "sl",
    "Target Zone": "tp",
}

st.title("📊 Demand & Supply Dashboard")
st.caption("Python/Streamlit port with ALL timeframes (5m to Weekly) + 200+ Symbols")

# ==========================================================================
# SETTINGS - (Rest of app.py remains SAME as previous version)
# ==========================================================================
# [The rest of app.py is identical to the previous version I gave you]
# Just copy the remaining app.py code from the previous message
