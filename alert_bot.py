"""
alert_bot.py - Standalone 24x7 Zone Alert Bot (NO Streamlit, NO PC needed)
With Rate Limiting to avoid Telegram 429 errors.
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
from telegram_utils import send_telegram_message, send_telegram_photo, wait_if_needed
from alert_common import alert_key, build_alert_text, render_zone_chart, ALERT_ICONS

# ==========================================================================
# ⚙️ CONFIG - apni pasand ke hisaab se yahan edit karo
# ==========================================================================

# 🔥 ALL TIMEFRAMES from 5min to Weekly
INTERVALS = [
    "5m", "15m", "30m", "45m", "60m", "75m", "125m",
    "2h", "4h", "5h", "6h", "8h", "10h", "12h", "16h",
    "1d", "1wk"
]

# ==========================================================================
# 🔥 SYMBOL LISTS - NSE + US + FOREX (Major+Minor+Cross) + COMMODITIES + BTC
# 🔥 BSE REMOVED, ONLY BTC-USD IN CRYPTO
# ==========================================================================

# --- INDIAN STOCKS (NSE Only) ---
NSE_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "HINDUNILVR.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS",
    "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS",
    "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "COALINDIA.NS", "BHARTIARTL.NS",
    "TATACONSUM.NS", "PIDILITIND.NS", "DIVISLAB.NS", "DRREDDY.NS", "GRASIM.NS",
    "JSWSTEEL.NS", "TECHM.NS", "TITAN.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    "BRITANNIA.NS", "HINDALCO.NS", "EICHERMOT.NS", "BAJAJFINSV.NS", "ADANIGREEN.NS",
    "ADANIENT.NS", "VEDL.NS", "TATASTEEL.NS", "JINDALSTEL.NS", "M&M.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "INDUSINDBK.NS",
    "YESBANK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "AUBANK.NS",
    "MPHASIS.NS", "MINDTREE.NS", "COFORGE.NS", "LTI.NS", "LTTS.NS",
    "PERSISTENT.NS", "HEXAWARE.NS", "NIITTECH.NS", "CIGNITI.NS", "ZENSARTECH.NS",
    "CIPLA.NS", "GLENMARK.NS", "AUROPHARMA.NS", "LUPIN.NS", "TORNTPHARM.NS",
    "APOLLOHOSP.NS", "FORTIS.NS", "MAXHEALTH.NS", "NARAYANA.NS", "METROPOLIS.NS",
    "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "ESCORTS.NS",
    "BOSCHLTD.NS", "MOTHERSON.NS", "BALKRISIND.NS", "APOLLOTYRE.NS", "MRF.NS",
    "NESTLEIND.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "EMAMILTD.NS",
    "TATAPOWER.NS", "ADANIPOWER.NS", "GAIL.NS", "PETRONET.NS", "IOC.NS", "BPCL.NS",
    "HINDZINC.NS", "NMDC.NS", "SAIL.NS",
    "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "SOBHA.NS",
    "L&TFH.NS", "RECLTD.NS", "PFC.NS", "NHPC.NS", "IRCTC.NS",
    "SUNTV.NS", "PVRINOX.NS", "ZEE.NS", "NETWORK18.NS", "TV18BRDCST.NS",
    "BHARTIARTL.NS", "TATACOMM.NS", "IDEA.NS",
    "HAL.NS", "BEL.NS", "BHEL.NS", "SIEMENS.NS", "ABB.NS",
    "SUZLON.NS", "TATACHEM.NS", "UPL.NS", "PIIND.NS", "SRTRANSFIN.NS",
]

# --- US STOCKS ---
US_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "NFLX", "ADBE", "CRM", "ORCL", "IBM", "CSCO", "INTC",
    "AMD", "QCOM", "TXN", "AVGO", "MU",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "PYPL",
    "SQ", "COIN", "BLK", "AXP", "USB", "PNC", "TFC",
    "JNJ", "PFE", "MRK", "UNH", "CVS", "ABBV", "LLY",
    "GILD", "BIIB", "AMGN", "VRTX", "REGN", "MRNA",
    "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "SBUX",
    "NKE", "DIS", "UPS", "FDX", "TGT", "LOW", "KHC",
    "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "VLO",
    "GE", "CAT", "BA", "RTX", "LMT", "HON", "UNP", "DHR",
    "T", "VZ", "TMUS", "CMCSA", "CHTR", "DISH",
    "AMT", "PLD", "CCI", "EQIX", "SPG", "PSA", "DLR",
    "COIN", "MSTR", "RIOT", "MARA", "CLSK",
    "^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX",
]

# --- FOREX (Major + Minor + Cross, NO Exotics) ---
MAJOR_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", 
    "USDCAD=X", "USDCHF=X", "NZDUSD=X",
]

MINOR_PAIRS = [
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURCAD=X", 
    "EURAUD=X", "EURNZD=X",
    "GBPJPY=X", "GBPCHF=X", "GBPCAD=X", "GBPAUD=X", "GBPNZD=X",
    "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X",
    "AUDCAD=X", "AUDCHF=X", "AUDNZD=X", "CADCHF=X", 
    "NZDCAD=X", "NZDCHF=X",
]

INR_PAIRS = [
    "USDINR=X", "EURINR=X", "GBPINR=X", "JPYINR=X",
]

FOREX_TICKERS = MAJOR_PAIRS + MINOR_PAIRS + INR_PAIRS

# --- COMMODITIES ---
COMMODITY_TICKERS = [
    "GC=F", "SI=F", "HG=F", "PL=F", "PA=F",
    "CL=F", "BZ=F", "NG=F", "RB=F", "HO=F",
    "ZC=F", "ZS=F", "ZW=F", "ZM=F", "ZL=F",
    "CT=F", "SB=F", "KC=F", "CC=F",
    "LE=F", "HE=F", "GF=F",
]

# --- CRYPTO (ONLY BTC-USD) ---
CRYPTO_TICKERS = ["BTC-USD"]

# ==========================================================================
# 🔥 COMBINE ALL SYMBOLS
# ==========================================================================

TICKERS = (
    NSE_TICKERS + 
    US_TICKERS + 
    FOREX_TICKERS + 
    COMMODITY_TICKERS + 
    CRYPTO_TICKERS
)

# ==========================================================================

# 🔥 yfinance interval mapping
YF_INTERVAL_MAP = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", 
    "30m": "30m", "60m": "60m", "90m": "90m",
    "1h": "60m", "4h": "60m",
    "1d": "1d", "5d": "5d", "1wk": "1wk", "1mo": "1mo", "3mo": "3mo",
    "45m": "30m", "75m": "60m", "125m": "60m",
    "2h": "60m", "5h": "60m", "6h": "60m", "8h": "60m", "10h": "60m",
    "12h": "1d", "16h": "1d",
}

PERIOD = "1mo"
ATR_LENGTH = 14
ATR_MULTIPLIER = 0.35
RR_TARGET = 3.0
PRE_ENTRY_MULT = 1.5
BASE_COUNT_FILTER = "All"

# 🔥 CRITICAL: Sirf LATEST candle ke alerts
ONLY_LATEST_BAR = True

# 🔥 Debounce time (seconds)
DEBOUNCE_SECONDS = 3600  # 1 hour

# 🔥 Batch size - kitne alerts ek saath bhejne hain
BATCH_SIZE = 5  # 5 alerts per batch

STATE_FILE = "alerted_state.json"
MAX_STATE_KEYS = 5000

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alert_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==========================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

PERIOD_LADDER = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


def get_yf_interval(itv: str) -> str:
    supported = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
    if itv in supported:
        return itv
    if itv in YF_INTERVAL_MAP:
        fallback = YF_INTERVAL_MAP[itv]
        if fallback != itv:
            logger.info(f"  🔄 {itv} -> using fallback {fallback}")
        return fallback
    logger.warning(f"  ⚠️ {itv} not recognized, using 1h as fallback")
    return "60m"


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
        logger.info(f"✅ State saved: {len(keys_list)} keys")
    except Exception as e:
        logger.error(f"Error saving state: {e}")


def should_send_alert(key: str, sent_keys: set, last_alert_time: dict) -> bool:
    if key in sent_keys:
        return False
    if key in last_alert_time:
        time_diff = time.time() - last_alert_time[key]
        if time_diff < DEBOUNCE_SECONDS:
            logger.info(f"  ⏱️ Debounce: {key} - waiting {DEBOUNCE_SECONDS - time_diff:.0f}s more")
            return False
    return True


def main():
    logger.info("=" * 60)
    logger.info(f"🚀 ZONE SCANNER STARTED at {dt.datetime.now()}")
    logger.info(f"📊 Total Symbols: {len(TICKERS)}")
    logger.info(f"📊 Total Timeframes: {len(INTERVALS)}")
    logger.info(f"📌 ONLY_LATEST_BAR: {ONLY_LATEST_BAR}")
    logger.info(f"⏱️ DEBOUNCE_SECONDS: {DEBOUNCE_SECONDS}s")
    logger.info(f"📦 BATCH_SIZE: {BATCH_SIZE}")
    logger.info("=" * 60)
    
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing.")
        sys.exit(1)

    sent_keys = load_state()
    logger.info(f"📂 Loaded {len(sent_keys)} previously alerted keys")
    
    last_alert_time = {}
    new_count = 0
    total_events = 0
    total_zones = 0
    skipped = []
    
    # 🔥 Store alerts to send in batch
    pending_alerts = []

    for tkr in TICKERS:
        for itv in INTERVALS:
            logger.info(f"\n📊 Scanning {tkr} [{itv}]...")
            
            df = fetch_smart(tkr, itv, PERIOD)
            if df.empty:
                logger.warning(f"❌ {tkr} {itv}: No data")
                skipped.append(f"{tkr} [{itv}]")
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
                logger.error(f"❌ Error: {e}")
                continue

            events = result.events
            total_events += len(events)
            total_zones += len(result.all_zones)
            
            if events:
                logger.info(f"  🔍 Found {len(events)} events")
            else:
                logger.info(f"  ℹ️ No events found")
            
            if ONLY_LATEST_BAR:
                last_bar = len(df) - 1
                events = [e for e in events if e["bar"] == last_bar]
                if events:
                    logger.info(f"  📌 Filtered to latest bar: {len(events)} events")
            
            for e in events:
                key = alert_key(tkr, itv, e)
                
                if not should_send_alert(key, sent_keys, last_alert_time):
                    continue
                    
                sent_keys.add(key)
                last_alert_time[key] = time.time()
                
                txt = build_alert_text(tkr, itv, e, df, RR_TARGET)
                chart_bytes = render_zone_chart(df, e, tkr, itv)
                
                # 🔥 Add to pending alerts instead of sending immediately
                pending_alerts.append({
                    "ticker": tkr,
                    "interval": itv,
                    "type": e["type"],
                    "text": txt,
                    "chart_bytes": chart_bytes,
                    "key": key
                })
                
                logger.info(f"  📝 Queued: {tkr} {itv} {e['type']}")

    # ============================================================
    # 🔥 SEND ALERTS IN BATCHES WITH RATE LIMITING
    # ============================================================
    
    logger.info(f"\n📤 Sending {len(pending_alerts)} queued alerts in batches...")
    
    for i in range(0, len(pending_alerts), BATCH_SIZE):
        batch = pending_alerts[i:i + BATCH_SIZE]
        
        for alert in batch:
            # 🔥 Wait for rate limit before each message
            # (wait_if_needed is called inside send functions)
            
            if alert["chart_bytes"]:
                ok, msg = send_telegram_photo(BOT_TOKEN, CHAT_ID, alert["chart_bytes"], caption=alert["text"])
            else:
                ok, msg = send_telegram_message(BOT_TOKEN, CHAT_ID, alert["text"])
            
            icon = ALERT_ICONS.get(alert["type"], "🔔")
            if ok:
                logger.info(f"  ✅ {icon} ALERT SENT: {alert['ticker']} {alert['interval']} {alert['type']}")
                new_count += 1
            else:
                logger.error(f"  ❌ Failed: {alert['ticker']} {alert['interval']} - {msg}")
        
        # 🔥 Wait between batches
        if i + BATCH_SIZE < len(pending_alerts):
            logger.info(f"⏳ Waiting 3 seconds before next batch...")
            time.sleep(3)

    # Save state
    save_state(sent_keys)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 SCAN COMPLETE")
    logger.info(f"  • Total symbols: {len(TICKERS)}")
    logger.info(f"  • Total timeframes: {len(INTERVALS)}")
    logger.info(f"  • Total zones found: {total_zones}")
    logger.info(f"  • Total events detected: {total_events}")
    logger.info(f"  • New alerts queued: {len(pending_alerts)}")
    logger.info(f"  • New alerts sent: {new_count}")
    if skipped:
        logger.warning(f"  ⚠️ Skipped: {len(skipped)} combinations")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
