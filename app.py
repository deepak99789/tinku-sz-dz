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
# 🔥 CUSTOM CSS - NEW LAYOUT
# ==========================================================================

st.markdown("""
<style>
    /* Main title */
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #FFD700;
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #1a1a2e, #16213e, #0f3460);
        border-radius: 10px;
        margin-bottom: 1.5rem;
        border: 2px solid #FFD700;
    }
    .main-title span {
        color: #00FF00;
    }
    /* Card style */
    .card {
        background: #1e1e2f;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #333;
        margin-bottom: 1rem;
    }
    .card-title {
        color: #FFD700;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    /* Metric cards */
    .metric-card {
        background: #1a1a2e;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #333;
        transition: all 0.3s;
    }
    .metric-card:hover {
        border-color: #FFD700;
        transform: scale(1.02);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #FFD700;
    }
    .metric-label {
        color: #aaa;
        font-size: 0.9rem;
    }
    /* Sidebar styling */
    .sidebar-title {
        color: #FFD700;
        font-size: 1.3rem;
        font-weight: 600;
        padding: 0.5rem 0;
        border-bottom: 2px solid #FFD700;
        margin-bottom: 1rem;
    }
    /* Status badge */
    .badge-success {
        background: #00FF00;
        color: #000;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-warning {
        background: #FFA500;
        color: #000;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-danger {
        background: #FF4444;
        color: #fff;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    /* Footer */
    .footer {
        text-align: center;
        padding: 1rem;
        color: #666;
        font-size: 0.8rem;
        border-top: 1px solid #333;
        margin-top: 2rem;
    }
    .footer span {
        color: #FFD700;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================================
# 🔥 SYMBOL LISTS - UPDATED
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

# --- NIFTY 500 STOCKS (Additional 300 stocks - Top ones) ---
NIFTY_500_ADD = [
    "AARTIIND.NS", "ABBOTINDIA.NS", "ABFRL.NS", "ADANIENT.NS", "ADANIGREEN.NS",
    "ADANIPORTS.NS", "ADANIPOWER.NS", "ALKEM.NS", "AMBER.NS", "ANGELONE.NS",
    "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASTRAL.NS", "ATUL.NS",
    "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS",
    "BAJAJFINSV.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BATAINDIA.NS",
    "BEL.NS", "BERGEPAINT.NS", "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS",
    "BIOCON.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "CADILAHC.NS",
    "CANBK.NS", "CASTROLIND.NS", "CENTRALBK.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS",
    "CIPLA.NS", "CITYUNION.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS",
    "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS",
    "DABUR.NS", "DEEPAKNTR.NS", "DELTACORP.NS", "DIVISLAB.NS", "DLF.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "EMAMILTD.NS", "ESCORTS.NS", "EXIDEIND.NS",
    "FEDERALBNK.NS", "FORTIS.NS", "GAIL.NS", "GLENMARK.NS", "GODREJCP.NS",
    "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", "GSPL.NS", "GUJGASLTD.NS",
    "HAL.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "HINDZINC.NS", "HONAUT.NS",
    "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS", "IDFCFIRSTB.NS",
    "IEX.NS", "IGL.NS", "INDIGO.NS", "INDUSINDBK.NS", "INFY.NS",
    "IOC.NS", "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JSWSTEEL.NS",
    "JUBLFOOD.NS", "KOTAKBANK.NS", "L&TFH.NS", "LICHSGFIN.NS", "LT.NS",
    "LTFH.NS", "LTI.NS", "LTTS.NS", "LUPIN.NS", "M&M.NS",
    "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MAXHEALTH.NS",
    "MCDOWELL-N.NS", "MCX.NS", "MFSL.NS", "MGL.NS", "MINDTREE.NS",
    "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS",
    "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS", "NETWORK18.NS", "NHPC.NS",
    "NIITTECH.NS", "NMDC.NS", "NTPC.NS", "OBEROIRLTY.NS", "ONGC.NS",
    "PAGEIND.NS", "PEL.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS",
    "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POWERGRID.NS", "PRESTIGE.NS",
    "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS",
    "SAIL.NS", "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SIEMENS.NS",
    "SOBHA.NS", "SRTRANSFIN.NS", "SUNPHARMA.NS", "SUNTV.NS", "SUZLON.NS",
    "TATACHEM.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS",
    "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TRENT.NS",
    "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS", "UNIONBANK.NS", "UPL.NS",
    "VEDL.NS", "VOLTAS.NS", "WIPRO.NS", "YESBANK.NS", "ZEEL.NS",
    "ZENSARTECH.NS", "ZYDUSLIFE.NS"
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

# --- FOREX (INR pairs removed) ---
FOREX_TICKERS = [
    # Major Pairs
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", 
    "USDCAD=X", "USDCHF=X", "NZDUSD=X",
    # Minor Pairs - Euro Crosses
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURCAD=X", 
    "EURAUD=X", "EURNZD=X",
    # Minor Pairs - Pound Crosses
    "GBPJPY=X", "GBPCHF=X", "GBPCAD=X", "GBPAUD=X", "GBPNZD=X",
    # Minor Pairs - Yen Crosses
    "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X",
    # Minor Pairs - Other Crosses
    "AUDCAD=X", "AUDCHF=X", "AUDNZD=X", "CADCHF=X", 
    "NZDCAD=X", "NZDCHF=X",
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

st.markdown('<div class="main-title">📊 DEEPAK <span>SUPPLY DEMAND</span> STRATEGY</div>', unsafe_allow_html=True)

# ==========================================================================
# 🔥 SIDEBAR - NEW LAYOUT
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
# 🔥 DISPLAY RESULTS - NEW LAYOUT
# ==========================================================================

if "combo_results" in st.session_state:
    combo_results = st.session_state["combo_results"]
    allowed_status = resolve_status_filter(status_choice)

    # Status Bar
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">🕒 {st.session_state.get('last_scan_time', '-')}</div>
            <div class="metric-label">Last Scan</div>
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

    # Summary Metrics
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

    # Chart Section
    st.markdown("---")
    
    chosen_label = st.selectbox("📈 Chart dikhayein:", combo_labels, index=0)
    chosen_key = combo_keys[combo_labels.index(chosen_label)]
    df = combo_results[chosen_key]["df"]
    result = combo_results[chosen_key]["result"]

    zones_filtered = [z for z in result.all_zones if z.status in allowed_status]

    # Stats for selected
    st.markdown("""
    <div style="display:flex; gap:1rem; flex-wrap:wrap; margin:1rem 0;">
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎯 SL Hits", result.sl_count)
    col2.metric("✅ TP Hits", result.tp_count)
    total = result.sl_count + result.tp_count
    winrate = (result.tp_count / total * 100) if total else 0
    col3.metric("📈 Win Rate", f"{winrate:.1f}%")
    col4.metric("📊 Zones Shown", f"{len(zones_filtered)} / {len(result.all_zones)}")

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
        Made with ❤️ by <span>DEEPAK</span> | Supply & Demand Strategy | ⏱️ {dt.datetime.now().strftime('%d-%b-%Y %H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

else:
    st.info("⚙️ Left sidebar me settings choose karke **🔄 Fetch & Scan** dabayein.")
