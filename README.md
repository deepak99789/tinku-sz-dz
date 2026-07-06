# 📊 Demand & Supply Dashboard (Streamlit)

Python/Streamlit port of a TradingView Pine Script indicator that detects
**Rally-Base-Drop (RBD)**, **Drop-Base-Drop (DBD)**, **Drop-Base-Rally (DBR)**,
and **Rally-Base-Rally (RBR)** supply/demand zones — with 1, 2, or 3 base-candle
variants, ATR-based buffers, a 1:R risk-to-reward target, and full
pre-alert → entry → SL/TP zone lifecycle tracking.

Works across markets via [yfinance](https://pypi.org/project/yfinance/):

| Market | Example tickers |
|---|---|
| Indian Stocks (NSE) | `RELIANCE.NS`, `TCS.NS`, `INFY.NS` |
| Indian Stocks (BSE) | `RELIANCE.BO`, `TCS.BO` |
| US Stocks / Index | `AAPL`, `TSLA`, `^GSPC` |
| Forex | `EURUSD=X`, `USDINR=X` |
| Commodity | `GC=F` (Gold), `CL=F` (Crude), `SI=F` (Silver) |
| Crypto | `BTC-USD`, `ETH-USD` |

## Features

- 4 pattern types × 4 base-candle variants (1 / 2 / 3 base candles, "All")
- Base Candle Count filter dropdown (same as the Pine Script input)
- ATR-based zone buffer & pre-entry "upcoming trade" distance
- Configurable Risk:Reward target
- Interactive Plotly candlestick chart with zone boxes, SL/TP tags
- Zone log table (proximal / distal / target / status)
- Optional Telegram bot alerts (zone found, entered, SL hit, TP hit)

## Project structure

```
.
├── app.py               # Streamlit UI
├── pattern_engine.py    # Pattern detection + zone lifecycle logic
├── telegram_utils.py    # Telegram Bot API helper
├── requirements.txt
├── .streamlit/config.toml
└── README.md
```

## Run locally

```bash
git clone https://github.com/<your-username>/demand-supply-dashboard.git
cd demand-supply-dashboard
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select the repo, branch, and `app.py` as the entry point.
4. Deploy. (No secrets needed unless you want default Telegram values —
   in that case add `BOT_TOKEN` / `CHAT_ID` under **Settings → Secrets**.)

## Telegram alerts setup (optional)

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the **Bot Token**.
2. Send your new bot any message, then open:
   `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` to find your **Chat ID**.
3. Paste both into the sidebar in the app (or store as Streamlit secrets).

## 🔔 24x7 Telegram Alerts (PC off hone par bhi)

Streamlit app ke Telegram alerts sirf tab kaam karte hain jab app browser me
khula ho. Agar PC/laptop band hone par bhi alerts chahiye, `alert_bot.py`
use karo - GitHub Actions par chalta hai, aapka PC ON hona zaroori nahi.
Poori setup guide: [SETUP_24x7_ALERTS.md](SETUP_24x7_ALERTS.md)

## Notes

- Pattern rules (candle-body %, leg-in/leg-out ratios, wick-safety checks) are
  a direct 1:1 port of the original Pine Script — same thresholds, same logic.
- yfinance intraday history is limited by Yahoo Finance itself
  (e.g. ~60 days for 5m/15m/30m candles) — the app auto-suggests a sensible
  history period per interval.
- This is an educational/technical-analysis tool, **not financial advice**.
