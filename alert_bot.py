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
import io
import datetime as dt

import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from pattern_engine import run_full_pipeline
from telegram_utils import send_telegram_message, send_telegram_photo

# ==========================================================================
# ⚙️ CONFIG - apni pasand ke hisaab se yahan edit karo
# ==========================================================================
TICKERS = {
    "Indian Stocks (NSE)": {
        "suffix_hint": "e.g. RELIANCE.NS, TCS.NS, INFY.NS",
        "tickers": [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS",
            "BAJFINANCE.NS", "HINDUNILVR.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS",
        ],
    },
    "Indian Stocks (BSE)": {
        "suffix_hint": "e.g. RELIANCE.BO, TCS.BO",
        "tickers": ["RELIANCE.BO", "TCS.BO", "INFY.BO", "HDFCBANK.BO", "SBIN.BO"],
    },
    "US Stocks / Index": {
        "suffix_hint": "e.g. AAPL, TSLA, ^GSPC, ^DJI",
        "tickers": [
            "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
            "^GSPC", "^DJI", "^IXIC",
        ],
    },
    "Forex": {
        "suffix_hint": "e.g. EURUSD=X, USDINR=X, GBPJPY=X",
        "tickers": ["EURUSD=X", "USDINR=X", "GBPJPY=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"],
    },
    "Commodity": {
        "suffix_hint": "e.g. GC=F (Gold), CL=F (Crude), SI=F (Silver)",
        "tickers": ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F"],
    },
    "Crypto": {
        "suffix_hint": "e.g. BTC-USD, ETH-USD, SOL-USD",
        "tickers": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    },
}

INTERVALS = ["15m", "1h", "1d"]   # jo bhi timeframes track karne hain

PERIOD = "1mo"                    # requested period - intraday ke liye auto chhota ho jayega agar zaroorat pade
ATR_LENGTH = 14
ATR_MULTIPLIER = 0.35
RR_TARGET = 3.0
PRE_ENTRY_MULT = 1.5
BASE_COUNT_FILTER = "All"         # "All" / "1" / "2" / "3"
ONLY_LATEST_BAR = True            # True = sirf sabse recent candle ka event alert karo (live monitoring ke liye best)

STATE_FILE = "alerted_state.json"
MAX_STATE_KEYS = 5000              # state file ko infinite badhne se rokne ke liye cap
# ==========================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# yfinance intraday history limit ke hisaab se step-down karne ke liye
PERIOD_LADDER = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]

ALERT_ICONS = {
    "zone_found": "✅",
    "entered": "🔵",
    "sl_hit": "🚨",
    "tp_hit": "🎯",
}


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


def alert_key(tkr: str, itv: str, event: dict) -> str:
    z = event["zone"]
    return f"{tkr}|{itv}|{event['type']}|{z.pattern_name}|{event['bar']}|{round(z.proximal, 4)}"


def build_text(tkr: str, itv: str, event: dict, df: pd.DataFrame) -> str:
    """Har alert type (zone_found / entered / sl_hit / tp_hit) me same
    detailed info deta hai: symbol, timeframe, pattern, type, proximal,
    leg-out formation date, base candle count, leg-out candle count."""
    z = event["zone"]
    zone_type = "Supply 🔴" if z.is_supply else "Demand 🟢"

    try:
        legout_date = df.index[z.trigger_bar].strftime("%d-%b-%Y %H:%M")
    except Exception:
        legout_date = "-"

    header_map = {
        "zone_found": "✅ ZONE FOUND",
        "entered": ("🔴 SELL ZONE TRIGGERED" if z.is_supply else "🟢 BUY ZONE TRIGGERED"),
        "sl_hit": "🚨 STOPLOSS HIT",
        "tp_hit": f"🎯 TARGET HIT (1:{RR_TARGET:g})",
    }
    header = header_map.get(event["type"], "🔔 UPDATE")

    lines = [
        header,
        f"Symbol: {tkr}",
        f"Timeframe: {itv}",
        f"Pattern: {z.pattern_name} ({zone_type})",
        f"Proximal: {z.proximal:.4f}",
        f"Distal: {z.distal:.4f}",
        f"Leg-out Formed: {legout_date}",
        f"Base Count: {z.base_count}",
        f"Leg-out Count: {z.legout_count}",
    ]
    if event["type"] == "tp_hit":
        lines.append(f"Target: {z.target:.4f}")
    elif event["type"] == "zone_found":
        lines.append(f"Target: {z.target:.4f}")

    return "\n".join(lines)


def render_zone_chart(df: pd.DataFrame, event: dict, tkr: str, itv: str):
    """Zone ke around candlestick chart PNG (bytes) banata hai, jo Telegram
    photo ke saath bheja jata hai. Kuch bhi galat ho to None return karta
    hai (caller text-only alert par fallback kar lega)."""
    try:
        z = event["zone"]
        lo = max(0, z.start_bar - 10)
        hi = min(len(df) - 1, max(z.end_bar, z.trigger_bar) + 15)
        sub = df.iloc[lo:hi + 1]
        if sub.empty:
            return None

        fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
        for idx, (_, row) in enumerate(sub.iterrows()):
            color = "#26a69a" if row["Close"] >= row["Open"] else "#ef5350"
            ax.plot([idx, idx], [row["Low"], row["High"]], color=color, linewidth=1)
            body_low = min(row["Open"], row["Close"])
            body_high = max(row["Open"], row["Close"])
            ax.add_patch(Rectangle((idx - 0.3, body_low), 0.6, max(body_high - body_low, 1e-6), color=color))

        top = max(z.proximal, z.distal)
        bottom = min(z.proximal, z.distal)
        start_x = z.start_bar - lo
        end_x = len(sub) - 1
        zone_color = "red" if z.is_supply else "green"
        ax.add_patch(Rectangle((start_x, bottom), max(end_x - start_x, 0.5), top - bottom,
                                color=zone_color, alpha=0.15))
        ax.axhline(z.proximal, color=zone_color, linestyle="--", linewidth=1, label="Proximal")
        ax.axhline(z.distal, color=zone_color, linestyle=":", linewidth=1, label="Distal")
        if event["type"] in ("tp_hit", "zone_found"):
            ax.axhline(z.target, color="blue", linestyle="--", linewidth=1, label="Target")

        ax.set_xlim(-1, len(sub))
        if itv in ("1d", "1wk"):
            labels = [ts.strftime("%d-%b-%y") for ts in sub.index]
        else:
            labels = [ts.strftime("%d-%b %H:%M") for ts in sub.index]
        step = max(1, len(labels) // 8)
        ticks = list(range(0, len(labels), step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([labels[i] for i in ticks], rotation=45, ha="right", fontsize=7)

        status_label = {"zone_found": "FRESH", "entered": "ENTERED", "sl_hit": "SL", "tp_hit": "TARGET"}.get(event["type"], "")
        ax.set_title(f"{tkr} [{itv}] - {z.pattern_name} {'Supply' if z.is_supply else 'Demand'} [{status_label}]", fontsize=10)
        ax.set_ylabel("Price")
        ax.legend(fontsize=7, loc="upper left")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"  [chart-error] {tkr} {itv}: {e}")
        return None


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

            for e in events:
                key = alert_key(tkr, itv, e)
                if key in sent_keys:
                    continue  # already alerted before -> skip (no duplicate)
                sent_keys.add(key)
                txt = build_text(tkr, itv, e, df)
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
