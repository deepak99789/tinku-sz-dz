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
    pip install pandas numpy yfinance requests matplotlib
    python alert_bot.py

Production (24x7, PC off): GitHub Actions workflow
(.github/workflows/scan.yml) ise automatically har N minute me chalata hai.
Setup steps SETUP.md me hain.
"""

import os
import sys
import json
import datetime as dt
import logging

import pandas as pd
import yfinance as yf

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS

# ==========================================================================
# ⚙️ CONFIG - apni pasand ke hisaab se yahan edit karo
# ==========================================================================

# 🔥 UPDATED: ALL TIMEFRAMES from 5min to Weekly
INTERVALS = [
    "5m", "15m", "30m", "45m", "60m", "75m", "125m",
    "2h", "4h", "5h", "6h", "8h", "10h", "12h", "16h",
    "1d", "1wk"
]

TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    # jitne chaho utne tickers yahan add kar do (NSE/BSE/US/Forex/Crypto sab chalega)
]

# yfinance interval mapping - some intervals need special handling
YF_INTERVAL_MAP = {
    "5m": "5m", "15m": "15m", "30m": "30m", "45m": "45m",
    "60m": "60m", "75m": "75m", "125m": "125m",
    "2h": "2h", "4h": "4h", "5h": "5h", "6h": "6h",
    "8h": "8h", "10h": "10h", "12h": "12h", "16h": "16h",
    "1d": "1d", "1wk": "1wk"
}

PERIOD = "1mo"                    # requested period - intraday ke liye auto chhota ho jayega agar zaroorat pade
ATR_LENGTH = 14
ATR_MULTIPLIER = 0.35
RR_TARGET = 3.0
PRE_ENTRY_MULT = 1.5
BASE_COUNT_FILTER = "All"         # "All" / "1" / "2" / "3"

# 🔥 FIX: Set to False to get alerts for ALL zones, not just latest bar
ONLY_LATEST_BAR = False            # True = sirf sabse recent candle ka event alert karo

STATE_FILE = "alerted_state.json"
MAX_STATE_KEYS = 5000              # state file ko infinite badhne se rokne ke liye cap

# Logging setup
LOG_FILE = "alert_bot.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==========================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# yfinance intraday history limit ke hisaab se step-down karne ke liye
PERIOD_LADDER = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


def get_yf_interval(itv: str) -> str:
    """Convert custom intervals to yfinance-compatible intervals"""
    return YF_INTERVAL_MAP.get(itv, itv)


def fetch_smart(tkr: str, itv: str, requested_period: str) -> pd.DataFrame:
    """Requested period try karta hai, khaali mile to chhote period pe
    step-down karta hai (jaisa Streamlit app me hota hai)."""
    yf_interval = get_yf_interval(itv)
    
    # yfinance doesn't support all intervals, fallback to 1h for unsupported
    if yf_interval not in ["5m", "15m", "30m", "45m", "1h", "2h", "4h", "1d", "1wk"]:
        logger.warning(f"⚠️ Interval {itv} not directly supported by yfinance, using 1h as fallback")
        yf_interval = "1h"
    
    idx = PERIOD_LADDER.index(requested_period) if requested_period in PERIOD_LADDER else 0
    for cand in [PERIOD_LADDER[i] for i in range(idx, -1, -1)]:
        try:
            logger.info(f"  Fetching {tkr} {itv} (yf: {yf_interval}) with period {cand}")
            df = yf.download(tkr, interval=yf_interval, period=cand, progress=False, auto_adjust=False)
        except Exception as e:
            logger.warning(f"  [warn] {tkr} {itv} {cand}: {e}")
            continue
        if df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        if not df.empty:
            logger.info(f"  ✅ Got {len(df)} candles for {tkr} {itv}")
            return df
    logger.warning(f"  ❌ No data for {tkr} {itv}")
    return pd.DataFrame()


def load_state() -> set:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                return set()
        except Exception as e:
            logger.warning(f"Error loading state: {e}")
            return set()
    return set()


def save_state(keys: set) -> None:
    keys_list = list(keys)[-MAX_STATE_KEYS:]
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(keys_list, f)
        logger.info(f"✅ State saved: {len(keys_list)} keys")
    except Exception as e:
        logger.error(f"Error saving state: {e}")


def send_alert_with_retry(bot_token: str, chat_id: str, text: str, chart_bytes: bytes = None, max_retries: int = 3):
    """Send alert with retry logic"""
    for attempt in range(max_retries):
        try:
            if chart_bytes:
                ok, msg = send_telegram_photo(bot_token, chat_id, chart_bytes, caption=text)
            else:
                ok, msg = send_telegram_message(bot_token, chat_id, text)
            
            if ok:
                return True, msg
            else:
                logger.warning(f"Attempt {attempt+1} failed: {msg}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # Wait before retry
        except Exception as e:
            logger.error(f"Attempt {attempt+1} error: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
    
    return False, "All retries failed"


def main():
    logger.info("=" * 60)
    logger.info(f"🚀 ZONE SCANNER STARTED at {dt.datetime.now()}")
    logger.info("=" * 60)
    
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID environment variables missing.")
        logger.error("   Please set: export TELEGRAM_BOT_TOKEN='your_token'")
        logger.error("   And: export TELEGRAM_CHAT_ID='your_chat_id'")
        sys.exit(1)

    sent_keys = load_state()
    logger.info(f"📂 Loaded {len(sent_keys)} previously alerted keys")
    
    new_count = 0
    total_events = 0
    total_zones = 0

    for tkr in TICKERS:
        for itv in INTERVALS:
            logger.info(f"\n📊 Scanning {tkr} [{itv}]...")
            
            df = fetch_smart(tkr, itv, PERIOD)
            if df.empty:
                logger.warning(f"❌ {tkr} {itv}: No data available")
                continue
            
            try:
                result = run_full_pipeline(
                    df,
                    atr_length=ATR_LENGTH,
                    atr_multiplier=ATR_MULTIPLIER,
                    rr_target=RR_TARGET,
                    pre_entry_mult=PRE_ENTRY_MULT,
                    base_count_filter=BASE_COUNT_FILTER,
                )
            except Exception as e:
                logger.error(f"❌ Error running pipeline for {tkr} {itv}: {e}")
                continue

            events = result.events
            total_events += len(events)
            total_zones += len(result.all_zones)
            
            # Debug: Log what was found
            if events:
                logger.info(f"  🔍 Found {len(events)} events for {tkr} {itv}")
                for e in events:
                    logger.info(f"    - {e['type']} at bar {e['bar']}")
            else:
                logger.info(f"  ℹ️ No events found for {tkr} {itv}")
            
            # Filter if ONLY_LATEST_BAR is True
            if ONLY_LATEST_BAR:
                last_bar = len(df) - 1
                events = [e for e in events if e["bar"] == last_bar]
                if events:
                    logger.info(f"  📌 Filtered to latest bar: {len(events)} events")
            
            # Process each event
            for e in events:
                key = alert_key(tkr, itv, e)
                if key in sent_keys:
                    logger.info(f"  ⏭️ Skipping already sent: {key}")
                    continue
                    
                sent_keys.add(key)
                logger.info(f"  🆕 New alert: {key}")
                
                # Build alert text
                txt = build_alert_text(tkr, itv, e, df, RR_TARGET)
                logger.info(f"  📝 Alert text: {txt[:100]}...")
                
                # Render chart
                chart_bytes = render_zone_chart(df, e, tkr, itv)
                
                # Send with retry
                ok, msg = send_alert_with_retry(BOT_TOKEN, CHAT_ID, txt, chart_bytes)
                
                icon = ALERT_ICONS.get(e["type"], "🔔")
                if ok:
                    logger.info(f"  ✅ {icon} ALERT SENT: {tkr} {itv} {e['type']}")
                else:
                    logger.error(f"  ❌ Failed to send alert: {msg}")
                
                new_count += 1

    # Save state
    save_state(sent_keys)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 SCAN COMPLETE")
    logger.info(f"  • Total tickers: {len(TICKERS)}")
    logger.info(f"  • Total timeframes: {len(INTERVALS)}")
    logger.info(f"  • Total zones found: {total_zones}")
    logger.info(f"  • Total events detected: {total_events}")
    logger.info(f"  • New alerts sent: {new_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
