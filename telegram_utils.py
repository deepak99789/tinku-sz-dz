"""
telegram_utils.py

Minimal Telegram Bot API wrapper - with RATE LIMITING to avoid 429 errors.
"""

import requests
import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

# 🔥 Rate Limiting Configuration
MAX_MESSAGES_PER_MINUTE = 20  # Safe limit (Telegram allows ~30/min)
MESSAGE_HISTORY = deque(maxlen=MAX_MESSAGES_PER_MINUTE)


def wait_if_needed():
    """Check if we need to wait before sending next message"""
    global MESSAGE_HISTORY
    
    now = time.time()
    # Remove messages older than 60 seconds
    while MESSAGE_HISTORY and now - MESSAGE_HISTORY[0] > 60:
        MESSAGE_HISTORY.popleft()
    
    # If we've sent too many messages in last 60 seconds, wait
    if len(MESSAGE_HISTORY) >= MAX_MESSAGES_PER_MINUTE:
        wait_time = 60 - (now - MESSAGE_HISTORY[0]) + 1
        if wait_time > 0:
            logger.warning(f"⏱️ Rate limit reached. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
    
    # Record this message
    MESSAGE_HISTORY.append(time.time())


def send_telegram_message(bot_token: str, chat_id: str, text: str, max_retries: int = 5) -> tuple[bool, str]:
    """Send message with rate limiting and retry logic"""
    if not bot_token or not chat_id:
        return False, "Bot token or chat id missing."
    
    # 🔥 Wait if rate limit is near
    wait_if_needed()
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url, 
                data={"chat_id": chat_id, "text": text[:4096]},  # Telegram text limit
                timeout=10
            )
            
            if resp.status_code == 200:
                return True, "sent"
            
            # Handle rate limit specifically
            if resp.status_code == 429:
                data = resp.json()
                retry_after = data.get("parameters", {}).get("retry_after", 30)
                logger.warning(f"⚠️ Rate limit hit. Retry after {retry_after}s (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_after + 1)  # Wait + extra second
                continue
                
            return False, f"Telegram API error {resp.status_code}: {resp.text}"
            
        except requests.RequestException as e:
            logger.error(f"Request failed (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return False, f"Request failed: {e}"
    
    return False, "Max retries exceeded"


def send_telegram_photo(bot_token: str, chat_id: str, photo_bytes: bytes, caption: str = "", max_retries: int = 5) -> tuple[bool, str]:
    """Send photo with rate limiting and retry logic"""
    if not bot_token or not chat_id:
        return False, "Bot token or chat id missing."
    if not photo_bytes:
        return False, "No photo bytes provided."
    
    # 🔥 Wait if rate limit is near
    wait_if_needed()
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    for attempt in range(max_retries):
        try:
            files = {"photo": ("zone_chart.png", photo_bytes, "image/png")}
            data = {"chat_id": chat_id, "caption": caption[:1024]}  # Telegram caption limit
            resp = requests.post(url, data=data, files=files, timeout=20)
            
            if resp.status_code == 200:
                return True, "sent"
            
            # Handle rate limit specifically
            if resp.status_code == 429:
                data = resp.json()
                retry_after = data.get("parameters", {}).get("retry_after", 30)
                logger.warning(f"⚠️ Rate limit hit. Retry after {retry_after}s (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_after + 1)  # Wait + extra second
                continue
                
            return False, f"Telegram API error {resp.status_code}: {resp.text}"
            
        except requests.RequestException as e:
            logger.error(f"Request failed (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return False, f"Request failed: {e}"
    
    return False, "Max retries exceeded"
