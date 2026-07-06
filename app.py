"""
app.py - Demand & Supply Dashboard (Streamlit port of the Pine Script indicator)

Works across:
    - Indian stocks (NSE/BSE)   e.g. RELIANCE.NS, TCS.BO
    - US stocks / indices       e.g. AAPL, TSLA, ^GSPC
    - Forex                    e.g. EURUSD=X, USDINR=X
    - Commodities               e.g. GC=F (Gold), CL=F (Crude), SI=F (Silver)
    - Crypto                    e.g. BTC-USD, ETH-USD

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import io
import os
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
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS, EVENT_STATUS_MAP

st.set_page_config(page_title="Demand & Supply Dashboard", layout="wide")


def _telegram_default(name: str) -> str:
    """TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env var ya st.secrets se default
    value uthata hai. Isse deploy karte waqt ek baar set kar dene ke baad
    UI me Bot Token / Chat ID khud-b-khud bhara aata hai - dobara type
    karne ki zaroorat nahi padti."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, "")

# --------------------------------------------------------------------------
# Presets - starter ticker lists per market. Add jitne chaho, yahin list
# me daal dena (baad me neeche "Extra tickers" box se bhi add kar sakte ho).
# --------------------------------------------------------------------------
MARKET_PRESETS = {
    "Indian Stocks (NSE)": {
        "suffix_hint": "e.g. RELIANCE.NS, TCS.NS, INFY.NS",
        "tickers": [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
            "BAJFINANCE.NS", "HINDUNILVR.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS",
        ],
    },
    "Indian Stocks (BSE)": {
        "suffix_hint": "e.g. RELIANCE.BO, TCS.BO",
        "tickers": ["RELIANCE.BO", "TCS.BO", "INFY.BO", "HDFCBANK.BO", "SBIN.BO"],
    },
    "US Stocks / Index": {
        "suffix_hint": "e.g. AAPL, TSLA, ^GSPC, ^DJI",
        "tickers": [
            "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
            "^GSPC", "^DJI", "^IXIC",
        ],
    },
    "Forex": {
        "suffix_hint": "e.g. EURUSD=X, USDINR=X, GBPJPY=X",
        "tickers": ["EURUSD=X", "USDINR=X", "GBPJPY=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"],
    },
    "Commodity": {
        "suffix_hint": "e.g. GC=F (Gold), CL=F (Crude), SI=F (Silver)",
        "tickers": ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F"],
    },
    "Crypto": {
        "suffix_hint": "e.g. BTC-USD, ETH-USD, SOL-USD",
        "tickers": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    },
}

INTERVAL_OPTIONS = ["5m", "15m", "30m", "1h", "1d", "1wk"]
PERIOD_OPTIONS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]
PERIOD_BY_INTERVAL = {
    "5m": "1mo", "15m": "1mo", "30m": "1mo",
    "1h": "2y", "1d": "5y", "1wk": "10y",
}

STATUS_LABELS = {
    "Fresh Zone": "active",
    "SL Zone": "sl",
    "Target Zone": "tp",
}
# (EVENT_STATUS_MAP ab alert_common.py se import hota hai - taaki manual
# Streamlit app aur 24x7 alert_bot.py dono same rule follow karein.)

st.title("📊 Demand & Supply Dashboard")
st.caption("Python/Streamlit port of the Pine Script RBD / DBD / DBR / RBR zone-detection indicator")

# ==========================================================================
# ⚙️ SETTINGS - centered in the main page (no sidebar)
# ==========================================================================
st.markdown("## ⚙️ Settings")
settings_box = st.container(border=True)

with settings_box:
    # ---- Row 1: Market / Ticker / Zone Status Filter / Timeframe ----
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
        select_all_status = st.checkbox("✅ All zone statuses", value=True)
        status_choice = st.multiselect(
            "🎯 Zone Status Filter",
            options=["Fresh Zone", "SL Zone", "Target Zone"],
            default=["Fresh Zone", "SL Zone", "Target Zone"] if select_all_status else [],
            disabled=select_all_status,
            help=(
                "Fresh = abhi tak SL/Target nahi laga. SL Zone = stoploss hit. "
                "Target Zone = target hit. Sirf ek status (jaise Fresh) ke "
                "alert chahiye to pehle upar wala '✅ All zone statuses' "
                "checkbox OFF karo, phir neeche sirf 'Fresh Zone' select karo."
            ),
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

    # ---- Row 2: Period / Pattern rules / Base filter ----
    row2_c1, row2_c2, row2_c3, row2_c4, row2_c5, row2_c6 = st.columns([1, 1, 1, 1, 1, 1.4])
    with row2_c1:
        period = st.selectbox(
            "History Period",
            PERIOD_OPTIONS,
            index=PERIOD_OPTIONS.index("1y") if "1y" in PERIOD_OPTIONS else 0,
            help="Intraday (5m/15m/30m) me Yahoo Finance khud history limit karta hai (~60 din).",
        )
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

    # ---- Row 3: Telegram alerts ----
    # Bot Token / Chat ID ab st.session_state me (key=) save hote hain, isliye
    # checkbox on/off karne par ya Auto-Scan ke rerun par bhi value udti nahi -
    # ek baar daal do, session bhar yaad rahega. Agar TELEGRAM_BOT_TOKEN /
    # TELEGRAM_CHAT_ID env var (ya st.secrets) me pehle se set hai, to fields
    # apne aap bhare hue aayenge.
    st.session_state.setdefault("bot_token", _telegram_default("TELEGRAM_BOT_TOKEN"))
    st.session_state.setdefault("chat_id", _telegram_default("TELEGRAM_CHAT_ID"))

    row3_c1, row3_c2, row3_c3, row3_c4 = st.columns([1, 1.3, 1.3, 1])
    with row3_c1:
        telegram_on = st.checkbox("📨 Enable Telegram alerts", value=False)
    with row3_c2:
        bot_token = st.text_input("Bot Token", type="password", key="bot_token", disabled=not telegram_on)
    with row3_c3:
        chat_id = st.text_input("Chat ID", key="chat_id", disabled=not telegram_on)
    with row3_c4:
        only_latest = st.checkbox("Only latest bar", value=True) if telegram_on else True

    st.divider()

    # ---- Row 4: Auto-Scan + In-app alerts ----
    st.markdown("**🔔 Alert System**")
    row4_c1, row4_c2, row4_c3, row4_c4 = st.columns([1.3, 1, 1, 1])
    with row4_c1:
        auto_scan_on = st.checkbox("♻️ Auto-Scan (khud-b-khud refresh)", value=False)
    with row4_c2:
        autoscan_interval = st.number_input(
            "Interval (sec)", min_value=15, value=60, step=5, disabled=not auto_scan_on
        )
    with row4_c3:
        sound_on = st.checkbox("🔊 Sound on new alert", value=True)
    with row4_c4:
        toast_on = st.checkbox("📳 In-app popup (toast)", value=True)

    if auto_scan_on and not AUTOREFRESH_AVAILABLE:
        st.warning(
            "⚠️ Auto-Scan ke liye `streamlit-autorefresh` package chahiye. "
            "requirements.txt me `streamlit-autorefresh` add karke app ko re-deploy karein."
        )

    run_btn = st.button("🔄 Fetch & Scan", type="primary", use_container_width=True)

# Auto-refresh timer (fires a rerun every N seconds when Auto-Scan is ON)
if auto_scan_on and AUTOREFRESH_AVAILABLE:
    st_autorefresh(interval=int(autoscan_interval * 1000), key="autoscan_timer")


def resolve_status_filter(choice_list):
    """Khaali selection => safe default: sab statuses allow karo."""
    if not choice_list:
        return set(STATUS_LABELS.values())
    return {STATUS_LABELS[c] for c in choice_list if c in STATUS_LABELS}


@st.cache_data(show_spinner=False)
def get_beep_b64(freq: int = 880, duration: float = 0.3, volume: float = 0.5, rate: int = 44100) -> str:
    """Ek chhota beep tone generate karta hai (WAV, base64) - koi external
    audio file ki zaroorat nahi, in-app alert sound ke liye use hota hai."""
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
    try:
        df = yf.download(tkr, interval=itv, period=per, progress=False, auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    return df


def fetch_data_smart(tkr: str, itv: str, requested_period: str):
    """
    Intraday intervals (5m/15m/30m/1h) me Yahoo Finance khud limited history
    deta hai (e.g. ~1 mahina). Agar requested period us interval ke liye
    zyada bada hai to Yahoo khaali data deta hai / error deta hai.

    Ye function requested period se shuru karke chhote periods ki taraf
    step-down karta hai jab tak data mil na jaaye - isse "All timeframes"
    select karne par bhi koi bhi combo error nahi dega, jitna data mil
    sakta hai utna dikha dega.
    """
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
st.session_state.setdefault("seen_alert_keys", set())      # in-app log/toast/sound dedup
st.session_state.setdefault("telegram_sent_keys", set())   # Telegram-specific dedup (independent!)
st.session_state.setdefault("alert_log", [])

trigger_scan = run_btn or auto_scan_on

if trigger_scan:
    if not final_tickers:
        st.error("Kam se kam ek ticker select karein (ya 'Select ALL tickers' on karein).")
        st.stop()
    if not final_intervals:
        st.error("Kam se kam ek timeframe select karein (ya 'Select ALL timeframes' on karein).")
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
        st.error("Kisi bhi ticker/interval combination me data nahi mila. Symbol check karein.")
        st.stop()

    if downgraded:
        st.info(
            "ℹ️ Ye combos ke liye intraday data limit ki wajah se chhota period use hua "
            "(available jitna data tha utna le liya gaya):\n\n" + "\n".join(f"- {x}" for x in downgraded)
        )
    if skipped:
        st.warning("⚠️ Inme bilkul data nahi mila, skip kar diya:\n\n" + "\n".join(f"- {x}" for x in skipped))

    st.session_state["combo_results"] = combo_results
    st.session_state["last_tickers"] = final_tickers
    st.session_state["last_intervals"] = final_intervals
    st.session_state["rr_target"] = rr_target
    st.session_state["last_scan_time"] = dt.datetime.now().strftime("%d-%b-%Y %H:%M:%S")

    # ---- Collect ALL current alert-worthy events across all combos ----
    # "Zone Status Filter" (Fresh/SL/Target) jo upar select kiya hai, wahi
    # ab yahan bhi respect hota hai - taaki "Fresh Zone" select karne par
    # Telegram/in-app par SL ya Target hit ka alert na aaye.
    allowed_status_for_alerts = resolve_status_filter(status_choice)
    collected = []
    for (tkr, itv), data in combo_results.items():
        result = data["result"]
        df = data["df"]
        events = result.events
        if only_latest:
            last_bar = len(df) - 1
            events = [e for e in events if e["bar"] == last_bar]
        events = [
            e for e in events
            if EVENT_STATUS_MAP.get(e["type"], "active") in allowed_status_for_alerts
        ]
        for e in events:
            key = alert_key(tkr, itv, e)
            txt = build_alert_text(tkr, itv, e, df, rr_target)
            collected.append({
                "key": key, "ticker": tkr, "interval": itv, "type": e["type"],
                "event": e, "df": df, "text": txt,
            })

    # ---- In-app (log / toast / sound) - dedup independent of Telegram ----
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
            for c in new_for_app[:5]:  # avoid flooding if a big batch fires at once
                st.toast(
                    f"{ALERT_ICONS.get(c['type'], '🔔')} {c['ticker']} [{c['interval']}] — {c['type'].replace('_', ' ').title()}",
                    icon=ALERT_ICONS.get(c["type"], "🔔"),
                )
        if sound_on:
            play_beep()

    # ---- Telegram - dedup INDEPENDENT of in-app log, so enabling Telegram
    # later still delivers alerts that were already shown in-app before ----
    if telegram_on:
        to_send = [c for c in collected if c["key"] not in st.session_state["telegram_sent_keys"]]
        if not bot_token or not chat_id:
            if to_send:
                st.warning("📨 Telegram ON hai lekin Bot Token / Chat ID khaali hai — alert nahi bheja ja saka.")
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
# DISPLAY RESULTS
# ==========================================================================
if "combo_results" in st.session_state:
    combo_results = st.session_state["combo_results"]
    rr_target_display = st.session_state.get("rr_target", 3.0)
    allowed_status = resolve_status_filter(status_choice)

    status_line = f"🕒 Last scan: {st.session_state.get('last_scan_time', '-')}"
    if auto_scan_on:
        status_line += f"  |  ♻️ Auto-Scan ON (har {int(autoscan_interval)}s me refresh hoga)"
    st.caption(status_line)

    # --- Live Alerts panel ---
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

    # --- Overall summary across ALL selected tickers & timeframes ---
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

        # --- Stats row (for the currently charted ticker/timeframe only) ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SL Hits", result.sl_count)
        c2.metric("TP Hits", result.tp_count)
        total = result.sl_count + result.tp_count
        winrate = (result.tp_count / total * 100) if total else 0
        c3.metric("Win Rate", f"{winrate:.1f}%")
        c4.metric("Zones Shown", f"{len(zones_filtered)} / {len(result.all_zones)}")

        # --- Chart ---
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

        # --- Combined Zone Log (across ALL selected tickers/intervals) ---
        st.subheader("Zone Log (all selected tickers & timeframes)")

        def normalize_ts(ts):
            """Alag markets ke timestamps alag timezones me hote hain
            (NSE=IST, US=EST, Crypto=UTC waghera). Ek column me sort karne
            se pehle sabko naive (tz-less) UTC me convert kar dete hain,
            warna pandas mixed-tz Timestamps compare nahi kar pata."""
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
            # Extra safety net: force the whole column into ONE uniform
            # datetime dtype. Even within the same market, yfinance returns
            # intraday candles as tz-aware and daily/weekly as tz-naive -
            # mixing these in one column breaks sort_values otherwise.
            zone_df["Start"] = pd.to_datetime(zone_df["Start"], errors="coerce")
            st.dataframe(
                zone_df.sort_values("Start", ascending=False),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Selected filter/timeframe/ticker combination me koi zone nahi mila.")

else:
    st.info("Upar settings choose karke **🔄 Fetch & Scan** dabayein.")
