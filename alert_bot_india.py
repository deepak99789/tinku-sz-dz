"""
alert_bot_india.py - 🇮🇳 NIFTY 500 Stocks 24x7 Alert Bot
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

TICKERS = [
    "360ONE.NS", "3MINDIA.NS", "ABB.NS", "ACC.NS", "ACMESOLAR.NS",
    "AIAENG.NS", "APLAPOLLO.NS", "AUBANK.NS", "AWL.NS", "AADHARHFC.NS",
    "AARTIIND.NS", "AAVAS.NS", "ABBOTINDIA.NS", "ACE.NS", "ACUTAAS.NS",
    "ADANIENSOL.NS", "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANIPOWER.NS",
    "ATGL.NS", "ABCAPITAL.NS", "ABFRL.NS", "ABLBL.NS", "ABREL.NS",
    "ABSLAMC.NS", "CPPLUS.NS", "AEGISLOG.NS", "AEGISVOPAK.NS", "AFCONS.NS",
    "AFFLE.NS", "AJANTPHARM.NS", "ALKEM.NS", "ABDL.NS", "ARE&M.NS",
    "AMBER.NS", "AMBUJACEM.NS", "ANANDRATHI.NS", "ANANTRAJ.NS", "ANGELONE.NS",
    "ANTHEM.NS", "ANURAS.NS", "APARINDS.NS", "APOLLOHOSP.NS", "APOLLOTYRE.NS",
    "APTUS.NS", "ASAHIINDIA.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTERDM.NS",
    "ASTRAL.NS", "ATHERENERG.NS", "ATUL.NS", "AUROPHARMA.NS", "AIIL.NS",
    "DMART.NS", "AXISBANK.NS", "BEML.NS", "BLS.NS", "BSE.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BAJAJHLDNG.NS", "BAJAJHFL.NS",
    "BALKRISIND.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BANKINDIA.NS",
    "MAHABANK.NS", "BATAINDIA.NS", "BAYERCROP.NS", "BELRISE.NS", "BERGEPAINT.NS",
    "BDL.NS", "BEL.NS", "BHARATFORG.NS", "BHEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BHARTIHEXA.NS", "BIKAJI.NS", "GROWW.NS", "BIOCON.NS",
    "BSOFT.NS", "BLUEDART.NS", "BLUEJET.NS", "BLUESTARCO.NS", "BBTC.NS",
    "BOSCHLTD.NS", "FIRSTCRY.NS", "BRIGADE.NS", "BRITANNIA.NS", "MAPMYINDIA.NS",
    "CCL.NS", "CESC.NS", "CGPOWER.NS", "CIEINDIA.NS", "CRISIL.NS",
    "CANFINHOME.NS", "CANBK.NS", "CANHLIFE.NS", "CAPLIPOINT.NS", "CGCL.NS",
    "CARBORUNIV.NS", "CARTRADE.NS", "CASTROLIND.NS", "CEATLTD.NS", "CEMPRO.NS",
    "CENTRALBK.NS", "CDSL.NS", "CHALET.NS", "CHAMBLFERT.NS", "CHENNPETRO.NS",
    "CHOICEIN.NS", "CHOLAHLDNG.NS", "CHOLAFIN.NS", "CIPLA.NS", "CUB.NS",
    "CLEAN.NS", "COALINDIA.NS", "COCHINSHIP.NS", "COFORGE.NS", "COHANCE.NS",
    "COLPAL.NS", "CAMS.NS", "CONCORDBIO.NS", "CONCOR.NS", "COROMANDEL.NS",
    "CRAFTSMAN.NS", "CREDITACC.NS", "CROMPTON.NS", "CUMMINSIND.NS", "CYIENT.NS",
    "DCMSHRIRAM.NS", "DLF.NS", "DOMS.NS", "DABUR.NS", "DALBHARAT.NS",
    "DATAPATTNS.NS", "DEEPAKFERT.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DEVYANI.NS",
    "DIVISLAB.NS", "DIXON.NS", "LALPATHLAB.NS", "DRREDDY.NS", "EIDPARRY.NS",
    "EIHOTEL.NS", "EICHERMOT.NS", "ELECON.NS", "ELGIEQUIP.NS", "EMAMILTD.NS",
    "EMCURE.NS", "EMMVEE.NS", "ENDURANCE.NS", "ENGINERSIN.NS", "ERIS.NS",
    "ESCORTS.NS", "ETERNAL.NS", "EXIDEIND.NS", "NYKAA.NS", "FEDERALBNK.NS",
    "FACT.NS", "FINCABLES.NS", "FSL.NS", "FIVESTAR.NS", "FORCEMOT.NS",
    "FORTIS.NS", "GAIL.NS", "GVT&D.NS", "GMRAIRPORT.NS", "GABRIEL.NS",
    "GALLANTT.NS", "GRSE.NS", "GICRE.NS", "GILLETTE.NS", "GLAND.NS",
    "GLAXO.NS", "GLENMARK.NS", "MEDANTA.NS", "GODIGIT.NS", "GPIL.NS",
    "GODFRYPHLP.NS", "GODREJCP.NS", "GODREJIND.NS", "GODREJPROP.NS", "GRANULES.NS",
    "GRAPHITE.NS", "GRASIM.NS", "GRAVITA.NS", "GESHIP.NS", "FLUOROCHEM.NS",
    "GMDCLTD.NS", "HEG.NS", "HBLENGINE.NS", "HCLTECH.NS", "HDBFS.NS",
    "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HFCL.NS", "HAVELLS.NS",
    "HEROMOTOCO.NS", "HEXT.NS", "HSCL.NS", "HINDALCO.NS", "HAL.NS",
    "HINDCOPPER.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "HINDZINC.NS", "POWERINDIA.NS",
    "HOMEFIRST.NS", "HONASA.NS", "HONAUT.NS", "HUDCO.NS", "HYUNDAI.NS",
    "ICICIBANK.NS", "ICICIGI.NS", "ICICIAMC.NS", "ICICIPRULI.NS", "IDBI.NS",
    "IDFCFIRSTB.NS", "IFCI.NS", "IIFL.NS", "IRB.NS", "IRCON.NS",
    "ITCHOTELS.NS", "ITC.NS", "ITI.NS", "INDGN.NS", "INDIACEM.NS",
    "INDIAMART.NS", "INDIANB.NS", "IEX.NS", "INDHOTEL.NS", "IOC.NS",
    "IOB.NS", "IRCTC.NS", "IRFC.NS", "IREDA.NS", "IGL.NS",
    "INDUSTOWER.NS", "INDUSINDBK.NS", "NAUKRI.NS", "INFY.NS", "INOXWIND.NS",
    "INTELLECT.NS", "INDIGO.NS", "IGIL.NS", "IKS.NS", "IPCALAB.NS",
    "JKCEMENT.NS", "JBMA.NS", "JKTYRE.NS", "JMFINANCIL.NS", "JSWCEMENT.NS",
    "JSWDULUX.NS", "JSWENERGY.NS", "JSWINFRA.NS", "JSWSTEEL.NS", "JAINREC.NS",
    "JPPOWER.NS", "J&KBANK.NS", "JINDALSAW.NS", "JSL.NS", "JINDALSTEL.NS",
    "JIOFIN.NS", "JUBLFOOD.NS", "JUBLINGREA.NS", "JUBLPHARMA.NS", "JWL.NS",
    "JYOTICNC.NS", "KPRMILL.NS", "KEI.NS", "KPITTECH.NS", "KAJARIACER.NS",
    "KPIL.NS", "KALYANKJIL.NS", "KARURVYSYA.NS", "KAYNES.NS", "KEC.NS",
    "KFINTECH.NS", "KIRLOSENG.NS", "KOTAKBANK.NS", "KIMS.NS", "LTF.NS",
    "LTTS.NS", "LGEINDIA.NS", "LICHSGFIN.NS", "LTFOODS.NS", "LTM.NS",
    "LT.NS", "LATENTVIEW.NS", "LAURUSLABS.NS", "THELEELA.NS", "LEMONTREE.NS",
    "LENSKART.NS", "LICI.NS", "LINDEINDIA.NS", "LLOYDSME.NS", "LODHA.NS",
    "LUPIN.NS", "MMTC.NS", "MRF.NS", "MGL.NS", "M&MFIN.NS",
    "M&M.NS", "MANAPPURAM.NS", "MRPL.NS", "MANKIND.NS", "MARICO.NS",
    "MARUTI.NS", "MFSL.NS", "MAXHEALTH.NS", "MAZDOCK.NS", "MEESHO.NS",
    "MINDACORP.NS", "MSUMI.NS", "MOTILALOFS.NS", "MPHASIS.NS", "MCX.NS",
    "MUTHOOTFIN.NS", "NATCOPHARM.NS", "NBCC.NS", "NCC.NS", "NHPC.NS",
    "NLCINDIA.NS", "NMDC.NS", "NSLNISP.NS", "NTPCGREEN.NS", "NTPC.NS",
    "NH.NS", "NATIONALUM.NS", "NAVA.NS", "NAVINFLUOR.NS", "NESTLEIND.NS",
    "NETWEB.NS", "NEULANDLAB.NS", "NEWGEN.NS", "NAM-INDIA.NS", "NIVABUPA.NS",
    "NUVAMA.NS", "NUVOCO.NS", "OBEROIRLTY.NS", "ONGC.NS", "OIL.NS",
    "OLAELEC.NS", "OLECTRA.NS", "PAYTM.NS", "ONESOURCE.NS", "OFSS.NS",
    "POLICYBZR.NS", "PCBL.NS", "PGEL.NS", "PIIND.NS", "PNBHOUSING.NS",
    "PTCIL.NS", "PVRINOX.NS", "PAGEIND.NS", "PARADEEP.NS", "PATANJALI.NS",
    "PERSISTENT.NS", "PETRONET.NS", "PFIZER.NS", "PHOENIXLTD.NS", "PWL.NS",
    "PIDILITIND.NS", "PINELABS.NS", "PIRAMALFIN.NS", "PPLPHARMA.NS", "POLYMED.NS",
    "POLYCAB.NS", "POONAWALLA.NS", "PFC.NS", "POWERGRID.NS", "PREMIERENE.NS",
    "PRESTIGE.NS", "PFOCUS.NS", "PNB.NS", "RRKABEL.NS", "RBLBANK.NS",
    "RECLTD.NS", "RHIM.NS", "RITES.NS", "RADICO.NS", "RVNL.NS",
    "RAILTEL.NS", "RAINBOW.NS", "RKFORGE.NS", "REDINGTON.NS", "RELIANCE.NS",
    "RPOWER.NS", "SBFC.NS", "SBICARD.NS", "SBILIFE.NS", "SJVN.NS",
    "SRF.NS", "SAGILITY.NS", "SAILIFE.NS", "SAMMAANCAP.NS", "MOTHERSON.NS",
    "SAPPHIRE.NS", "SARDAEN.NS", "SAREGAMA.NS", "SCHAEFFLER.NS", "SCHNEIDER.NS",
    "SCI.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SHYAMMETL.NS", "ENRIN.NS",
    "SIEMENS.NS", "SIGNATURE.NS", "SOBHA.NS", "SOLARINDS.NS", "SONACOMS.NS",
    "SONATSOFTW.NS", "STARHEALTH.NS", "SBIN.NS", "SAIL.NS", "SUMICHEM.NS",
    "SUNPHARMA.NS", "SUNTV.NS", "SUNDARMFIN.NS", "SUPREMEIND.NS", "SPLPETRO.NS",
    "SUZLON.NS", "SWANCORP.NS", "SWIGGY.NS", "SYNGENE.NS", "SYRMA.NS",
    "TBOTEK.NS", "TVSMOTOR.NS", "TATACAP.NS", "TATACHEM.NS", "TATACOMM.NS",
    "TCS.NS", "TATACONSUM.NS", "TATAELXSI.NS", "TATAINVEST.NS", "TMCV.NS",
    "TMPV.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TATATECH.NS", "TTML.NS",
    "TECHM.NS", "TECHNOE.NS", "TEGA.NS", "TEJASNET.NS", "TENNIND.NS",
    "NIACL.NS", "RAMCOCEM.NS", "THERMAX.NS", "TIMKEN.NS", "TITAGARH.NS",
    "TITAN.NS", "TORNTPHARM.NS", "TORNTPOWER.NS", "TARIL.NS", "TRAVELFOOD.NS",
    "TRENT.NS", "TRIDENT.NS", "TRITURBINE.NS", "TIINDIA.NS", "UCOBANK.NS",
    "UNOMINDA.NS", "UPL.NS", "UTIAMC.NS", "ULTRACEMCO.NS", "UNIONBANK.NS",
    "UBL.NS", "UNITDSPR.NS", "URBANCO.NS", "USHAMART.NS", "VTL.NS",
    "VBL.NS", "VEDL.NS", "VIJAYA.NS", "VMM.NS", "IDEA.NS",
    "VOLTAS.NS", "WAAREEENER.NS", "WELCORP.NS", "WELSPUNLIV.NS", "WHIRLPOOL.NS",
    "WIPRO.NS", "WOCKPHARMA.NS", "YESBANK.NS", "ZFCVINDIA.NS", "ZEEL.NS",
    "ZENTEC.NS", "ZENSARTECH.NS", "ZYDUSLIFE.NS", "ZYDUSWELL.NS", "ECLERX.NS",
]


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

# ==========================================================================
# 🔥 RUN CACHE - Prevent duplicates within same run
# ==========================================================================

RUN_CACHE = set()

def is_duplicate_in_run(tkr: str, itv: str, event: dict) -> bool:
    z = event["zone"]
    key = f"{tkr}|{itv}|{int(z.proximal)}"
    if key in RUN_CACHE:
        return True
    RUN_CACHE.add(key)
    return False


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


def is_duplicate_with_tolerance(tkr: str, itv: str, event: dict, sent_keys: set) -> bool:
    z = event["zone"]
    for key in sent_keys:
        parts = key.split("|")
        if len(parts) >= 3:
            saved_tkr = parts[0]
            saved_itv = parts[1]
            try:
                saved_prox = int(float(parts[2]))
            except (ValueError, IndexError):
                continue
            if saved_tkr == tkr and saved_itv == itv and abs(saved_prox - int(z.proximal)) < 2:
                return True
    return False


def main():
    global RUN_CACHE
    RUN_CACHE = set()
    
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
                if is_duplicate_in_run(tkr, itv, e):
                    logger.info(f"  ⏭️ Skipping duplicate in run: {tkr} {itv} {e['type']}")
                    continue
                
                key = alert_key(tkr, itv, e)
                
                if is_duplicate_with_tolerance(tkr, itv, e, sent_keys):
                    logger.info(f"  ⏭️ Skipping duplicate (state): {key}")
                    continue
                
                if not should_send_alert(key, sent_keys, last_alert_time):
                    continue
                    
                sent_keys.add(key)
                last_alert_time[key] = time.time()
                
                txt = build_alert_text(tkr, itv, e, df, RR_TARGET)
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
