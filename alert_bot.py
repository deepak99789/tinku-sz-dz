"""
alert_bot.py - Standalone 24x7 Zone Alert Bot (NO Streamlit, NO PC needed)

Ye script Streamlit app se ALAG hai. Isse GitHub Actions par schedule karke
chalaya jata hai, isliye aapka PC/laptop band ho tab bhi ye chalta rehta hai
aur naya zone banate hi Telegram par alert bhej deta hai.

Kaise kaam karta hai:
    1. TICKERS / INTERVALS list (neeche CONFIG me) ke saath scan karta hai.
    2. pattern_engine.py ka wahi RBD/DBD/DBR/RBR logic use karta hai jo
       Streamlit app me hai - 100% same rules.
    3. Har run ke baad already-alerted zones "alerted_state.json" me save
       kar deta hai, taaki agli baar SAME zone ka dobara alert na aaye.
    4. Telegram par sirf NAYE events (zone found / entered / SL hit / TP hit)
       bhejta hai.

Run manually (local test):
    export TELEGRAM_BOT_TOKEN="your_bot_token"
    export TELEGRAM_CHAT_ID="your_chat_id"
    pip install pandas numpy yfinance requests
    python alert_bot.py

Production (24x7, PC off): GitHub Actions workflow
(.github/workflows/scan.yml) ise automatically har N minute me chalata hai.
Setup steps SETUP.md me hain.
"""

import os
import sys
import json
import datetime as dt

import pandas as pd
import yfinance as yf

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS, EVENT_STATUS_MAP

# ==========================================================================
# ⚙️ CONFIG - apni pasand ke hisaab se yahan edit karo
# ==========================================================================
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X", "USDCHF=X",
            "EURGBP=X", "EURJPY=X", "EURAUD=X", "EURCAD=X", "EURCHF=X", "EURNZD=X",
            "GBPJPY=X", "GBPAUD=X", "GBPCAD=X", "GBPCHF=X", "GBPNZD=X",
            "AUDJPY=X", "AUDCAD=X", "AUDCHF=X", "AUDNZD=X",
            "CADJPY=X", "CADCHF=X", "NZDJPY=X", "NZDCAD=X", "NZDCHF=X", "CHFJPY=X", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "PEP", "COST",
            "CSCO", "TMUS", "ADBE", "NFLX", "AMD", "CMCSA", "TXN", "QCOM", "INTC", "AMGN",
            "HON", "INTU", "AMAT", "BKNG", "SBUX", "MDLZ", "ISRG", "GILD", "LRCX", "REGN",
            "VRTX", "MU", "ADP", "PANW", "MELI", "SNPS", "CDNS", "KLAC", "CSX", "MAR",
            "ORLY", "ASML", "CTAS", "NXPI", "WDAY", "MNST", "ROP", "LULU", "ADSK", "CPRT",
            "AEP", "KDP", "MCHP", "ODFL", "PAYX", "PCAR", "DXCM", "CHTR", "MRVL", "LNT",
            "AZN", "EXC", "IDXX", "MSI", "CTSH", "FTNT", "GFL", "TEAM", "BKR", "DDOG",
            "PDD", "CEG", "GEHC", "ROST", "FAST", "VRSK", "BILI", "ANSS", "SIRI", "ALGN",
            "EA", "ILMN", "WBD", "MDB", "FANG", "TTWO", "OKTA", "SPLK", "DASH", "ZS",
            "CRWD", "COGN", "MSTR", "HOOD", "ARM", "PLTR", "SMCI", "APP",
    # jitne chaho utne tickers yahan add kar do (NSE/BSE/US/Forex/Crypto sab chalega)
]

INTERVALS = ["15m", "1h", "1d"]   # jo bhi timeframes track karne hain

PERIOD = "1mo"                    # requested period - intraday ke liye auto chhota ho jayega agar zaroorat pade
ATR_LENGTH = 14
ATR_MULTIPLIER = 0.35
RR_TARGET = 3.0
PRE_ENTRY_MULT = 1.5
BASE_COUNT_FILTER = "All"         # "All" / "1" / "2" / "3"
ONLY_LATEST_BAR = True            # True = sirf sabse recent candle ka event alert karo (live monitoring ke liye best)

# Kaunsi zone-status ke alert Telegram par chahiye - ye 24x7 bot Streamlit
# app se ALAG/independent chalta hai, isliye Streamlit ka "Zone Status Filter"
# isko cover nahi karta - yahan alag se set karna padega.
#   "active" = Fresh zone (zone_found / entered)
#   "sl"     = Stoploss hit
#   "tp"     = Target hit
# Sirf Fresh Zone alerts chahiye to: ALERT_STATUSES = ["active"]
ALERT_STATUSES = ["active"]

STATE_FILE = "alerted_state.json"
MAX_STATE_KEYS = 5000              # state file ko infinite badhne se rokne ke liye cap
# ==========================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# yfinance intraday history limit ke hisaab se step-down karne ke liye
PERIOD_LADDER = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


def fetch_smart(tkr: str, itv: str, requested_period: str) -> pd.DataFrame:
    """Requested period try karta hai, khaali mile to chhote period pe
    step-down karta hai (jaisa Streamlit app me hota hai)."""
    idx = PERIOD_LADDER.index(requested_period) if requested_period in PERIOD_LADDER else 0
    for cand in [PERIOD_LADDER[i] for i in range(idx, -1, -1)]:
        try:
            df = yf.download(tkr, interval=itv, period=cand, progress=False, auto_adjust=False)
        except Exception as e:
            print(f"  [warn] {tkr} {itv} {cand}: {e}")
            continue
        if df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        if not df.empty:
            return df
    return pd.DataFrame()


def load_state() -> set:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_state(keys: set) -> None:
    keys = list(keys)[-MAX_STATE_KEYS:]
    with open(STATE_FILE, "w") as f:
        json.dump(keys, f)


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID environment variables missing.")
        sys.exit(1)

    sent_keys = load_state()
    new_count = 0
    print(f"=== Scan started {dt.datetime.now()} ===")

    for tkr in TICKERS:
        for itv in INTERVALS:
            df = fetch_smart(tkr, itv, PERIOD)
            if df.empty:
                print(f"[skip] {tkr} {itv}: no data")
                continue

            result = run_full_pipeline(
                df,
                atr_length=ATR_LENGTH,
                atr_multiplier=ATR_MULTIPLIER,
                rr_target=RR_TARGET,
                pre_entry_mult=PRE_ENTRY_MULT,
                base_count_filter=BASE_COUNT_FILTER,
            )

            events = result.events
            if ONLY_LATEST_BAR:
                last_bar = len(df) - 1
                events = [e for e in events if e["bar"] == last_bar]
            events = [e for e in events if EVENT_STATUS_MAP.get(e["type"], "active") in ALERT_STATUSES]

            for e in events:
                key = alert_key(tkr, itv, e)
                if key in sent_keys:
                    continue  # already alerted before -> skip (no duplicate)
                sent_keys.add(key)
                txt = build_alert_text(tkr, itv, e, df, RR_TARGET)
                chart_bytes = render_zone_chart(df, e, tkr, itv)
                if chart_bytes:
                    ok, msg = send_telegram_photo(BOT_TOKEN, CHAT_ID, chart_bytes, caption=txt)
                else:
                    ok, msg = send_telegram_message(BOT_TOKEN, CHAT_ID, txt)
                icon = ALERT_ICONS.get(e["type"], "🔔")
                print(f"[alert] {icon} {tkr} {itv} {e['type']} -> sent={ok} {msg}")
                new_count += 1

    save_state(sent_keys)
    print(f"=== Done. {new_count} new alert(s) sent. ===")


if __name__ == "__main__":
    main()
