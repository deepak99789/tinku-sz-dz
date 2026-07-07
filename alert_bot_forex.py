"""
alert_bot_forex.py - 💱 Forex + Commodity + Crypto + Indices 24x7 Alert Bot
Forex: Major + Minor + Cross
Commodity: XAUUSD, XAGUSD, Aluminium (Zinc removed)
Crypto: BTCUSD
Indices: S&P500, US30, US100, Russell 2000, GER40, JPN225
Timeframes: 5m, 15m, 30m, 45m, 75m, 125m, 1h, 2h, 4h, 5h, 6h, 8h, 10h, 12h, 16h, Daily, Weekly
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
# ⚙️ CONFIG - FOREX + COMMODITY + CRYPTO + INDICES
# ==========================================================================

# 🔥 TIMEFRAMES - All timeframes
INTERVALS = [
    "5m", "15m", "30m", "45m", "75m", "125m",
    "1h", "2h", "4h", "5h", "6h", "8h", "10h", "12h", "16h",
    "1d", "1wk"
]

# 🔥 FOREX - Major + Minor + Cross
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

# 🔥 COMMODITIES
COMMODITY_TICKERS = [
    "GC=F",    # Gold (XAUUSD)
    "SI=F",    # Silver (XAGUSD)
    "ALI=F",   # Aluminium
]

# 🔥 CRYPTO - Only BTCUSD
CRYPTO_TICKERS = [
    "BTC-USD",  # Bitcoin
]

# 🔥 INDICES
INDICES_TICKERS = [
    "^GSPC",    # S&P 500 (SP500)
    "^DJI",     # US30 (Dow Jones)
    "^IXIC",    # US100 (NASDAQ)
    "^RUT",     # Russell 2000
    "^GDAXI",   # GER40 (DAX)
    "^N225",    # JPN225 (Nikkei 225)
]

# 🔥 COMBINE ALL
TICKERS = FOREX_TICKERS + COMMODITY_TICKERS + CRYPTO_TICKERS + INDICES_TICKERS

YF_INTERVAL_MAP = {
    "5m": "5m", "15m": "15m", "30m": "30m", "45m": "30m",
    "60m": "60m", "75m": "60m", "125m": "60m",
    "2h": "60m", "4h": "60m", "5h": "60m", "6h": "60m",
    "8h": "60m", "10h": "60m", "12h": "1d", "16h": "1d",
    "1d": "1d", "1wk": "1wk"
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

STATE_FILE = "alerted_state_forex.json"
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
    supported = ["5m", "15m", "30m", "60m", "1h", "1d", "1wk"]
    if itv in supported:
        return itv
    return YF_INTERVAL_MAP.get(itv, "60m")


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
                return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()


def save_state(keys: set) -> None:
    keys_list = list(keys)[-MAX_STATE_KEYS:]
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(keys_list, f)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logger.error(f"Error saving state: {e}")


def should_send_alert(key: str, sent_keys: set, last_alert_time: dict) -> bool:
    if key in sent_keys:
        return False
    if key in last_alert_time:
        if time.time() - last_alert_time[key] < DEBOUNCE_SECONDS:
            return False
    return True


def main():
    logger.info("=" * 60)
    logger.info("💱 FOREX + COMMODITY + CRYPTO + INDICES SCANNER STARTED")
    logger.info(f"📊 Total Symbols: {len(TICKERS)}")
    logger.info(f"📊 Total Timeframes: {len(INTERVALS)}")
    logger.info(f"   • Forex: {len(FOREX_TICKERS)}")
    logger.info(f"   • Commodity: {len(COMMODITY_TICKERS)}")
    logger.info(f"   • Crypto: {len(CRYPTO_TICKERS)}")
    logger.info(f"   • Indices: {len(INDICES_TICKERS)}")
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
    
    summary = f"""💱 FOREX + COMMODITY + CRYPTO + INDICES SCAN COMPLETE
  • Symbols: {len(TICKERS)}
  • Timeframes: {len(INTERVALS)}
  • Zones found: {total_zones}
  • New alerts: {new_count}
  • ⏱️ {dt.datetime.now().strftime('%d-%b %H:%M:%S')}"""
    
    
    logger.info("📊 FOREX + COMMODITY + CRYPTO + INDICES SCAN COMPLETE")


if __name__ == "__main__":
    main()
