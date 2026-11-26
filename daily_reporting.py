"""Persistent daily reporting ledger and PDF/CSV Telegram reports.

This module observes the existing scanner output. It does not change zone
detection, entry, stop-loss, target, or lifecycle rules.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import time
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import pandas_market_calendars as mcal
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

LOG = logging.getLogger("daily_reporting")
ROOT = Path(__file__).resolve().parent
MARKETS = {
    "india": {"label": "India", "timezone": "Asia/Kolkata", "calendar": "XNSE",
              "chat_env": "TELEGRAM_CHAT_ID_INDIA"},
    "us": {"label": "US", "timezone": "America/New_York", "calendar": "NYSE",
           "chat_env": "TELEGRAM_CHAT_ID_US"},
    "forex": {"label": "Forex", "timezone": "America/New_York", "chat_env": "TELEGRAM_CHAT_ID_FOREX"},
}
CSV_FIELDS = [
    "zone_id", "market", "date", "formed_at", "symbol", "timeframe",
    "pattern", "zone_type", "proximal_entry", "distal_stoploss", "target",
    "risk_reward", "base_count", "legout_count", "status", "activated",
    "pre_alerted", "result_time", "alerts_sent"
]


def _iso(value):
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.isoformat()


def _zone_id(market, ticker, interval, zone, formed_at):
    raw = "|".join([
        market, ticker, interval, str(zone.pattern_name), _iso(formed_at),
        f"{float(zone.proximal):.10g}", f"{float(zone.distal):.10g}"
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ReportLedger:
    def __init__(self, market: str):
        if market not in MARKETS:
            raise ValueError(f"Unsupported report market: {market}")
        self.market = market
        self.path = ROOT / f"report_ledger_{market}.json"
        self.data = {"zones": {}, "events": {}, "sent_alerts": {}}
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    for key in self.data:
                        if isinstance(loaded.get(key), dict):
                            self.data[key] = loaded[key]
        except Exception:
            LOG.exception("Could not load report ledger %s", self.path)

    def record_scan(self, ticker, interval, df, result):
        if df is None or df.empty:
            return
        tz = ZoneInfo(MARKETS[self.market]["timezone"])
        for zone in result.all_zones:
            try:
                formed_at = df.index[int(zone.trigger_bar)]
                zone_id = _zone_id(self.market, ticker, interval, zone, formed_at)
                result_time = None
                for event in result.events:
                    if event.get("zone") is zone and event.get("type") in ("sl_hit", "tp_hit"):
                        result_time = _iso(df.index[int(event["bar"])])
                risk = abs(float(zone.distal) - float(zone.proximal))
                reward = abs(float(zone.target) - float(zone.proximal))
                formed_ts = pd.Timestamp(formed_at)
                if formed_ts.tzinfo is None:
                    formed_ts = formed_ts.tz_localize("UTC")
                formed_local = formed_ts.tz_convert(tz)
                self.data["zones"][zone_id] = {
                    "zone_id": zone_id, "market": self.market,
                    "date": formed_local.date().isoformat(),
                    "formed_at": formed_ts.isoformat(), "symbol": ticker,
                    "timeframe": interval, "pattern": str(zone.pattern_name),
                    "zone_type": "Supply" if zone.is_supply else "Demand",
                    "proximal_entry": float(zone.proximal),
                    "distal_stoploss": float(zone.distal), "target": float(zone.target),
                    "risk_reward": (round(reward / risk, 4) if risk else None),
                    "base_count": int(zone.base_count), "legout_count": int(zone.legout_count),
                    "status": str(zone.status), "activated": bool(zone.activated),
                    "pre_alerted": bool(zone.pre_alerted), "result_time": result_time,
                }
            except Exception:
                LOG.exception("Unable to record zone for %s %s", ticker, interval)

        for event in result.events:
            try:
                zone = event["zone"]
                formed_at = df.index[int(zone.trigger_bar)]
                zone_id = _zone_id(self.market, ticker, interval, zone, formed_at)
                event_at = _iso(df.index[int(event["bar"])])
                event_type = str(event["type"])
                event_id = f"{zone_id}|{event_type}|{event_at}"
                self.data["events"][event_id] = {
                    "event_id": event_id, "zone_id": zone_id, "market": self.market,
                    "symbol": ticker, "timeframe": interval, "event_type": event_type,
                    "event_at": event_at,
                }
            except Exception:
                LOG.exception("Unable to record lifecycle event")

    def record_alert_sent(self, ticker, interval, event, df):
        try:
            zone = event["zone"]
            formed_at = df.index[int(zone.trigger_bar)]
            zone_id = _zone_id(self.market, ticker, interval, zone, formed_at)
            event_at = _iso(df.index[int(event["bar"])])
            key = f"{zone_id}|{event['type']}|{event_at}"
            self.data["sent_alerts"][key] = {
                "zone_id": zone_id, "market": self.market, "symbol": ticker,
                "timeframe": interval, "event_type": str(event["type"]),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            LOG.exception("Unable to record successful Telegram alert")

    def save(self):
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, self.path)


def _read_ledger(market):
    path = ROOT / f"report_ledger_{market}.json"
    if not path.exists():
        return {"zones": {}, "events": {}, "sent_alerts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"zones": {}, "events": {}, "sent_alerts": {}}
    except Exception:
        LOG.exception("Ledger read failed: %s", path)
        return {"zones": {}, "events": {}, "sent_alerts": {}}


def _local_date(iso_value, tz_name):
    ts = pd.Timestamp(iso_value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(ZoneInfo(tz_name)).date().isoformat()


def _report_rows(market, day=None, since_utc=None):
    data = _read_ledger(market)
    tz_name = MARKETS[market]["timezone"]
    zones = []
    for zone in data.get("zones", {}).values():
        if day and zone.get("date") != day:
            continue
        if since_utc:
            try:
                if pd.Timestamp(zone["formed_at"]) < since_utc:
                    continue
            except Exception:
                continue
        row = dict(zone)
        row["alerts_sent"] = sum(1 for a in data.get("sent_alerts", {}).values()
                                 if a.get("zone_id") == row.get("zone_id"))
        zones.append(row)
    events = list(data.get("events", {}).values())
    if day:
        events = [e for e in events if _local_date(e["event_at"], tz_name) == day]
    elif since_utc:
        events = [e for e in events if pd.Timestamp(e["event_at"]) >= since_utc]
    sent = list(data.get("sent_alerts", {}).values())
    if day:
        sent = [a for a in sent if _local_date(a["sent_at"], tz_name) == day]
    elif since_utc:
        sent = [a for a in sent if pd.Timestamp(a["sent_at"]) >= since_utc]
    return zones, events, sent


def _summary(zones, events, sent):
    return {
        "total_zones": len(zones),
        "demand": sum(z["zone_type"] == "Demand" for z in zones),
        "supply": sum(z["zone_type"] == "Supply" for z in zones),
        "alerts_sent": len(sent),
        "target_hits": sum(e["event_type"] == "tp_hit" for e in events),
        "sl_hits": sum(e["event_type"] == "sl_hit" for e in events),
        "active": sum(z["status"] == "active" for z in zones),
        "untouched": sum(z["status"] == "active" and not z["activated"] for z in zones),
        "invalid": sum(z["status"] == "invalid" for z in zones),
        "entered": sum(e["event_type"] == "entered" for e in events),
    }


def _csv_bytes(zones):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for zone in sorted(zones, key=lambda x: x.get("formed_at", ""), reverse=True):
        writer.writerow(zone)
    return buf.getvalue().encode("utf-8-sig")


def _pdf_bytes(title, period, zones, summary):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Paragraph(f"Period: {period}", styles["Normal"]), Spacer(1, 12)]
    metrics = [
        ["Total zones", "Demand", "Supply", "Alerts sent", "Target hits", "SL hits", "Active", "Untouched", "Invalid"],
        [str(summary["total_zones"]), str(summary["demand"]), str(summary["supply"]),
         str(summary["alerts_sent"]), str(summary["target_hits"]), str(summary["sl_hits"]),
         str(summary["active"]), str(summary["untouched"]), str(summary["invalid"])]
    ]
    t = Table(metrics, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#243447")),
                           ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.grey),
                           ("ALIGN",(0,0),(-1,-1),"CENTER"),("PADDING",(0,0),(-1,-1),6)]))
    story += [t, Spacer(1, 14)]
    detail = [["Symbol","TF","Pattern","Type","Entry","SL","Target","RR","Base","Legout","Status"]]
    for z in zones:
        detail.append([str(z.get("symbol","")),str(z.get("timeframe","")),str(z.get("pattern","")),
                       str(z.get("zone_type","")),f'{float(z.get("proximal_entry",0)):.8g}',
                       f'{float(z.get("distal_stoploss",0)):.8g}',f'{float(z.get("target",0)):.8g}',
                       str(z.get("risk_reward") or ""),str(z.get("base_count","")),
                       str(z.get("legout_count","")),str(z.get("status",""))])
    table = Table(detail, repeatRows=1, colWidths=[75,38,45,48,60,60,60,35,35,40,48])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#243447")),
                               ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.25,colors.lightgrey),
                               ("FONTSIZE",(0,0),(-1,-1),7),("PADDING",(0,0),(-1,-1),3)]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()


def _send_document(token, chat_id, payload, filename, caption, max_attempts=3):
    """Upload one Telegram document, retrying transient network/server failures."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"document": (filename, payload)},
                timeout=(15, 90),
            )

            # Telegram rate limits are retryable; honor its suggested wait time.
            if response.status_code == 429:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                retry_after = body.get("parameters", {}).get("retry_after", 2)
                last_error = RuntimeError(f"Telegram rate limited the upload (429): {body}")
                if attempt < max_attempts:
                    wait_seconds = max(1, min(int(retry_after), 30))
                    LOG.warning(
                        "Telegram rate limit for %s; attempt %s/%s, waiting %ss",
                        filename, attempt, max_attempts, wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise last_error

            # Retry server-side failures; ordinary 4xx errors usually need
            # a configuration/payload correction and should fail immediately.
            if response.status_code >= 500:
                last_error = requests.HTTPError(
                    f"Telegram server error {response.status_code}: {response.text[:500]}",
                    response=response,
                )
                if attempt < max_attempts:
                    wait_seconds = 2 ** attempt
                    LOG.warning(
                        "Telegram server error uploading %s; attempt %s/%s, retrying in %ss",
                        filename, attempt, max_attempts, wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise last_error

            response.raise_for_status()
            body = response.json()
            if not body.get("ok"):
                raise RuntimeError(f"Telegram document send failed: {body}")
            LOG.info("Telegram document delivered: %s (attempt %s)", filename, attempt)
            return True

        except (requests.ConnectionError, requests.Timeout, requests.ChunkedEncodingError) as exc:
            last_error = exc
            if attempt >= max_attempts:
                LOG.exception("Telegram upload failed after %s attempts: %s", max_attempts, filename)
                raise
            wait_seconds = 2 ** attempt
            LOG.warning(
                "Temporary Telegram connection failure for %s; attempt %s/%s, retrying in %ss: %s",
                filename, attempt, max_attempts, wait_seconds, exc,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"Telegram upload failed for {filename}: {last_error}")


def send_report(market, period, zones, events, sent, chat_id=None, title=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    cfg = MARKETS.get(market)
    if not token or (not cfg and market != "combined"):
        raise RuntimeError("TELEGRAM_BOT_TOKEN or market configuration missing")
    chat_id = chat_id or (os.getenv(cfg["chat_env"], "") if cfg else "")
    if market == "combined" and not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID_COMBINED") or os.getenv("TELEGRAM_CHAT_ID_INDIA", "")
    if not chat_id:
        raise RuntimeError(f"Telegram chat id missing for {market}")
    summary = _summary(zones, events, sent)
    label = title or (cfg["label"] if cfg else "Combined")
    caption = (f"📊 {label} Daily Report\nPeriod: {period}\n"
               f"Zones: {summary['total_zones']} | Demand: {summary['demand']} | Supply: {summary['supply']}\n"
               f"Alerts: {summary['alerts_sent']} | TP: {summary['target_hits']} | SL: {summary['sl_hits']}\n"
               f"Active: {summary['active']} | Untouched: {summary['untouched']} | Invalid: {summary['invalid']}")
    csv_payload = _csv_bytes(zones)
    pdf_payload = _pdf_bytes(f"{label} Daily Report", period, zones, summary)
    safe = label.lower().replace(" ", "_")
    _send_document(token, chat_id, pdf_payload, f"{safe}_{period}.pdf", caption)
    _send_document(token, chat_id, csv_payload, f"{safe}_{period}.csv", f"{label} CSV — {len(zones)} zones")
    return summary


def _report_state():
    path = ROOT / "report_state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        LOG.exception("Report state is unreadable")
        return {}


def _save_report_state(state):
    path = ROOT / "report_state.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _session_due(market, now_utc):
    cfg = MARKETS[market]
    local_now = now_utc.tz_convert(cfg["timezone"])
    day = local_now.date().isoformat()
    try:
        cal = mcal.get_calendar(cfg["calendar"])
        schedule = cal.schedule(start_date=day, end_date=day)
        if schedule.empty:
            return None
        close_utc = pd.Timestamp(schedule.iloc[0]["market_close"])
        if close_utc.tzinfo is None:
            close_utc = close_utc.tz_localize("UTC")
        if now_utc >= close_utc + pd.Timedelta(minutes=10):
            return day
    except Exception:
        LOG.exception("Exchange calendar check failed for %s", market)
    return None


def run_due_reports():
    now = pd.Timestamp.now(tz="UTC")
    state = _report_state()
    sent_any = False

    for market in ("india", "us"):
        day = _session_due(market, now)
        key = f"{market}:{day}" if day else None
        if key and not state.get(key):
            zones, events, sent = _report_rows(market, day=day)
            send_report(market, day, zones, events, sent)
            state[key] = datetime.now(timezone.utc).isoformat()
            _save_report_state(state)
            sent_any = True
            LOG.info("Sent %s report for %s", market, day)

    ny_now = now.tz_convert("America/New_York")
    forex_day = ny_now.date().isoformat()
    forex_key = f"forex:{forex_day}"
    if ny_now.weekday() < 5 and (ny_now.hour, ny_now.minute) >= (17, 10) and not state.get(forex_key):
        zones, events, sent = _report_rows("forex", day=forex_day)
        send_report("forex", forex_day, zones, events, sent)
        state[forex_key] = datetime.now(timezone.utc).isoformat()
        _save_report_state(state)
        sent_any = True
        LOG.info("Sent Forex report for %s", forex_day)

    # One combined rolling 24-hour report after the New York 5 PM rollover.
    # At 17:10 New York, delivery is about 03:40 IST in US winter or 02:40 IST in US summer.
    combined_day = forex_day
    combined_key = f"combined:{combined_day}"
    if ny_now.weekday() < 5 and (ny_now.hour, ny_now.minute) >= (17, 15) and not state.get(combined_key):
        since = now - pd.Timedelta(hours=24)
        all_zones, all_events, all_sent = [], [], []
        for market in ("india", "us", "forex"):
            z, e, s = _report_rows(market, since_utc=since)
            all_zones.extend(z); all_events.extend(e); all_sent.extend(s)
        send_report("combined", combined_day, all_zones, all_events, all_sent,
                    title="Combined (rolling 24h)")
        state[combined_key] = datetime.now(timezone.utc).isoformat()
        _save_report_state(state)
        sent_any = True
        LOG.info("Sent combined report for %s", combined_day)

    if not sent_any:
        LOG.info("No market report is due right now")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_due_reports()
