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

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message

st.set_page_config(page_title="Demand & Supply Dashboard", layout="wide")

MARKET_PRESETS = {
    "Indian Stocks (NSE)": {"suffix_hint": "e.g. RELIANCE.NS, TCS.NS, INFY.NS", "default": "RELIANCE.NS"},
    "US Stocks / Index": {"suffix_hint": "e.g. AAPL, TSLA, ^GSPC, ^DJI", "default": "AAPL"},
    "Forex": {"suffix_hint": "e.g. EURUSD=X, USDINR=X, GBPJPY=X", "default": "EURUSD=X"},
    "Commodity": {"suffix_hint": "e.g. GC=F (Gold), CL=F (Crude), SI=F (Silver)", "default": "GC=F"},
    "Crypto": {"suffix_hint": "e.g. BTC-USD, ETH-USD, SOL-USD", "default": "BTC-USD"},
}

INTERVAL_OPTIONS = ["5m", "15m", "30m", "1h", "1d", "1wk"]
PERIOD_OPTIONS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]
# yfinance limits intraday history (e.g. ~60 days for 5m/15m/30m), so we
# suggest a safe default period per interval - values must exist in PERIOD_OPTIONS
PERIOD_BY_INTERVAL = {
    "5m": "1mo", "15m": "1mo", "30m": "1mo",
    "1h": "2y", "1d": "5y", "1wk": "10y",
}

st.title("📊 Demand & Supply Dashboard")
st.caption("Python/Streamlit port of the Pine Script RBD / DBD / DBR / RBR zone-detection indicator")

with st.sidebar:
    st.header("⚙️ Settings")

    market = st.selectbox("Market Type", list(MARKET_PRESETS.keys()))
    preset = MARKET_PRESETS[market]
    ticker = st.text_input("Ticker Symbol", value=preset["default"], help=preset["suffix_hint"])

    interval = st.selectbox("Candle Interval", INTERVAL_OPTIONS, index=4)
    _default_period = PERIOD_BY_INTERVAL.get(interval, "1y")
    _period_idx = PERIOD_OPTIONS.index(_default_period) if _default_period in PERIOD_OPTIONS else 0
    period = st.selectbox("History Period", PERIOD_OPTIONS, index=_period_idx)

    st.divider()
    st.subheader("Pattern Rules")
    atr_length = st.number_input("ATR Length for Buffer", min_value=1, value=14)
    atr_multiplier = st.number_input("ATR Buffer Multiplier", min_value=0.0, value=0.35, step=0.05)
    rr_target = st.number_input("Risk-to-Reward Target", min_value=0.1, value=3.0, step=0.1)
    pre_entry_mult = st.number_input("Upcoming Alert Distance (x ATR)", min_value=0.0, value=1.5, step=0.1)
    base_count_filter = st.selectbox("Base Candle Count", ["All", "1", "2", "3"], index=0)

    st.divider()
    st.subheader("📨 Telegram Alerts (optional)")
    telegram_on = st.checkbox("Enable Telegram alerts", value=False)
    bot_token = st.text_input("Bot Token", type="password") if telegram_on else ""
    chat_id = st.text_input("Chat ID") if telegram_on else ""
    only_latest = st.checkbox("Only alert on the most recent bar", value=True) if telegram_on else True

    run_btn = st.button("🔄 Fetch & Scan", type="primary", use_container_width=True)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(tkr: str, itv: str, per: str) -> pd.DataFrame:
    df = yf.download(tkr, interval=itv, period=per, progress=False, auto_adjust=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    return df


if run_btn or "last_result" in st.session_state:
    if run_btn:
        with st.spinner(f"Fetching {ticker} ({interval}, {period})..."):
            df = fetch_data(ticker, interval, period)
        if df.empty:
            st.error("Data nahi mila. Ticker symbol ya interval/period combination check karein.")
            st.stop()

        result = run_full_pipeline(
            df,
            atr_length=atr_length,
            atr_multiplier=atr_multiplier,
            rr_target=rr_target,
            pre_entry_mult=pre_entry_mult,
            base_count_filter=base_count_filter,
        )
        st.session_state["last_result"] = result
        st.session_state["last_df"] = df
        st.session_state["last_ticker"] = ticker

        if telegram_on:
            events = result.events
            if only_latest:
                last_bar = len(df) - 1
                events = [e for e in events if e["bar"] == last_bar]
            for e in events:
                z = e["zone"]
                if e["type"] == "zone_found":
                    txt = f"Zone Found ✅\n{ticker} | {z.pattern_name} {'Supply 🔴' if z.is_supply else 'Demand 🟢'}\nProximal: {z.proximal:.4f}"
                elif e["type"] == "sl_hit":
                    txt = f"🚨 STOPLOSS HIT\n{ticker} | {z.pattern_name}"
                elif e["type"] == "tp_hit":
                    txt = f"🎯 TARGET HIT (1:{rr_target:g})\n{ticker} | {z.pattern_name}\nTarget: {z.target:.4f}"
                elif e["type"] == "entered":
                    txt = f"{'🔴 Sell' if z.is_supply else '🟢 Buy'} Zone Triggered\n{ticker} | {z.pattern_name}"
                else:
                    txt = f"🔔 Upcoming Trade\n{ticker} | {z.pattern_name}"
                ok, msg = send_telegram_message(bot_token, chat_id, txt)
                if not ok:
                    st.sidebar.warning(f"Telegram: {msg}")

    result = st.session_state["last_result"]
    df = st.session_state["last_df"]
    ticker = st.session_state["last_ticker"]

    # --- Stats row ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SL Hits", result.sl_count)
    c2.metric("TP Hits", result.tp_count)
    total = result.sl_count + result.tp_count
    winrate = (result.tp_count / total * 100) if total else 0
    c3.metric("Win Rate", f"{winrate:.1f}%")
    c4.metric("Base Filter", base_count_filter)

    # --- Chart ---
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name=ticker, increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        )
    )

    for z in result.all_zones:
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

    # --- Zone table ---
    st.subheader("Zone Log")
    rows = []
    for z in result.all_zones:
        rows.append({
            "Pattern": z.pattern_name,
            "Type": "Supply" if z.is_supply else "Demand",
            "Start": df.index[z.start_bar],
            "Proximal": round(z.proximal, 4),
            "Distal": round(z.distal, 4),
            "Target": round(z.target, 4),
            "Status": z.status.upper(),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values("Start", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Is data range me koi zone detect nahi hua. Base filter ya timeframe try karein.")

else:
    st.info("Sidebar se ticker aur settings choose karke **Fetch & Scan** dabayein.")
