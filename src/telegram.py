import html
import logging

import requests

from src.config import (
    ALERT_CHAT_ID,
    CHAT_ID,
    SEND_ERROR_ALERTS,
    TELEGRAM_MESSAGE_LIMIT,
    TELEGRAM_TOKEN,
)

logger = logging.getLogger(__name__)


def split_message(text, limit=TELEGRAM_MESSAGE_LIMIT):
    """Chia nhỏ tin nhắn theo dòng để tránh cắt ngang thẻ HTML."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append("".join(current))
                current = []
                current_len = 0
            for i in range(0, len(line), limit):
                chunks.append(line[i : i + limit])
            continue

        if current_len + len(line) > limit:
            chunks.append("".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line)

    if current:
        chunks.append("".join(current))
    return chunks


def _post_chunks(text, chat_id):
    if not TELEGRAM_TOKEN or not chat_id:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = split_message(text, limit=TELEGRAM_MESSAGE_LIMIT)
    all_ok = True

    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        res = requests.post(url, json=payload, timeout=30)
        if not res.ok:
            logger.warning("Lỗi gửi Telegram (HTML): %s", res.text)
            payload.pop("parse_mode")
            fallback_res = requests.post(url, json=payload, timeout=30)
            if not fallback_res.ok:
                logger.error(
                    "Lỗi gửi Telegram (text thuần): %s", fallback_res.text
                )
                all_ok = False

    return all_ok


def send_telegram_message(text):
    if not text:
        logger.info("Không có tin mới để gửi.")
        return False

    return _post_chunks(text, CHAT_ID)


def send_alert_message(title, details):
    """Gửi cảnh báo ngắn về Telegram khi RSSHub/token X/Threads hoặc bot gặp sự cố."""
    if not SEND_ERROR_ALERTS:
        return False
    if not TELEGRAM_TOKEN or not ALERT_CHAT_ID:
        return False

    safe_title = html.escape(str(title))
    if isinstance(details, (list, tuple)):
        body_lines = [f"• {html.escape(str(line))}" for line in details]
        body = "\n".join(body_lines)
    else:
        body = html.escape(str(details))

    message = f"⚠️ <b>{safe_title}</b>\n{body}"
    try:
        return _post_chunks(message, ALERT_CHAT_ID)
    except Exception as exc:
        logger.error("Không thể gửi cảnh báo Telegram: %s", exc)
        return False
