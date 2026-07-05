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
