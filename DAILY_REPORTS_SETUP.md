# Daily Market Reports — Tinku SZ-DZ

This feature adds four Telegram report deliveries without changing the existing pattern detector or its Entry / SL / Target lifecycle rules.

## Reports and delivery time

- India: after the NSE cash-market session closes (calendar close + 10 minutes).
- US: after the NYSE regular session closes (calendar close + 10 minutes).
- Forex: after the New York 5:00 PM rollover (17:10 America/New_York). In India this is approximately 3:40 AM IST during US standard time and 2:40 AM IST during US daylight-saving time. The 5:00 PM rollover itself is approximately 3:30 AM IST / 2:30 AM IST respectively.
- Combined: at 17:15 America/New_York, covering the trailing 24 hours across India, US, and Forex. This is a rolling 24-hour combined report, not a same-calendar-date aggregation, because the markets use different timezones.

The report workflow checks every five minutes. GitHub Actions cron is not second-accurate, so delivery can be several minutes late. Exchange-calendar holidays are skipped; calendars may not immediately reflect an exceptional same-day exchange closure, so confirm exceptional holiday notices separately.

## Telegram secrets

The scanner already expects these repository Actions secrets:

- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID_INDIA
- TELEGRAM_CHAT_ID_US
- TELEGRAM_CHAT_ID_FOREX

Optional:
- TELEGRAM_CHAT_ID_COMBINED — if omitted, the combined report goes to TELEGRAM_CHAT_ID_INDIA.

The report sends a PDF and a CSV as two Telegram documents. Both files contain the complete report-period zone list. The PDF includes the summary and a detailed zone table; the CSV contains machine-readable columns including formed time, market, symbol, timeframe, RBR/RBD/DBR/DBD pattern, Demand/Supply, Entry/Proximal, SL/Distal, Target, RR, base/legout counts, status, result time, and alert count.

## Persistence and duplicate handling

Each market scanner updates its own committed JSON ledger:

- report_ledger_india.json
- report_ledger_us.json
- report_ledger_forex.json

Zone IDs are deterministic from market, symbol, timeframe, pattern, formation timestamp, and zone boundaries. Repeated five-minute scans update the same zone instead of adding another row. Lifecycle events and successful Telegram alert sends are stored separately. report_state.json prevents a report for the same market/session date from being sent twice.

The ledger is stored in the repository because GitHub Actions runners are ephemeral. The existing scanner workflows commit their market ledger alongside their alert-state JSON file.

## Status meanings

- Active: zone is still active according to the existing engine.
- Untouched: active and not yet entered/activated.
- Target / SL: counted from the engine's actual tp_hit / sl_hit events.
- Invalid: counted only if the engine records status invalid. The current lifecycle engine does not emit an invalid status, so this may remain zero.

## Enable

After merging the feature branch, open the repository Actions tab and make sure Daily Market Reports is enabled. Run it manually once to verify secrets and Telegram delivery. The report workflow runs independently of the Streamlit browser session and does not require your computer to stay on.
