# Free multi-source market data

The Streamlit dashboard and the three Telegram scanners now call the same
`data_sources.fetch_ohlcv()` function. The existing zone rules in
`pattern_engine.py`, alert de-duplication, Telegram formatting, and state
files are intentionally unchanged.

## Provider order

- Crypto pairs: Binance public 5-minute klines first, then Yahoo Finance.
- Other symbols: Yahoo Finance first.
- Optional Twelve Data fallback: set `TWELVEDATA_API_KEY` in the deployment
  environment. This is only attempted when the primary providers return no data.
- The returned dataframe uses a datetime index and normalized
  `Open, High, Low, Close` columns (plus `Volume` when supplied).

## Supported dashboard and scanner timeframes

`5m, 15m, 30m, 45m, 75m, 125m, 1H, 2H, 4H, 5H, 6H, 8H, 10H, 16H, 1D, 1W`

Non-native intraday intervals are built from 5-minute OHLCV candles in
`timeframe_builder.py`: Open=first, High=max, Low=min, Close=last, Volume=sum.
No missing source candles are filled. Incomplete buckets are excluded from
signals. Indian stock bars are aligned to 09:15 Asia/Kolkata; US stock bars to
09:30 America/New_York; forex and crypto bars to UTC.

## Important free-data limitations

- Yahoo Finance intraday history and availability are limited and can vary by
  symbol. A free source cannot guarantee every symbol/timeframe on every scan.
- Binance public klines are limited to the latest 1,000 5-minute candles per
  request in this implementation; this is not a full one-month history.
- Twelve Data free-plan quotas and supported markets/timeframes depend on its
  current plan. Supplying a key does not guarantee quota for large universes.
- 8H/10H/16H candles may not exist for exchange-traded stocks because their
  regular session is shorter than the requested interval. The builder drops
  incomplete session buckets rather than manufacturing candles.
- Exact TradingView matches are not guaranteed: feed, session, timezone, DST,
  and candle-boundary settings must match.
- Each bot continues to discard its latest candle before running the zone
  engine, preserving the existing closed-candle alert behavior.

## Deployment

No new required package was added; `requests` and `yfinance` are already in
`requirements.txt`. Add `TWELVEDATA_API_KEY` only if you have a key. Do not
put API keys in source files or commit them to GitHub.
