"""
alert_bot_india.py - 🇮🇳 NIFTY 200 Stocks 24x7 Alert Bot
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
# ⚙️ CONFIG - NIFTY 200 STOCKS
# ==========================================================================

# 🔥 TIMEFRAMES - As per requirement
INTERVALS = [
    "5m", "15m", "30m", "75m", "125m", "2h", "1d", "1wk"
]

# 🔥 NIFTY 200 STOCKS (Complete List)
TICKERS = [
    # NIFTY 50 (Large Cap)
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "HINDUNILVR.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS",
    "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS",
    "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "COALINDIA.NS", "BHARTIARTL.NS",
    "TATACONSUM.NS", "PIDILITIND.NS", "DIVISLAB.NS", "DRREDDY.NS", "GRASIM.NS",
    "JSWSTEEL.NS", "TECHM.NS", "TITAN.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    "BRITANNIA.NS", "HINDALCO.NS", "EICHERMOT.NS", "BAJAJFINSV.NS", "ADANIGREEN.NS",
    "ADANIENT.NS", "VEDL.NS", "TATASTEEL.NS", "JINDALSTEL.NS", "M&M.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "INDUSINDBK.NS", "YESBANK.NS",
    
    # NIFTY Next 50 (Mid Cap)
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "AUBANK.NS",
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
    
    # Additional Nifty 200 Stocks
    "ABCAPITAL.NS", "ACC.NS", "ADANIPOWER.NS", "ALKEM.NS", "AMBER.NS",
    "ANGELONE.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASTRAL.NS", "ATUL.NS",
    "AUBANK.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BATAINDIA.NS",
    "BERGEPAINT.NS", "BIOCON.NS", "BLUESTAR.NS", "BOSCHLTD.NS", "CADILAHC.NS",
    "CANBK.NS", "CASTROLIND.NS", "CEATLTD.NS", "CENTRALBK.NS", "CHAMBLFERT.NS",
    "CHOLAFIN.NS", "CIPLA.NS", "CITYUNION.NS", "COALINDIA.NS", "COFORGE.NS",
    "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS",
    "CUMMINSIND.NS", "DABUR.NS", "DALMIABHA.NS", "DEEPAKNTR.NS", "DELTACORP.NS",
    "DIVISLAB.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS", "ESCORTS.NS",
    "EXIDEIND.NS", "FEDERALBNK.NS", "FORTIS.NS", "GAIL.NS", "GODREJCP.NS",
    "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", "GSPL.NS", "GUJGASLTD.NS",
    "HAL.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "HONAUT.NS", "ICICIGI.NS", "ICICIPRULI.NS",
    "IDEA.NS", "IDFCFIRSTB.NS", "IEX.NS", "IGL.NS", "INDIGO.NS",
    "INDUSINDBK.NS", "INFY.NS", "IOC.NS", "IRCTC.NS", "ITC.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "JUBLFOOD.NS", "KOTAKBANK.NS", "L&TFH.NS",
    "LICHSGFIN.NS", "LT.NS", "LTI.NS", "LTTS.NS", "M&M.NS",
    "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MCDOWELL-N.NS",
    "MCX.NS", "METROPOLIS.NS", "MFSL.NS", "MGL.NS", "MOTHERSUMI.NS",
    "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS",
    "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", "OBEROIRLTY.NS",
    "ONGC.NS", "PAGEIND.NS", "PEL.NS", "PETRONET.NS", "PFC.NS",
    "PIDILITIND.NS", "PNB.NS", "POWERGRID.NS", "PVRINOX.NS", "RAMCOCEM.NS",
    "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SHREECEM.NS", "SIEMENS.NS", "SRTRANSFIN.NS", "SUNPHARMA.NS", "SUNTV.NS",
    "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS",
    "UBL.NS", "ULTRACEMCO.NS", "UPL.NS", "VEDL.NS", "VOLTAS.NS",
    "WIPRO.NS", "YESBANK.NS", "ZEEL.NS", "ZYDUSLIFE.NS"
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

STATE_FILE = "alerted_state_india.json"
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
        logger.info(f"✅ State saved: {len(keys_list)} keys")
    except Exception as e:
        logger.error(f"Error saving state: {e}")


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
    logger.info("🇮🇳 NIFTY 200 SCANNER STARTED")
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
    
    summary = f"""🇮🇳 NIFTY 200 SCAN COMPLETE
  • Symbols: {len(TICKERS)}
  • Timeframes: {len(INTERVALS)}
  • Zones found: {total_zones}
  • New alerts: {new_count}
  • ⏱️ {dt.datetime.now().strftime('%d-%b %H:%M:%S')}"""
    send_telegram_message(BOT_TOKEN, CHAT_ID, summary)
    
    logger.info("📊 NIFTY 200 SCAN COMPLETE")


if __name__ == "__main__":
    main()
