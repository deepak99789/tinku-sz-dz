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
import time

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS

st.set_page_config(page_title="Demand & Supply Dashboard", layout="wide")

# ==========================================================================
# 🔥 SUPPORTED YFINANCE TIMEFRAMES (REAL DATA)
# ==========================================================================

INTERVAL_OPTIONS = [
    "5m", "15m", "30m", "60m", "90m",
    "1d", "5d", "1wk", "1mo", "3mo"
]

PERIOD_OPTIONS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]

YF_INTERVAL_MAP_APP = {
    "5m": "5m", "15m": "15m", "30m": "30m",
    "60m": "60m", "90m": "90m",
    "1d": "1d", "5d": "5d",
    "1wk": "1wk", "1mo": "1mo", "3mo": "3mo"
}

PERIOD_BY_INTERVAL = {
    "5m": "1mo", "15m": "1mo", "30m": "1mo",
    "60m": "1mo", "90m": "1mo",
    "1d": "5y", "5d": "5y",
    "1wk": "10y", "1mo": "10y", "3mo": "10y",
}

STATUS_LABELS = {
    "Fresh Zone": "active",
    "SL Zone": "sl",
    "Target Zone": "tp",
}

MARKET_PRESETS = {
    "🇮🇳 NIFTY 500": {
        "suffix_hint": "e.g. RELIANCE.NS, TCS.NS",
        "tickers": [
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
            "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "AUBANK.NS",
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
            "PIIND.NS", "SRTRANSFIN", "TRENT.NS", "UBL.NS", "VOLTAS.NS", "ZYDUSLIFE.NS",
            "ABCAPITAL.NS", "ACC.NS", "ALKEM.NS", "AMBER.NS", "ANGELONE.NS",
            "ASTRAL.NS", "ATUL.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BATAINDIA.NS",
            "BERGEPAINT.NS", "BIOCON.NS", "CADILAHC.NS", "CASTROLIND.NS", "CEATLTD.NS",
            "CENTRALBK.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS", "CITYUNION.NS", "COLPAL.NS",
            "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS",
            "DEEPAKNTR.NS", "DELTACORP.NS", "EXIDEIND.NS", "GRANULES.NS", "GSPL.NS",
            "GUJGASLTD.NS", "HDFCAMC.NS", "HONAUT.NS", "ICICIGI.NS", "ICICIPRULI.NS",
            "IDEA.NS", "IEX.NS", "IGL.NS", "INDIGO.NS", "JUBLFOOD.NS", "LICHSGFIN.NS",
            "M&MFIN.NS", "MANAPPURAM.NS", "MCDOWELL-N.NS", "MCX.NS", "MFSL.NS", "MGL.NS",
            "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "PAGEIND.NS",
            "PEL.NS", "RAMCOCEM.NS", "SHREECEM.NS"
        ],
    },
    "🇺🇸 US Stocks / Index": {
        "suffix_hint": "e.g. AAPL, TSLA, ^GSPC, ^DJI",
        "tickers": [
            "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
            "NFLX", "ADBE", "CRM", "ORCL", "IBM", "CSCO", "INTC",
            "AMD", "QCOM", "TXN", "AVGO", "MU",
            "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "PYPL",
            "COIN", "BLK", "AXP", "USB", "PNC", "TFC",
            "JNJ", "PFE", "MRK", "UNH", "CVS", "ABBV", "LLY",
            "GILD", "BIIB", "AMGN", "VRTX", "REGN", "MRNA",
            "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "SBUX",
            "NKE", "DIS", "UPS", "FDX", "TGT", "LOW", "KHC",
            "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "VLO",
            "GE", "CAT", "BA", "RTX", "LMT", "HON", "UNP", "DHR",
            "T", "VZ", "TMUS", "CMCSA",
            "^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX",
        ],
    },
    "💱 Forex": {
        "suffix_hint": "e.g. EURUSD=X, GBPJPY=X",
        "tickers": [
            "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", 
            "USDCAD=X", "USDCHF=X", "NZDUSD=X",
            "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURCAD=X", 
            "EURAUD=X", "EURNZD=X",
            "GBPJPY=X", "GBPCHF=X", "GBPCAD=X", "GBPAUD=X", "GBPNZD=X",
            "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X",
            "AUDCAD=X", "AUDCHF=X", "AUDNZD=X", "CADCHF=X", 
            "NZDCAD=X", "NZDCHF=X",
        ],
    },
    "🥇 Commodity": {
        "suffix_hint": "e.g. GC=F (Gold), CL=F (Crude)",
        "tickers": [
            "GC=F", "SI=F", "HG=F", "PL=F", "PA=F",
            "CL=F", "BZ=F", "NG=F", "RB=F", "HO=F",
            "ZC=F", "ZS=F", "ZW=F", "ZM=F", "ZL=F",
            "CT=F", "SB=F", "KC=F", "CC=F",
            "LE=F", "HE=F", "GF=F",
        ],
    },
    "🪙 Crypto": {
        "suffix_hint": "e.g. BTC-USD",
        "tickers": ["BTC-USD"],
    },
}

st.title("📊 Demand & Supply Dashboard")
st.caption("Python/Streamlit port of the Pine Script RBD / DBD / DBR / RBR zone-detection indicator")

# ==========================================================================
# ⚙️ SETTINGS
# ==========================================================================
st.markdown("## ⚙️ Settings")
settings_box = st.container(border=True)

with settings_box:
    row1_c1, row1_c2, row1_c3, row1_c4 = st.columns([1.2, 1.6, 1.4, 1])
    with row1_c1:
        market = st.selectbox("Market Type", list(MARKET_PRESETS.keys()))
        preset = MARKET_PRESETS[market]
    with row1_c2:
        select_all_tickers = st.checkbox("✅ Select ALL tickers", value=False)
        tickers_selected = st.multiselect(
            "Ticker Symbol(s)",
            options=preset["tickers"],
            default=preset["tickers"] if select_all_tickers else preset["tickers"][:1],
            disabled=select_all_tickers,
            help=preset["suffix_hint"],
        )
    with row1_c3:
        status_choice = st.multiselect(
            "🎯 Zone Status Filter",
            options=["All", "Fresh Zone", "SL Zone", "Target Zone"],
            default=["All"],
        )
    with row1_c4:
        select_all_intervals = st.checkbox("✅ Select ALL timeframes", value=False)
        intervals_selected = st.multiselect(
            "Timeframe(s)",
            options=INTERVAL_OPTIONS,
            default=INTERVAL_OPTIONS if select_all_intervals else ["1d"],
            disabled=select_all_intervals,
        )

    if select_all_tickers:
        final_tickers = list(preset["tickers"])
    else:
        final_tickers = list(dict.fromkeys(tickers_selected))
    final_intervals = INTERVAL_OPTIONS if select_all_intervals else intervals_selected

    st.divider()

    row2_c1, row2_c2, row2_c3, row2_c4, row2_c5, row2_c6 = st.columns([1, 1, 1, 1, 1, 1.4])
    with row2_c1:
        period = st.selectbox("History Period", PERIOD_OPTIONS, index=4)
    with row2_c2:
        atr_length = st.number_input("ATR Length", min_value=1, value=14)
    with row2_c3:
        atr_multiplier = st.number_input("ATR Multiplier", min_value=0.0, value=0.35, step=0.05)
    with row2_c4:
        rr_target = st.number_input("Risk:Reward", min_value=0.1, value=3.0, step=0.1)
    with row2_c5:
        pre_entry_mult = st.number_input("Alert Dist (x ATR)", min_value=0.0, value=1.5, step=0.1)
    with row2_c6:
        base_count_filter = st.selectbox("Base Candle Count", ["All", "1", "2", "3"], index=0)

    st.divider()

    row3_c1, row3_c2, row3_c3, row3_c4 = st.columns([1, 1.3, 1.3, 1])
    with row3_c1:
        telegram_on = st.checkbox("📨 Enable Telegram alerts", value=False)
    with row3_c2:
        bot_token = st.text_input("Bot Token", type="password") if telegram_on else ""
    with row3_c3:
        chat_id = st.text_input("Chat ID") if telegram_on else ""
    with row3_c4:
        only_latest = st.checkbox("Only latest bar", value=True) if telegram_on else True

    st.divider()

    st.markdown("**🔔 Alert System**")
    row4_c1, row4_c2, row4_c3, row4_c4 = st.columns([1.3, 1, 1, 1])
    with row4_c1:
        auto_scan_on = st.checkbox("♻️ Auto-Scan", value=False)
    with row4_c2:
        autoscan_interval = st.number_input("Interval (sec)", min_value=15, value=60, step=5, disabled=not auto_scan_on)
    with row4_c3:
        sound_on = st.checkbox("🔊 Sound on new alert", value=True)
    with row4_c4:
        toast_on = st.checkbox("📳 In-app popup (toast)", value=True)

    if auto_scan_on and not AUTOREFRESH_AVAILABLE:
        st.warning("⚠️ `streamlit-autorefresh` package required for auto-scan.")

    run_btn = st.button("🔄 Fetch & Scan", type="primary", use_container_width=True)

if auto_scan_on and AUTOREFRESH_AVAILABLE:
    st_autorefresh(interval=int(autoscan_interval * 1000), key="autoscan_timer")


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
# RUN SCAN
# ==========================================================================
st.session_state.setdefault("seen_alert_keys", set())
st.session_state.setdefault("telegram_sent_keys", set())
st.session_state.setdefault("alert_log", [])

trigger_scan = run_btn or auto_scan_on

if trigger_scan:
    if not final_tickers:
        st.error("Kam se kam ek ticker select karein.")
        st.stop()
    if not final_intervals:
        st.error("Kam se kam ek timeframe select karein.")
        st.stop()

    combo_results = {}
    skipped = []
    downgraded = []
    total_combos = len(final_tickers) * len(final_intervals)
    progress = st.progress(0, text="Fetching & scanning...")
    done = 0

    for tkr in final_tickers:
        for itv in final_intervals:
            done += 1
            progress.progress(done / total_combos, text=f"Fetching {tkr} ({itv})...")
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
        st.error("Kisi bhi ticker/interval combination me data nahi mila.")
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
        is_fresh_only = "Fresh Zone" in status_choice and "All" not in status_choice
        
        if is_fresh_only:
            to_send = [
                c for c in collected 
                if c["key"] not in st.session_state["telegram_sent_keys"] 
                and c["event"]["zone"].status == "active"
            ]
            if to_send:
                st.info(f"📨 Sirf {len(to_send)} Fresh Zones Telegram par bheje ja rahe hain...")
        else:
            to_send = [c for c in collected if c["key"] not in st.session_state["telegram_sent_keys"]]
            if to_send:
                st.info(f"📨 {len(to_send)} alerts (All Zones) Telegram par bheje ja rahe hain...")
        
        if not bot_token or not chat_id:
            if to_send:
                st.warning("📨 Bot Token / Chat ID missing.")
        
        sent_count = 0
        for c in to_send:
            if sent_count > 0 and sent_count % 3 == 0:
                st.info(f"⏱️ Rate limit: Waiting 2 seconds... ({sent_count} messages sent)")
                time.sleep(2)
            
            chart_bytes = render_zone_chart(c["df"], c["event"], c["ticker"], c["interval"])
            if chart_bytes:
                ok, msg = send_telegram_photo(bot_token, chat_id, chart_bytes, caption=c["text"])
            else:
                ok, msg = send_telegram_message(bot_token, chat_id, c["text"])
            
            st.session_state["telegram_sent_keys"].add(c["key"])
            if ok:
                sent_count += 1
                zone_status = c["event"]["zone"].status
                status_text = "Fresh" if zone_status == "active" else zone_status.upper()
                st.success(f"✅ Telegram sent: {c['ticker']} [{c['interval']}] - {c['type']} ({status_text})")
            else:
                st.warning(f"Telegram ({c['ticker']} [{c['interval']}]): {msg}")


# ==========================================================================
# DISPLAY RESULTS
# ==========================================================================
if "combo_results" in st.session_state:
    combo_results = st.session_state["combo_results"]
    allowed_status = resolve_status_filter(status_choice)

    status_line = f"🕒 Last scan: {st.session_state.get('last_scan_time', '-')}"
    if auto_scan_on:
        status_line += f"  |  ♻️ Auto-Scan ON (har {int(autoscan_interval)}s me refresh hoga)"
    st.caption(status_line)

    with st.expander(f"🔔 Live Alerts ({len(st.session_state['alert_log'])})", expanded=bool(st.session_state["alert_log"])):
        if st.session_state["alert_log"]:
            if st.button("🗑️ Clear alerts"):
                st.session_state["alert_log"] = []
                st.rerun()
            for a in st.session_state["alert_log"][:30]:
                icon = ALERT_ICONS.get(a["type"], "🔔")
                st.markdown(f"**{icon} [{a['time']}] {a['ticker']} [{a['interval']}]** — {a['text'].splitlines()[0]}")
        else:
            st.caption("Abhi tak koi alert nahi aaya.")

    combo_keys = list(combo_results.keys())
    combo_labels = [
        f"{t} [{i} · {combo_results[(t, i)]['period_used']}]" for t, i in combo_keys
    ]

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

    st.divider()
    st.markdown("### 📋 Final Summary — sab tickers & timeframes")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Zones Detected", total_zones_all)
    s2.metric("🟡 Fresh Zones", total_fresh_all)
    s3.metric("🔴 SL Hit", total_sl_all)
    s4.metric("🟢 Target Hit", total_tp_all)

    dc = st.container()
    with dc:
        st.divider()
        chosen_label = st.selectbox("📈 Chart dikhayein:", combo_labels, index=0)
        chosen_key = combo_keys[combo_labels.index(chosen_label)]
        df = combo_results[chosen_key]["df"]
        result = combo_results[chosen_key]["result"]
        ticker = chosen_key[0]

        zones_filtered = [z for z in result.all_zones if z.status in allowed_status]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SL Hits", result.sl_count)
        c2.metric("TP Hits", result.tp_count)
        total = result.sl_count + result.tp_count
        winrate = (result.tp_count / total * 100) if total else 0
        c3.metric("Win Rate", f"{winrate:.1f}%")
        c4.metric("Zones Shown", f"{len(zones_filtered)} / {len(result.all_zones)}")

        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                name=ticker, increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
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
            height=700, xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=30, b=10),
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Zone Log (all selected tickers & timeframes)")

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
                   
