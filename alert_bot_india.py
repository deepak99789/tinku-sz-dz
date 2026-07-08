"""
alert_bot_india.py - 🇮🇳 NIFTY 500 Stocks 24x7 Alert Bot
REAL DATA - All yfinance supported timeframes
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
# ⚙️ CONFIG - ALL YFINANCE SUPPORTED TIMEFRAMES (REAL DATA)
# ==========================================================================

# 🔥 ALL TIMEFRAMES THAT yfinance SUPPORTS (REAL DATA)
INTERVALS = [
    "1m", "2m", "5m", "15m", "30m", "60m", "90m",
    "1d", "5d", "1wk", "1mo", "3mo"
]

# 🔥 NIFTY 500 STOCKS (Complete List)
TICKERS = [
    # ===== NIFTY 50 =====
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
    "PIIND.NS", "SRTRANSFIN", "TRENT.NS", "UBL.NS", "VOLTAS.NS", "ZYDUSLIFE.NS",
    
    # ===== NIFTY NEXT 50 =====
    "ABCAPITAL.NS", "ACC.NS", "ALKEM.NS", "AMBER.NS",
    "ANGELONE.NS", "ASTRAL.NS", "ATUL.NS",
    "BALRAMCHIN.NS", "BANDHANBNK.NS", "BATAINDIA.NS",
    "BERGEPAINT.NS", "BIOCON.NS", "CADILAHC.NS",
    "CASTROLIND.NS", "CEATLTD.NS", "CENTRALBK.NS", "CHAMBLFERT.NS",
    "CHOLAFIN.NS", "CITYUNION.NS",
    "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS",
    "CUMMINSIND.NS", "DEEPAKNTR.NS", "DELTACORP.NS",
    "EXIDEIND.NS", "GRANULES.NS",
    "GSPL.NS", "GUJGASLTD.NS",
    "HDFCAMC.NS", "HONAUT.NS", "ICICIGI.NS", "ICICIPRULI.NS",
    "IDEA.NS", "IEX.NS", "IGL.NS", "INDIGO.NS",
    "JUBLFOOD.NS", "LICHSGFIN.NS", "M&MFIN.NS",
    "MANAPPURAM.NS", "MCDOWELL-N.NS", "MCX.NS", "MFSL.NS", "MGL.NS",
    "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS",
    "NAVINFLUOR.NS", "PAGEIND.NS", "PEL.NS",
    "RAMCOCEM.NS", "SHREECEM.NS",
    "SRTRANSFIN", "TRENT.NS", "UBL.NS", "VOLTAS.NS", "ZYDUSLIFE.NS",
    
    # ===== ADDITIONAL NIFTY 500 STOCKS =====
    "3MINDIA.NS", "AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS",
    "ABFRL.NS", "ACC.NS", "ADANIENT.NS", "ADANIGREEN.NS",
    "ADANIPORTS.NS", "ADANIPOWER.NS", "ALKEM.NS", "ALOKINDS.NS",
    "AMBER.NS", "AMBUJACEM.NS", "APOLLOHOSP.NS", "APOLLOTYRE.NS",
    "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS", "ATUL.NS",
    "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS",
    "BAJAJFINSV.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BANKBARODA.NS",
    "BATAINDIA.NS", "BEL.NS", "BERGEPAINT.NS", "BHARATFORG.NS",
    "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS",
    "BPCL.NS", "BRITANNIA.NS", "CADILAHC.NS", "CANBK.NS",
    "CASTROLIND.NS", "CENTRALBK.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS",
    "CIPLA.NS", "CITYUNION.NS", "COALINDIA.NS", "COFORGE.NS",
    "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS",
    "CUB.NS", "CUMMINSIND.NS", "DABUR.NS", "DALMIABHA.NS",
    "DEEPAKNTR.NS", "DELTACORP.NS", "DIVISLAB.NS", "DLF.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "EMAMILTD.NS", "ESCORTS.NS",
    "EXIDEIND.NS", "FEDERALBNK.NS", "FORTIS.NS", "GAIL.NS",
    "GLENMARK.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS",
    "GRASIM.NS", "GSPL.NS", "GUJGASLTD.NS", "HAL.NS",
    "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "HINDZINC.NS",
    "HONAUT.NS", "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS",
    "IDEA.NS", "IDFCFIRSTB.NS", "IEX.NS", "IGL.NS",
    "INDIGO.NS", "INDUSINDBK.NS", "INFY.NS", "IOC.NS",
    "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JSWSTEEL.NS",
    "JUBLFOOD.NS", "KOTAKBANK.NS", "L&TFH.NS", "LICHSGFIN.NS",
    "LT.NS", "LTFH.NS", "LTI.NS", "LTTS.NS",
    "LUPIN.NS", "M&M.NS", "M&MFIN.NS", "MANAPPURAM.NS",
    "MARICO.NS", "MARUTI.NS", "MAXHEALTH.NS", "MCDOWELL-N.NS",
    "MCX.NS", "MFSL.NS", "MGL.NS", "MINDTREE.NS",
    "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS",
    "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS",
    "NETWORK18.NS", "NHPC.NS", "NIITTECH.NS", "NMDC.NS",
    "NTPC.NS", "OBEROIRLTY.NS", "ONGC.NS", "PAGEIND.NS",
    "PEL.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS",
    "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POWERGRID.NS",
    "PRESTIGE.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS",
    "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBILIFE.NS",
    "SBIN.NS", "SHREECEM.NS", "SIEMENS.NS", "SOBHA.NS",
    "SRTRANSFIN.NS", "SUNPHARMA.NS", "SUNTV.NS", "SUZLON.NS",
    "TATACHEM.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS",
    "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS",
    "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS", "UBL.NS",
    "ULTRACEMCO.NS", "UNIONBANK.NS", "UPL.NS", "VEDL.NS",
    "VOLTAS.NS", "WIPRO.NS", "YESBANK.NS", "ZEEL.NS",
    "ZENSARTECH.NS", "ZYDUSLIFE.NS"
]

YF_INTERVAL_MAP = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
    "60m": "60m", "90m": "90m", "1d": "1d", "5d": "5d",
    "1wk": "1wk", "1mo": "1mo", "3mo": "3mo"
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

STATE_FILE = "alert_state_india.json"
MAX_STATE_KEYS = 5000

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alert_bot_india.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_INDIA", "")

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
        time_diff = time.time() - last_alert_time[key]
        if time_diff < DEBOUNCE_SECONDS:
            return False
    return True


def main():
    logger.info("=" * 60)
    logger.info("🇮🇳 NIFTY 500 SCANNER STARTED (REAL DATA)")
    logger.info(f"📊 Total Symbols: {len(TICKERS)}")
    logger.info(f"📊 Total Timeframes: {len(INTERVALS)}")
    logger.info(f"📌 Timeframes: {INTERVALS}")
    logger.info("=" * 60)
    
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ TELEGRAM credentials missing.")
        sys.exit(1)

    sent_keys = load_state()
    logger.info(f"📂 Loaded {len(sent_keys)} previously alerted keys")
    
    last_alert_time = {}
    new_count = 0
    total_events = 0
    total_zones = 0
    pending_alerts = []

    for tkr in TICKERS:
        for itv in INTERVALS:
            logger.info(f"\n📊 Scanning {tkr} [{itv}]...")
            
            df = fetch_smart(tkr, itv, PERIOD)
            if df.empty:
                logger.warning(f"❌ {tkr} {itv}: No data")
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
                logger.error(f"❌ Error running pipeline: {e}")
                continue

            events = result.events
            total_events += len(events)
            total_zones += len(result.all_zones)
            
            if events:
                logger.info(f"  🔍 Found {len(events)} events")
                for e in events[:3]:
                    logger.info(f"    - {e['type']} at bar {e['bar']}")
                if len(events) > 3:
                    logger.info(f"    ... and {len(events) - 3} more")
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
                
                txt = build_alert_text(tkr, itv, e, df, RR_TARGET, "yfinance_real")
                chart_bytes = render_zone_chart(df, e, tkr, itv)
                
                pending_alerts.append({
                    "ticker": tkr,
                    "interval": itv,
                    "type": e["type"],
                    "text": txt,
                    "chart_bytes": chart_bytes,
                    "key": key
                })
                
                logger.info(f"  📝 Queued: {tkr} {itv} {e['type']}")

    # Send alerts
    logger.info(f"\n📤 Sending {len(pending_alerts)} queued alerts in batches...")
    
    for i in range(0, len(pending_alerts), BATCH_SIZE):
        batch = pending_alerts[i:i + BATCH_SIZE]
        
        for alert in batch:
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
        
        if i + BATCH_SIZE < len(pending_alerts):
            logger.info(f"⏳ Waiting 3 seconds before next batch...")
            time.sleep(3)

    save_state(sent_keys)
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 NIFTY 500 SCAN COMPLETE (REAL DATA)")
    logger.info(f"  • Symbols: {len(TICKERS)}")
    logger.info(f"  • Timeframes: {len(INTERVALS)}")
    logger.info(f"  • Zones found: {total_zones}")
    logger.info(f"  • New alerts sent: {new_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
