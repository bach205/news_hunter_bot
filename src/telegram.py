import requests

from src.config import CHAT_ID, TELEGRAM_MESSAGE_LIMIT, TELEGRAM_TOKEN


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


def send_telegram_message(text):
    if not text:
        print("Không có tin mới để gửi.")
        return

    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = split_message(text, limit=TELEGRAM_MESSAGE_LIMIT)
    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        res = requests.post(url, json=payload, timeout=30)
        if not res.ok:
            print(f"Lỗi gửi Telegram: {res.text}")
            # Fallback gửi text thuần nếu thẻ HTML bị lỗi
            payload.pop("parse_mode")
            requests.post(url, json=payload, timeout=30)
