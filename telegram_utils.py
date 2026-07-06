"""
telegram_utils.py

Minimal Telegram Bot API wrapper - mirrors the Pine Script's
alert(nlb_msg, alert.freq_once_per_bar) webhook behaviour, but sends
straight to Telegram instead of going through TradingView's alert webhook.

Setup:
1. Message @BotFather on Telegram -> /newbot -> get your BOT_TOKEN
2. Message your new bot once, then open:
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   to find your CHAT_ID
3. Paste both into the Streamlit sidebar (or store as env vars / secrets)
"""

import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Bot token or chat id missing."
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
        if resp.status_code == 200:
            return True, "sent"
        return False, f"Telegram API error {resp.status_code}: {resp.text}"
    except requests.RequestException as e:
        return False, f"Request failed: {e}"


def send_telegram_photo(bot_token: str, chat_id: str, photo_bytes: bytes, caption: str = "") -> tuple[bool, str]:
    """Zone ka chart image Telegram par bhejta hai, caption ke saath.
    Telegram caption limit ~1024 characters hai, isliye zyada lamba
    caption automatically trim ho jata hai."""
    if not bot_token or not chat_id:
        return False, "Bot token or chat id missing."
    if not photo_bytes:
        return False, "No photo bytes provided."
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        files = {"photo": ("zone_chart.png", photo_bytes, "image/png")}
        data = {"chat_id": chat_id, "caption": caption[:1024]}
        resp = requests.post(url, data=data, files=files, timeout=20)
        if resp.status_code == 200:
            return True, "sent"
        return False, f"Telegram API error {resp.status_code}: {resp.text}"
    except requests.RequestException as e:
        return False, f"Request failed: {e}"
