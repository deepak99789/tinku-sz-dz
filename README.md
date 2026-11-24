# 📊 Demand & Supply Dashboard (Streamlit)

Python/Streamlit port of a TradingView Pine Script indicator that detects
**Rally-Base-Drop (RBD)**, **Drop-Base-Drop (DBD)**, **Drop-Base-Rally (DBR)**,
and **Rally-Base-Rally (RBR)** supply/demand zones — with 1, 2, or 3 base-candle
variants, ATR-based buffers, a 1:R risk-to-reward target, and full
pre-alert → entry → SL/TP zone lifecycle tracking.

Uses a free multi-source Forex feed (Yahoo Finance first, then optional Twelve Data / Alpha Vantage fallbacks). Other markets continue to use [yfinance](https://pypi.org/project/yfinance/):

| Market | Example tickers |
|---|---|
| Indian Stocks (NSE) | `RELIANCE.NS`, `TCS.NS`, `INFY.NS` |
| Indian Stocks (BSE) | `RELIANCE.BO`, `TCS.BO` |
| US Stocks / Index | `AAPL`, `TSLA`, `^GSPC` |
| Forex | 28 standard pairs (7 USD majors + 21 crosses), e.g. `EURUSD=X`, `GBPJPY=X` |
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

## Forex data source (Free Multi-Source)

The Dashboard and `alert_bot_forex.py` share the same `forex_data.py` module and the same 28-pair list. Data-source order:

1. Yahoo Finance (no API key)
2. Twelve Data (optional `TWELVEDATA_API_KEY`)
3. Alpha Vantage (optional `ALPHAVANTAGE_API_KEY`)

For the full fallback chain, add the optional API keys under Streamlit Cloud **Settings → Secrets** and GitHub **Settings → Secrets and variables → Actions**. Without those keys, Yahoo Finance remains the only available Forex source. Free-provider quotas, supported intervals, and market coverage can vary; 90-minute and 3-month candles currently rely on Yahoo Finance.

## Notes

- Pattern rules (candle-body %, leg-in/leg-out ratios, wick-safety checks) are
  a direct 1:1 port of the original Pine Script — same thresholds, same logic.
- yfinance intraday history is limited by Yahoo Finance itself
  (e.g. ~60 days for 5m/15m/30m candles) — the app auto-suggests a sensible
  history period per interval.
- This is an educational/technical-analysis tool, **not financial advice**.
