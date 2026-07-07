"""
alert_bot_us.py - 🇺🇸 US100 Stocks 24x7 Alert Bot
Timeframes: 5m, 15m, 30m, 75m, 125m, 2h, Daily, Weekly
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
# ⚙️ CONFIG - US100 STOCKS (CLEANED - No Delisted Symbols)
# ==========================================================================

INTERVALS = [
    "5m", "15m", "30m", "75m", "125m", "2h", "1d", "1wk"
]

# 🔥 US100 STOCKS - CLEANED (Removed: SQ, PXD, DISH, ATVI, TWTR, FB, VXX, etc.)
TICKERS = [
    # ===== TECHNOLOGY =====
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "NFLX", "ADBE", "CRM", "ORCL", "IBM", "CSCO", "INTC",
    "AMD", "QCOM", "TXN", "AVGO", "MU", "ARM",
    "PLTR", "SNOW", "CRWD", "ZS", "PANW", "FTNT", "OKTA",
    "DDOG", "MDB", "TEAM", "NET", "HUBS", "NOW",
    "ADSK", "CDNS", "SNPS", "NXPI", "MCHP", "ADI", "SWKS",
    "MRVL", "ANSS", "ROP", "TYL", "PTC", "VRSN", "AKAM",
    "ANET", "DELL", "HPQ", "HPE", "NTAP", "STX", "WDC",
    "SMCI", "ON", "TER", "ENTG", "LRCX", "KLAC", "AMAT",
    
    # ===== FINANCE =====
    "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "PYPL",
    "COIN", "BLK", "AXP", "USB", "PNC", "TFC",
    "SCHW", "AMTD", "FIS", "FISV", "GPN", "JKHY",
    "MCO", "SPGI", "ICE", "NDAQ", "CME", "CBOE",
    "SYF", "DFS", "ALLY", "SOFI", "HOOD",
    
    # ===== HEALTHCARE =====
    "JNJ", "PFE", "MRK", "UNH", "CVS", "ABBV", "LLY",
    "GILD", "BIIB", "AMGN", "VRTX", "REGN", "MRNA",
    "ISRG", "DHR", "TMO", "ABT", "MDT", "SYK", "BSX",
    "ZTS", "EW", "IDXX", "DXCM", "ALGN", "HUM", "CI",
    "ELV", "CNC", "MOH", "WBA", "COR", "CAH",
    "BHC", "NBIX", "INCY", "UTHR", "ALNY",
    
    # ===== CONSUMER =====
    "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "SBUX",
    "NKE", "DIS", "UPS", "FDX", "TGT", "LOW", "KHC",
    "CMG", "BKNG", "EXPE", "MAR", "HLT", "RCL",
    "CCL", "NCLH", "YUM", "DPZ", "QSR", "DRI",
    "MGM", "WYNN", "LVS", "CZR",
    "ABNB", "UBER", "LYFT", "DASH",
    "EL", "CLX", "CHD", "CL", "KMB",
    
    # ===== ENERGY =====
    "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "VLO",
    "MPC", "DVN", "HAL", "BKR", "FTI", "NOV",
    "KMI", "OKE", "WMB", "LNG", "EQT",
    "FANG", "MRO", "CTRA", "HES", "APA",
    
    # ===== INDUSTRIAL =====
    "GE", "CAT", "BA", "RTX", "LMT", "HON", "UNP", "DHR",
    "DE", "CARR", "OTIS", "CTAS", "MMM", "EMR", "ETN",
    "ITW", "CMI", "PH", "AME", "ROK", "IR", "URI",
    "PCAR", "FAST", "GWW", "ODFL", "XPO",
    "FDX", "UPS", "JBHT", "CHRW",
    "GD", "NOC", "LHX", "HII",
    
    # ===== COMMUNICATION =====
    "T", "VZ", "TMUS", "CMCSA", "CHTR",
    "EA", "TTWO", "SNAP", "PINS", "MTCH",
    "ROKU", "ZG", "GOOGL", "META", "NFLX",
    
    # ===== REAL ESTATE =====
    "AMT", "PLD", "CCI", "EQIX", "SPG", "PSA", "DLR",
    "VICI", "ARE", "AVB", "EQR", "ESS", "MAA", "SUI",
    "UDR", "INVH", "CPT", "AIV", "BXP", "FRT", "KIM",
    "REG", "WY", "LAMR", "CUBE",
    
    # ===== CRYPTO RELATED =====
    "COIN", "MSTR", "RIOT", "MARA", "CLSK",
    "HOOD", "SOFI", "WULF", "CIFR", "HUT",
    
    # ===== ETFs & INDEXES =====
    "SPY", "QQQ", "DIA", "IWM", "VOO", "VTI",
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY",
    "XLP", "XLU", "XLRE", "XLC", "XLB",
]

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

STATE_FILE = "alerted_state_us.json"
MAX_STATE_KEYS = 5000

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alert_bot_us.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_US", "")

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
    logger.info("🇺🇸 US100 SCANNER STARTED")
    logger.info(f"📊 Total Symbols: {len(TICKERS)}")
    logger.info(f"📊 Total Timeframes: {len(INTERVALS)}")
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
    
    summary = f"""🇺🇸 US100 SCAN COMPLETE
  • Symbols: {len(TICKERS)}
  • Timeframes: {len(INTERVALS)}
  • Zones found: {total_zones}
  • New alerts: {new_count}
  • ⏱️ {dt.datetime.now().strftime('%d-%b %H:%M:%S')}"""
    send_telegram_message(BOT_TOKEN, CHAT_ID, summary)
    
    logger.info("📊 US100 SCAN COMPLETE")


if __name__ == "__main__":
    main()
