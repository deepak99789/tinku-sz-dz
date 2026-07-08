"""
app.py - DEEPAK SUPPLY DEMAND STRATEGY Dashboard
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
import time

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS

st.set_page_config(
    page_title="DEEPAK SUPPLY DEMAND STRATEGY", 
    layout="wide",
    page_icon="📊"
)

# ==========================================================================
# 🔥 CUSTOM CSS - CENTRE LAYOUT
# ==========================================================================

st.markdown("""
<style>
    /* Main container - centre */
    .main-container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 0 1rem;
    }
    
    /* Main title */
    .main-title {
        font-size: 2.8rem;
        font-weight: 700;
        color: #FFD700;
        text-align: center;
        padding: 1.2rem 0;
        background: linear-gradient(135deg, #0a0a1a, #1a1a3e, #0a0a1a);
        border-radius: 15px;
        margin-bottom: 1.5rem;
        border: 2px solid #FFD700;
        box-shadow: 0 0 30px rgba(255, 215, 0, 0.15);
        letter-spacing: 2px;
    }
    .main-title span {
        color: #00FF88;
        text-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
    }
    .main-title small {
        font-size: 0.8rem;
        color: #888;
        display: block;
        margin-top: 0.3rem;
        letter-spacing: 1px;
    }
    
    /* Centre all content */
    .stApp {
        max-width: 1400px;
        margin: 0 auto;
    }
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Card style */
    .card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #2a2a4a;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: all 0.3s;
    }
    .card:hover {
        border-color: #FFD700;
        box-shadow: 0 4px 25px rgba(255, 215, 0, 0.1);
    }
    .card-title {
        color: #FFD700;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    /* Metric cards - centre */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
        justify-content: center;
    }
    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #0f0f23);
        padding: 1.2rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #2a2a4a;
        transition: all 0.3s;
        min-width: 150px;
    }
    .metric-card:hover {
        border-color: #FFD700;
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(255, 215, 0, 0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #FFD700;
        font-family: 'Courier New', monospace;
    }
    .metric-label {
        color: #aaa;
        font-size: 0.85rem;
        margin-top: 0.3rem;
    }
    
    /* Sidebar - centre */
    .css-1d391kg, .css-1lcbmhc {
        background: linear-gradient(180deg, #0a0a1a, #1a1a2e);
    }
    .sidebar-title {
        color: #FFD700;
        font-size: 1.4rem;
        font-weight: 700;
        text-align: center;
        padding: 0.8rem 0;
        border-bottom: 2px solid #FFD700;
        margin-bottom: 1.2rem;
        letter-spacing: 1px;
    }
    
    /* Buttons */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #FFD700, #FFA500);
        color: #000;
        font-weight: 700;
        font-size: 1.1rem;
        padding: 0.6rem;
        border-radius: 10px;
        border: none;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 30px rgba(255, 215, 0, 0.3);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #1a1a3e, #0f0f23);
        border-radius: 10px;
        border: 1px solid #2a2a4a;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 1.5rem;
        color: #666;
        font-size: 0.85rem;
        border-top: 1px solid #2a2a4a;
        margin-top: 2rem;
        background: linear-gradient(135deg, #0a0a1a, #1a1a2e);
        border-radius: 10px;
    }
    .footer span {
        color: #FFD700;
        font-weight: 600;
    }
    .footer .heart {
        color: #FF4444;
    }
    
    /* Select boxes centre */
    .stSelectbox, .stMultiselect, .stNumberInput, .stCheckbox {
        width: 100%;
    }
    
    /* Centre all widgets */
    .stSelectbox > div, .stMultiselect > div {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================================
# 🔥 SYMBOL LISTS
# ==========================================================================

# --- NIFTY 200 STOCKS ---
NIFTY_200 = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "HINDUNILVR.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS",
    "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "COALINDIA.NS", "BHARTIARTL.NS",
    "TATACONSUM.NS", "PIDILITIND.NS", "DIVISLAB.NS", "DRREDDY.NS", "GRASIM.NS",
    "JSWSTEEL.NS", "TECHM.NS", "TITAN.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    "BRITANNIA.NS", "HINDALCO.NS", "EICHERMOT.NS", "BAJAJFINSV.NS", "ADANIGREEN.NS",
    "ADANIENT.NS", "VEDL.NS", "TATASTEEL.NS", "JINDALSTEL.NS", "M&M.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "INDUSINDBK.NS", "YESBANK.NS",
    "TATAMOTORS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "AUBANK.NS",
    "MPHASIS.NS", "COFORGE.NS", "LTTS.NS", "PERSISTENT.NS", "ZENSARTECH.NS",
    "CIPLA.NS", "GLENMARK.NS", "AUROPHARMA.NS", "LUPIN.NS", "TORNTPHARM.NS",
    "APOLLOHOSP.NS", "FORTIS.NS", "MAXHEALTH.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS",
    "TVSMOTOR.NS", "ASHOKLEY.NS", "ESCORTS.NS", "BOSCHLTD.NS", "MOTHERSON.NS",
    "BALKRISIND.NS", "APOLLOTYRE.NS", "MRF.NS", "NESTLEIND.NS", "DABUR.NS",
    "MARICO.NS", "GODREJCP.NS", "EMAMILTD.NS", "TATAPOWER.NS", "ADANIPOWER.NS",
    "GAIL.NS", "PETRONET.NS", "IOC.NS", "BPCL.NS", "HINDZINC.NS", "NMDC.NS",
    "SAIL.NS", "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS",
    "SOBHA.NS", "LTFH.NS", "RECLTD.NS", "PFC.NS", "NHPC.NS", "IRCTC.NS",
    "SUNTV.NS", "PVRINOX.NS", "ZEEL.NS", "NETWORK18.NS", "HAL.NS", "BEL.NS",
    "BHEL.NS", "SIEMENS.NS", "ABB.NS", "SUZLON.NS", "TATACHEM.NS", "UPL.NS",
    "PIIND.NS", "ABCAPITAL.NS", "ACC.NS", "ALKEM.NS", "AMBER.NS",
    "ANGELONE.NS", "ASTRAL.NS", "ATUL.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS",
    "BATAINDIA.NS", "BERGEPAINT.NS", "BIOCON.NS", "CADILAHC.NS",
    "CASTROLIND.NS", "CEATLTD.NS", "CENTRALBK.NS", "CHAMBLFERT.NS",
    "CHOLAFIN.NS", "CITYUNION.NS", "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS",
    "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DEEPAKNTR.NS", "DELTACORP.NS",
    "EXIDEIND.NS", "GRANULES.NS", "GSPL.NS", "GUJGASLTD.NS", "HDFCAMC.NS",
    "HONAUT.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS", "IEX.NS",
    "IGL.NS", "INDIGO.NS", "JUBLFOOD.NS", "LICHSGFIN.NS", "M&MFIN.NS",
    "MANAPPURAM.NS", "MCDOWELL-N.NS", "MCX.NS", "MFSL.NS", "MGL.NS",
    "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS",
    "PAGEIND.NS", "PEL.NS", "RAMCOCEM.NS", "SHREECEM.NS", "SRTRANSFIN",
    "TRENT.NS", "UBL.NS", "VOLTAS.NS", "ZYDUSLIFE.NS"
]

# --- NIFTY 500 ADDITIONAL ---
NIFTY_500_ADD = [
    "AARTIIND.NS", "ABBOTINDIA.NS", "ABFRL.NS", "ALKEM.NS", "AMBER.NS",
    "ANGELONE.NS", "ASTRAL.NS", "ATUL.NS", "BALRAMCHIN.NS", "BATAINDIA.NS",
    "BHARATFORG.NS", "BIOCON.NS", "CADILAHC.NS", "CASTROLIND.NS",
    "CEATLTD.NS", "CENTRALBK.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS",
    "CITYUNION.NS", "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS",
    "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DEEPAKNTR.NS",
    "DELTACORP.NS", "EXIDEIND.NS", "GRANULES.NS", "GSPL.NS",
    "GUJGASLTD.NS", "HDFCAMC.NS", "HONAUT.NS", "ICICIGI.NS",
    "ICICIPRULI.NS", "IEX.NS", "IGL.NS", "INDIGO.NS",
    "JUBLFOOD.NS", "LICHSGFIN.NS", "M&MFIN.NS",
    "MANAPPURAM.NS", "MCDOWELL-N.NS", "MFSL.NS", "MGL.NS",
    "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS",
    "NAVINFLUOR.NS", "PAGEIND.NS", "PEL.NS",
    "RAMCOCEM.NS", "SHREECEM.NS", "SRTRANSFIN",
    "TRENT.NS", "UBL.NS", "VOLTAS.NS", "ZYDUSLIFE.NS"
]

# --- FUTURE STOCKS ---
FUTURE_STOCKS = [
    "BANKNIFTY", "NIFTY", "FINNIFTY", "MIDCPNIFTY",
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "ITC", "LT", "AXISBANK", "KOTAKBANK"
]

# --- US 30 (Dow Jones) ---
US_30_TICKERS = [
    "AAPL", "MSFT", "JPM", "V", "JNJ", "WMT", "PG", "UNH",
    "HD", "DIS", "CSCO", "VZ", "NKE", "GS", "CAT", "IBM",
    "MRK", "CVX", "KO", "BA", "MCD", "AXP", "CRM", "AMGN",
    "HON", "DOW", "INTC", "WBA", "TRV", "MMM"
]

# --- NASDAQ 100 ---
NASDAQ_100 = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META",
    "TSLA", "NFLX", "ADBE", "CRM", "ORCL", "CSCO", "INTC",
    "AMD", "QCOM", "TXN", "AVGO", "MU", "PLTR", "SNOW",
    "CRWD", "PANW", "FTNT", "DDOG", "MDB", "TEAM", "NET",
    "NOW", "ADSK", "CDNS", "SNPS", "NXPI", "MCHP", "ADI",
    "MRVL", "ANET", "SMCI", "ON", "LRCX", "KLAC", "AMAT",
    "DELL", "HPQ", "HPE", "NTAP", "STX", "WDC", "TER", "ENTG",
    "V", "MA", "PYPL", "COIN", "BLK", "AXP", "SCHW", "SPGI",
    "JNJ", "PFE", "MRK", "UNH", "ABBV", "LLY", "GILD", "AMGN",
    "VRTX", "REGN", "MRNA", "ISRG", "DHR", "TMO", "ABT", "MDT",
    "SYK", "BSX", "PG", "KO", "PEP", "WMT", "COST", "HD",
    "MCD", "SBUX", "NKE", "DIS", "TGT", "LOW", "XOM", "CVX",
    "COP", "EOG", "OXY", "PSX", "GE", "CAT", "BA", "RTX",
    "LMT", "HON"
]

# --- FOREX (No INR) ---
FOREX_TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", 
    "USDCAD=X", "USDCHF=X", "NZDUSD=X",
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURCAD=X", 
    "EURAUD=X", "EURNZD=X",
    "GBPJPY=X", "GBPCHF=X", "GBPCAD=X", "GBPAUD=X", "GBPNZD=X",
    "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X",
    "AUDCAD=X", "AUDCHF=X", "AUDNZD=X", "CADCHF=X", 
    "NZDCAD=X", "NZDCHF=X",
]

# --- COMMODITIES ---
COMMODITY_TICKERS = [
    "GC=F",    # Gold
    "SI=F",    # Silver
    "HG=F",    # Copper
    "PL=F",    # Platinum
    "PA=F",    # Palladium
    "CL=F",    # Crude Oil WTI
    "BZ=F",    # Brent Crude
    "NG=F",    # Natural Gas
    "RB=F",    # Gasoline
    "HO=F",    # Heating Oil
    "ZC=F",    # Corn
    "ZS=F",    # Soybean
    "ZW=F",    # Wheat
    "ZM=F",    # Soybean Meal
    "ZL=F",    # Soybean Oil
    "CT=F",    # Cotton
    "SB=F",    # Sugar
    "KC=F",    # Coffee
    "CC=F",    # Cocoa
    "LE=F",    # Live Cattle
    "HE=F",    # Lean Hogs
    "GF=F",    # Feeder Cattle
]

# --- CRYPTO ---
CRYPTO_TICKERS = [
    "BTC-USD", "ETH-USD", "USDT-USD", "BNB-USD", "SOL-USD",
    "XRP-USD", "ADA-USD", "DOGE-USD", "TRX-USD", "DOT-USD",
    "MATIC-USD", "SHIB-USD", "LTC-USD", "AVAX-USD", "UNI-USD",
    "LINK-USD", "ATOM-USD", "ETC-USD", "XLM-USD", "BCH-USD",
    "ALGO-USD", "VET-USD", "ICP-USD", "FIL-USD", "EGLD-USD",
    "APT-USD", "ARB-USD", "OP-USD", "SUI-USD", "SEI-USD",
]

# ==========================================================================
# 🔥 MARKET PRESETS
# ==========================================================================

MARKET_PRESETS = {
    "🇮🇳 NIFTY 200": {
        "suffix_hint": "e.g. RELIANCE.NS, TCS.NS",
        "tickers": NIFTY_200,
    },
    "🇮🇳 NIFTY 500": {
        "suffix_hint": "e.g. RELIANCE.NS, TCS.NS",
        "tickers": NIFTY_200 + NIFTY_500_ADD,
    },
    "📈 Futures": {
        "suffix_hint": "e.g. NIFTY, BANKNIFTY",
        "tickers": FUTURE_STOCKS,
    },
    "🇺🇸 US 30 (Dow Jones)": {
        "suffix_hint": "e.g. AAPL, MSFT",
        "tickers": US_30_TICKERS,
    },
    "🇺🇸 NASDAQ 100": {
        "suffix_hint": "e.g. AAPL, MSFT",
        "tickers": NASDAQ_100,
    },
    "💱 Forex (No INR)": {
        "suffix_hint": "e.g. EURUSD=X, GBPJPY=X",
        "tickers": FOREX_TICKERS,
    },
    "🥇 Commodities": {
        "suffix_hint": "e.g. GC=F (Gold), CL=F (Crude)",
        "tickers": COMMODITY_TICKERS,
    },
    "🪙 Crypto": {
        "suffix_hint": "e.g. BTC-USD, ETH-USD",
        "tickers": CRYPTO_TICKERS,
    },
}

# ==========================================================================
# 🔥 TIMEFRAMES
# ==========================================================================

INTERVAL_OPTIONS = [
    "5m", "15m", "30m", "45m", "60m", "75m", "125m",
    "2h", "4h", "5h", "6h", "8h", "10h", "12h", "16h",
    "1d", "1wk"
]

PERIOD_OPTIONS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]

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

# ==========================================================================
# 🔥 NEW LAYOUT - TITLE
# ==========================================================================

st.markdown('<div class="main-title">📊 DEEPAK <span>SUPPLY DEMAND</span> STRATEGY<small>Professional Zone Detection & Alert System</small></div>', unsafe_allow_html=True)

# ==========================================================================
# 🔥 SIDEBAR - CENTRE LAYOUT
# ==========================================================================

with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ SETTINGS</div>', unsafe_allow_html=True)
    
    market = st.selectbox("📊 Market Type", list(MARKET_PRESETS.keys()))
    preset = MARKET_PRESETS[market]
    
    select_all_tickers = st.checkbox("✅ Select ALL tickers", value=False)
    tickers_selected = st.multiselect(
        "📌 Ticker Symbol(s)",
        options=preset["tickers"],
        default=preset["tickers"] if select_all_tickers else preset["tickers"][:1],
        disabled=select_all_tickers,
        help=preset["suffix_hint"],
    )
    
    status_choice = st.multiselect(
        "🎯 Zone Status Filter",
        options=["All", "Fresh Zone", "SL Zone", "Target Zone"],
        default=["All"],
        help="Fresh = abhi tak SL/Target nahi laga. SL Zone = stoploss hit. Target Zone = target hit.",
    )
    
    select_all_intervals = st.checkbox("✅ Select ALL timeframes", value=False)
    intervals_selected = st.multiselect(
        "⏰ Timeframe(s)",
        options=INTERVAL_OPTIONS,
        default=INTERVAL_OPTIONS if select_all_intervals else ["1d"],
        disabled=select_all_intervals,
    )

    if select_all_tickers:
        final_tickers = list(preset["tickers"])
    else:
        final_tickers = list(dict.fromkeys(tickers_selected))
    final_intervals = INTERVAL_OPTIONS if select_all_intervals else intervals_selected

    st.markdown("---")
    
    period = st.selectbox("📅 History Period", PERIOD_OPTIONS, index=4)
    atr_length = st.number_input("📏 ATR Length", min_value=1, value=14)
    atr_multiplier = st.number_input("📐 ATR Multiplier", min_value=0.0, value=0.35, step=0.05)
    rr_target = st.number_input("🎯 Risk:Reward", min_value=0.1, value=3.0, step=0.1)
    pre_entry_mult = st.number_input("🔔 Alert Dist (x ATR)", min_value=0.0, value=1.5, step=0.1)
    base_count_filter = st.selectbox("📊 Base Candle Count", ["All", "1", "2", "3"], index=0)

    st.markdown("---")
    
    telegram_on = st.checkbox("📨 Enable Telegram alerts", value=False)
    if telegram_on:
        bot_token = st.text_input("🤖 Bot Token", type="password")
        chat_id = st.text_input("💬 Chat ID")
        only_latest = st.checkbox("📌 Only latest bar", value=True)
    else:
        bot_token = ""
        chat_id = ""
        only_latest = True

    st.markdown("---")
    
    auto_scan_on = st.checkbox("♻️ Auto-Scan", value=False)
    if auto_scan_on:
        autoscan_interval = st.number_input("⏱️ Interval (sec)", min_value=15, value=60, step=5)
    else:
        autoscan_interval = 60
    
    sound_on = st.checkbox("🔊 Sound on new alert", value=True)
    toast_on = st.checkbox("📳 In-app popup (toast)", value=True)

    if auto_scan_on and not AUTOREFRESH_AVAILABLE:
        st.warning("⚠️ `streamlit-autorefresh` package chahiye.")

    run_btn = st.button("🔄 Fetch & Scan", type="primary", use_container_width=True)

if auto_scan_on and AUTOREFRESH_AVAILABLE:
    st_autorefresh(interval=int(autoscan_interval * 1000), key="autoscan_timer")

# ==========================================================================
# 🔥 FUNCTIONS
# ==========================================================================

def resolve_status_filter(choice_list):
    if not choice_list or "All" in choice_list:
        return set(STATUS_LABELS.values())
    return {STATUS_LABELS[c] for c in choice_list if c in STATUS_LABELS}


@st.cache_data(show_spinner=False)
def get_beep_b64(freq: int = 880, duration: float = 0.3, volume: float = 0.5, rate: int = 44100) -> str:
    n_samples = int(rate * duration)
    buf = io.BytesIO()
    wf = wave.open(buf, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(rate)
    frames = bytearray()
    fade_start = int(n_samples * 0.7)
    for i in range(n_samples):
        t = i / rate
        value = volume * math.sin(2 * math.pi * freq * t)
        fade = 1.0 if i < fade_start else max(0.0, (n_samples - i) / (n_samples - fade_start))
        sample = int(max(-1.0, min(1.0, value * fade)) * 32767)
        frames += struct.pack("<h", sample)
    wf.writeframes(bytes(frames))
    wf.close()
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def play_beep():
    b64 = get_beep_b64()
    st.markdown(
        f'<audio autoplay="true"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(tkr: str, itv: str, per: str) -> pd.DataFrame:
    yf_itv = YF_INTERVAL_MAP_APP.get(itv, itv)
    try:
        df = yf.download(tkr, interval=yf_itv, period=per, progress=False, auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    return df


def fetch_data_smart(tkr: str, itv: str, requested_period: str):
    start_idx = PERIOD_OPTIONS.index(requested_period)
    candidates = [PERIOD_OPTIONS[i] for i in range(start_idx, -1, -1)]
    for cand in candidates:
        df = fetch_data(tkr, itv, cand)
        if not df.empty:
            return df, cand
    return pd.DataFrame(), None

# ==========================================================================
# 🔥 RUN SCAN
# ==========================================================================

st.session_state.setdefault("seen_alert_keys", set())
st.session_state.setdefault("telegram_sent_keys", set())
st.session_state.setdefault("alert_log", [])

trigger_scan = run_btn or auto_scan_on

if trigger_scan:
    if not final_tickers:
        st.error("❌ Kam se kam ek ticker select karein.")
        st.stop()
    if not final_intervals:
        st.error("❌ Kam se kam ek timeframe select karein.")
        st.stop()

    combo_results = {}
    skipped = []
    downgraded = []
    total_combos = len(final_tickers) * len(final_intervals)
    progress = st.progress(0, text="📊 Fetching & scanning...")
    done = 0

    for tkr in final_tickers:
        for itv in final_intervals:
            done += 1
            progress.progress(done / total_combos, text=f"📊 Fetching {tkr} ({itv})...")
            df, period_used = fetch_data_smart(tkr, itv, period)
            if df.empty:
                skipped.append(f"{tkr} [{itv}]")
                continue
            if period_used != period:
                downgraded.append(f"{tkr} [{itv}] → {period_used}")
            result = run_full_pipeline(
                df,
                atr_length=atr_length,
                atr_multiplier=atr_multiplier,
                rr_target=rr_target,
                pre_entry_mult=pre_entry_mult,
                base_count_filter=base_count_filter,
            )
            combo_results[(tkr, itv)] = {"df": df, "result": result, "period_used": period_used}

    progress.empty()

    if not combo_results:
        st.error("❌ Kisi bhi ticker/interval combination me data nahi mila. Symbol check karein.")
        st.stop()

    if downgraded:
        st.info("ℹ️ In combos ke liye chhota period use hua:\n\n" + "\n".join(f"- {x}" for x in downgraded[:10]))
    if skipped:
        st.warning("⚠️ Inme data nahi mila:\n\n" + "\n".join(f"- {x}" for x in skipped[:10]))

    st.session_state["combo_results"] = combo_results
    st.session_state["last_tickers"] = final_tickers
    st.session_state["last_intervals"] = final_intervals
    st.session_state["rr_target"] = rr_target
    st.session_state["last_scan_time"] = dt.datetime.now().strftime("%d-%b-%Y %H:%M:%S")

    collected = []
    for (tkr, itv), data in combo_results.items():
        result = data["result"]
        df = data["df"]
        events = result.events
        if only_latest:
            last_bar = len(df) - 1
            events = [e for e in events if e["bar"] == last_bar]
        for e in events:
            key = alert_key(tkr, itv, e)
            txt = build_alert_text(tkr, itv, e, df, rr_target)
            collected.append({
                "key": key, "ticker": tkr, "interval": itv, "type": e["type"],
                "event": e, "df": df, "text": txt,
            })

    new_for_app = [c for c in collected if c["key"] not in st.session_state["seen_alert_keys"]]
    for c in new_for_app:
        st.session_state["seen_alert_keys"].add(c["key"])

    if new_for_app:
        now_str = dt.datetime.now().strftime("%H:%M:%S")
        log_entries = [
            {"key": c["key"], "ticker": c["ticker"], "interval": c["interval"],
             "type": c["type"], "text": c["text"], "time": now_str}
            for c in new_for_app
        ]
        st.session_state["alert_log"] = (log_entries[::-1] + st.session_state["alert_log"])[:100]

        if toast_on:
            for c in new_for_app[:5]:
                st.toast(
                    f"{ALERT_ICONS.get(c['type'], '🔔')} {c['ticker']} [{c['interval']}] — {c['type'].replace('_', ' ').title()}",
                    icon=ALERT_ICONS.get(c["type"], "🔔"),
                )
        if sound_on:
            play_beep()

    if telegram_on:
        to_send = [c for c in collected if c["key"] not in st.session_state["telegram_sent_keys"]]
        if not bot_token or not chat_id:
            if to_send:
                st.warning("📨 Bot Token / Chat ID missing.")
        for c in to_send:
            chart_bytes = render_zone_chart(c["df"], c["event"], c["ticker"], c["interval"])
            if chart_bytes:
                ok, msg = send_telegram_photo(bot_token, chat_id, chart_bytes, caption=c["text"])
            else:
                ok, msg = send_telegram_message(bot_token, chat_id, c["text"])
            st.session_state["telegram_sent_keys"].add(c["key"])
            if not ok:
                st.warning(f"Telegram ({c['ticker']} [{c['interval']}]): {msg}")

# ==========================================================================
# 🔥 DISPLAY RESULTS - CENTRE LAYOUT
# ==========================================================================

if "combo_results" in st.session_state:
    combo_results = st.session_state["combo_results"]
    allowed_status = resolve_status_filter(status_choice)

    # Status Bar - Centre
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">🕒</div>
            <div class="metric-label">{st.session_state.get('last_scan_time', '-')}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        scan_status = "🟢 Active" if auto_scan_on else "🔴 Manual"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{scan_status}</div>
            <div class="metric-label">Scan Mode</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">📊 {len(combo_results)}</div>
            <div class="metric-label">Total Combos</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Live Alerts
    with st.expander(f"🔔 Live Alerts ({len(st.session_state['alert_log'])})", expanded=bool(st.session_state["alert_log"])):
        if st.session_state["alert_log"]:
            if st.button("🗑️ Clear alerts"):
                st.session_state["alert_log"] = []
                st.rerun()
            for a in st.session_state["alert_log"][:30]:
                icon = ALERT_ICONS.get(a["type"], "🔔")
                st.markdown(f"**{icon} [{a['time']}] {a['ticker']} [{a['interval']}]** — {a['text'].splitlines()[0]}")
        else:
            st.caption("📭 Abhi tak koi alert nahi aaya.")

    combo_keys = list(combo_results.keys())
    combo_labels = [
        f"{t} [{i} · {combo_results[(t, i)]['period_used']}]" for t, i in combo_keys
    ]

    # Summary Metrics - Centre Grid
    total_zones_all = 0
    total_fresh_all = 0
    total_sl_all = 0
    total_tp_all = 0
    for data in combo_results.values():
        for z in data["result"].all_zones:
            total_zones_all += 1
            if z.status == "active":
                total_fresh_all += 1
            elif z.status == "sl":
                total_sl_all += 1
            elif z.status == "tp":
                total_tp_all += 1

    st.markdown("---")
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_zones_all}</div>
            <div class="metric-label">📊 Total Zones</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#FFD700;">🟡 {total_fresh_all}</div>
            <div class="metric-label">Fresh Zones</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#FF4444;">🔴 {total_sl_all}</div>
            <div class="metric-label">SL Hit</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#00FF00;">🟢 {total_tp_all}</div>
            <div class="metric-label">Target Hit</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Chart Section
    st.markdown("---")
    
    chosen_label = st.selectbox("📈 Chart dikhayein:", combo_labels, index=0)
    chosen_key = combo_keys[combo_labels.index(chosen_label)]
    df = combo_results[chosen_key]["df"]
    result = combo_results[chosen_key]["result"]

    zones_filtered = [z for z in result.all_zones if z.status in allowed_status]

    # Stats for selected
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">🎯 {result.sl_count}</div>
            <div class="metric-label">SL Hits</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">✅ {result.tp_count}</div>
            <div class="metric-label">TP Hits</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        total = result.sl_count + result.tp_count
        winrate = (result.tp_count / total * 100) if total else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#00FF88;">📈 {winrate:.1f}%</div>
            <div class="metric-label">Win Rate</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">📊 {len(zones_filtered)}/{len(result.all_zones)}</div>
            <div class="metric-label">Zones Shown</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Chart
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name=chosen_key[0], increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        )
    )

    for z in zones_filtered:
        x0, x1 = df.index[z.start_bar], df.index[min(z.end_bar, len(df) - 1)]
        top = max(z.proximal, z.distal)
        bottom = min(z.proximal, z.distal)
        if z.status == "sl":
            color = "rgba(255,0,0,0.35)"
        elif z.status == "tp":
            color = "rgba(0,200,0,0.35)"
        else:
            color = "rgba(255,0,0,0.12)" if z.is_supply else "rgba(0,255,0,0.12)"

        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=bottom, y1=top,
            fillcolor=color, line=dict(width=1, color=color.replace("0.12", "0.6").replace("0.35", "0.9")),
        )
        fig.add_annotation(
            x=x0, y=top, text=f"{z.pattern_name} {'Supply' if z.is_supply else 'Demand'} [{z.status.upper()}]",
            showarrow=False, yshift=10, font=dict(size=9, color="white"),
            bgcolor="#FF0000" if z.is_supply else "#00AA00",
        )

    fig.update_layout(
        height=650, 
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10),
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        font=dict(color="white"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Zone Log
    st.subheader("📋 Zone Log (all selected)")

    def normalize_ts(ts):
        ts = pd.Timestamp(ts)
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        return ts

    rows = []
    for (tkr, itv), data in combo_results.items():
        r = data["result"]
        d = data["df"]
        for z in r.all_zones:
            if z.status not in allowed_status:
                continue
            rows.append({
                "Ticker": tkr,
                "Interval": itv,
                "Pattern": z.pattern_name,
                "Type": "Supply" if z.is_supply else "Demand",
                "Base Count": z.base_count,
                "Legout Count": z.legout_count,
                "Start": normalize_ts(d.index[z.start_bar]),
                "Proximal": round(z.proximal, 4),
                "Distal": round(z.distal, 4),
                "Target": round(z.target, 4),
                "Status": z.status.upper(),
            })
    if rows:
        zone_df = pd.DataFrame(rows)
        zone_df["Start"] = pd.to_datetime(zone_df["Start"], errors="coerce")
        st.dataframe(
            zone_df.sort_values("Start", ascending=False),
            use_container_width=True, 
            hide_index=True,
        )
    else:
        st.info("ℹ️ Selected filter/timeframe/ticker combination me koi zone nahi mila.")

    # Footer
    st.markdown(f"""
    <div class="footer">
        Made with <span class="heart">❤️</span> by <span>DEEPAK</span> &nbsp;|&nbsp; Supply & Demand Strategy &nbsp;|&nbsp; ⏱️ {dt.datetime.now().strftime('%d-%b-%Y %H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

else:
    st.info("⚙️ Left sidebar me settings choose karke **🔄 Fetch & Scan** dabayein.")
