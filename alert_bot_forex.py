"""
alert_bot_forex.py - 💱 Forex + Commodity + Crypto + Indices 24x7 Alert Bot
REAL DATA - Supported yfinance timeframes
"""

import os
import sys
import json
import datetime as dt
import logging
import time

import pandas as pd
import yfinance as yf

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS

# ==========================================================================
# ⚙️ CONFIG - SUPPORTED TIMEFRAMES (REAL DATA)
# ==========================================================================

INTERVALS = [
    "5m", "15m", "30m", "60m", "90m",
    "1d", "5d", "1wk", "1mo", "3mo"
]

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

COMMODITY_TICKERS = ["GC=F", "SI=F"]
CRYPTO_TICKERS = ["BTC-USD"]
INDICES_TICKERS = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^GDAXI", "^N225"]

TICKERS = FOREX_TICKERS + COMMODITY_TICKERS + CRYPTO_TICKERS + INDICES_TICKERS

YF_INTERVAL_MAP = {
    "5m": "5m", "15m": "15m", "30m": "30m",
    "60m": "60m", "90m": "90m",
    "1d": "1d", "5d": "5d", "1wk": "1wk", "1mo": "1mo", "3mo": "3mo"
}

PERIOD = "1mo"
ATR_LENGTH = 14
ATR_MULTIPLIER = 0.35
RR_TARGET = 3.0
PRE_ENTRY_MULT = 1.5
BASE_COUNT_FILTER = "All"
ONLY_LATEST_BAR = True
DEBOUNCE_SECONDS = 3600
BATCH_SIZE = 5

STATE_FILE = "alert_state_forex.json"
MAX_STATE_KEYS = 5000

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alert_bot_forex.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_FOREX", "")

PERIOD_LADDER = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


def get_yf_interval(itv: str) -> str:
    return YF_INTERVAL_MAP.get(itv, itv)


def fetch_smart(tkr: str, itv: str, requested_period: str) -> pd.DataFrame:
    yf_interval = get_yf_interval(itv)
    idx = PERIOD_LADDER.index(requested_period) if requested_period in PERIOD_LADDER else 0
    for cand in [PERIOD_LADDER[i] for i in range(idx, -1, -1)]:
        try:
            df = yf.download(tkr, interval=yf_interval, period=cand, progress=False, auto_adjust=False)
        except Exception:
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
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                return set()
        except Exception:
            return set()
    return set()


def save_state(keys: set) -> None:
    keys_list = list(keys)[-MAX_STATE_KEYS:]
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(keys_list, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        logger.info(f"✅ State saved: {len(keys_list)} keys")
    except Exception as e:
        logger.error(f"❌ Error saving state: {e}")


def should_send_alert(key: str, sent_keys: set, last_alert_time: dict) -> bool:
    if key in sent_keys:
        return False
    if key in last_alert_time:
        if time.time() - last_alert_time[key] < DEBOUNCE_SECONDS:
            return False
    return True


# ==========================================================================
# 🔥 DUPLICATE CHECK WITH TOLERANCE (Forex)
# ==========================================================================

def is_duplicate_with_tolerance(tkr: str, itv: str, event: dict, sent_keys: set) -> bool:
    """Check if same zone already alerted (with 0.0005 tolerance for forex)"""
    z = event["zone"]
    tolerance = 0.0005 if "=X" in tkr else 0.5
    for key in sent_keys:
        parts = key.split("|")
        if len(parts) >= 5:
            saved_tkr = parts[0]
            saved_itv = parts[1]
            saved_pattern = parts[2]
            try:
                saved_prox = float(parts[3])
                saved_dist = float(parts[4])
            except ValueError:
                continue
            
            if saved_tkr == tkr and saved_itv == itv and saved_pattern == z.pattern_name:
                if abs(saved_prox - z.proximal) < tolerance and abs(saved_dist - z.distal) < tolerance:
                    return True
    return False


def main():
    logger.info("=" * 60)
    logger.info("💱 FOREX + COMMODITY + CRYPTO + INDICES SCANNER STARTED (REAL DATA)")
    logger.info(f"📊 Total Symbols: {len(TICKERS)}")
    logger.info(f"📊 Total Timeframes: {len(INTERVALS)}")
    logger.info(f"📌 Timeframes: {INTERVALS}")
    logger.info("=" * 60)
    
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ TELEGRAM credentials missing.")
        sys.exit(1)

    sent_keys = load_state()
    last_alert_time = {}
    new_count = 0
    total_events = 0
    total_zones = 0
    pending_alerts = []

    for tkr in TICKERS:
        for itv in INTERVALS:
            df = fetch_smart(tkr, itv, PERIOD)
            if df.empty:
                continue
            
            try:
                result = run_full_pipeline(df, atr_length=ATR_LENGTH, atr_multiplier=ATR_MULTIPLIER,
                                           rr_target=RR_TARGET, pre_entry_mult=PRE_ENTRY_MULT,
                                           base_count_filter=BASE_COUNT_FILTER)
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                continue

            events = result.events
            total_events += len(events)
            total_zones += len(result.all_zones)
            
            if ONLY_LATEST_BAR:
                last_bar = len(df) - 1
                events = [e for e in events if e["bar"] == last_bar]
            
            for e in events:
                key = alert_key(tkr, itv, e)
                
                # 🔥 TOLERANCE CHECK
                if is_duplicate_with_tolerance(tkr, itv, e, sent_keys):
                    logger.info(f"  ⏭️ Skipping duplicate (tolerance): {key}")
                    continue
                
                if not should_send_alert(key, sent_keys, last_alert_time):
                    continue
                    
                sent_keys.add(key)
                last_alert_time[key] = time.time()
                txt = build_alert_text(tkr, itv, e, df, RR_TARGET)
                chart_bytes = render_zone_chart(df, e, tkr, itv)
                pending_alerts.append({
                    "ticker": tkr, "interval": itv, "type": e["type"],
                    "text": txt, "chart_bytes": chart_bytes, "key": key
                })

    for i in range(0, len(pending_alerts), BATCH_SIZE):
        batch = pending_alerts[i:i + BATCH_SIZE]
        for alert in batch:
            if alert["chart_bytes"]:
                ok, msg = send_telegram_photo(BOT_TOKEN, CHAT_ID, alert["chart_bytes"], caption=alert["text"])
            else:
                ok, msg = send_telegram_message(BOT_TOKEN, CHAT_ID, alert["text"])
            if ok:
                new_count += 1
        if i + BATCH_SIZE < len(pending_alerts):
            time.sleep(3)

    save_state(sent_keys)
    
    logger.info("📊 FOREX + COMMODITY + CRYPTO + INDICES SCAN COMPLETE (REAL DATA)")
    logger.info(f"  • Symbols: {len(TICKERS)}")
    logger.info(f"  • Timeframes: {len(INTERVALS)}")
    logger.info(f"  • New alerts: {new_count}")


if __name__ == "__main__":
    main()
