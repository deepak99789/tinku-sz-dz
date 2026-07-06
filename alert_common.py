"""
alert_common.py - Shared alert text + chart builder

Ye module Streamlit app (app.py) aur 24x7 background bot (alert_bot.py)
DONO use karte hain, taaki Telegram par jaane wala alert ka design hamesha
same/consistent rahe - ek jagah update karo, dono jagah reflect ho jayega.
"""

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ALERT_ICONS = {
    "zone_found": "✅",
    "entered": "🔵",
    "sl_hit": "🚨",
    "tp_hit": "🎯",
    "pre_alert": "🔔",
}

# Har event type zone ki KIS status-stage se related hai - "Fresh" (active),
# "SL" ya "Target". app.py (manual) aur alert_bot.py (24x7 background bot)
# DONO isi mapping ko use karke apna "sirf fresh zone ka alert bhejo" (ya
# sirf SL/Target) wala filter apply karte hain - taaki dono jagah same rule
# rahe aur ek jagah update karne se dusri jagah bhi automatically reflect ho.
EVENT_STATUS_MAP = {
    "zone_found": "active",
    "pre_alert": "active",
    "entered": "active",
    "sl_hit": "sl",
    "tp_hit": "tp",
}


def alert_key(tkr: str, itv: str, event: dict) -> str:
    """Unique key per (ticker, interval, event type, zone, bar) - isse same
    alert dobara (duplicate) nahi bheja/dikhaya jayega."""
    z = event["zone"]
    return f"{tkr}|{itv}|{event['type']}|{z.pattern_name}|{event['bar']}|{round(z.proximal, 4)}"


def build_alert_text(tkr: str, itv: str, event: dict, df, rr_target: float) -> str:
    """Har alert type (zone_found / entered / sl_hit / tp_hit) me same
    detailed info deta hai: symbol, timeframe, pattern, type, proximal,
    distal, leg-out formation date, base candle count, leg-out candle count."""
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
        "tp_hit": f"🎯 TARGET HIT (1:{rr_target:g})",
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
    if event["type"] in ("zone_found", "tp_hit"):
        lines.append(f"Target: {z.target:.4f}")

    return "\n".join(lines)


def render_zone_chart(df, event: dict, tkr: str, itv: str):
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
    except Exception:
        return None
