"""
alerts/notifier_telegram.py
────────────────────────────
Sends alert notifications to a Telegram bot with snapshot image.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

SEVERITY_EMOJI = {
    "low":    "🟡",
    "medium": "🟠",
    "high":   "🔴",
}

RULE_LABEL = {
    "loitering": "Loitering Detected",
    "trailing":  "Trailing / Stalking Pattern",
    "intrusion": "Restricted Zone Intrusion",
    "crowd":     "Crowd Density Alert",
    "abandoned": "Abandoned Object",
}


async def send_alert(
    event_id: str,
    camera_id: str,
    camera_name: str,
    rule_type: str,
    confidence: float,
    severity: str,
    snapshot_path: Optional[str] = None,
    zone_name: Optional[str] = None,
    dwell_time: Optional[float] = None,
) -> bool:
    """
    Send an alert message (+ snapshot) to Telegram.

    Returns True on success, False on failure.
    """
    if not BOT_TOKEN or not CHAT_ID or "your_bot_token" in BOT_TOKEN:
        logger.debug("Telegram credentials not configured — skipping notification.")
        return False

    emoji   = SEVERITY_EMOJI.get(severity, "⚠️")
    label   = RULE_LABEL.get(rule_type, rule_type.upper())
    zone_str = f"\n📍 Zone: *{zone_name}*" if zone_name else ""
    dwell_str = f"\n⏱️ Dwell time: *{dwell_time:.0f}s*" if dwell_time else ""

    message = (
        f"{emoji} *SentryEye Alert* — {label}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📷 Camera: *{camera_name}* (`{camera_id}`)\n"
        f"🎯 Severity: *{severity.upper()}*\n"
        f"📊 Confidence: *{confidence * 100:.0f}%*"
        f"{zone_str}"
        f"{dwell_str}\n"
        f"🆔 Event ID: `{event_id}`"
    )

    try:
        bot = Bot(token=BOT_TOKEN)

        if snapshot_path and os.path.isfile(snapshot_path):
            with open(snapshot_path, "rb") as photo:
                await bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=photo,
                    caption=message,
                    parse_mode="Markdown",
                )
        else:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode="Markdown",
            )

        logger.info(f"Telegram alert sent for event {event_id}")
        return True

    except TelegramError as e:
        logger.error(f"Telegram send failed: {e}")
        return False
