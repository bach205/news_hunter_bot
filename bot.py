import os
import json
import re
import feedparser
import requests
from google import genai

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

HISTORY_FILE = "seen_links.json"

RSS_FEEDS = {
    "VnExpress - Thời sự": "https://vnexpress.net/rss/thoi-su.rss",
    "VnExpress - Thế giới": "https://vnexpress.net/rss/the-gioi.rss",
    "VnExpress - Công nghệ": "https://vnexpress.net/rss/so-hoa.rss",
    "VietNamNet - Thời sự": "https://vietnamnet.vn/rss/thoi-su.rss",
    "VietNamNet - Tin nóng": "https://vietnamnet.vn/home.rss",
    "Hacker News (Hot Tech)": "https://hnrss.org/frontpage?points=100",
    "Reuters (World & Politics)": "https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    # Thêm tài khoản X hoặc Threads qua RSSHub tại đây (ví dụ):
    # "X - Reuters": "https://rsshub.app/twitter/user/reuters",
    # "Threads - Zuckerberg": "https://rsshub.app/threads/zuck",
}


def load_seen_links():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def save_seen_links(links):
    recent_links = links[-500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(recent_links, f, ensure_ascii=False, indent=2)


def fetch_latest_news():
    seen_list = load_seen_links()
    seen_set = set(seen_list)
    new_articles = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= 5:
                    break
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:350]

                if link and link not in seen_set:
                    new_articles.append(f"[{source}] {title}\nMô tả: {summary}\nLink: {link}")
                    seen_set.add(link)
                    seen_list.append(link)
                    count += 1
        except Exception as e:
            print(f"Lỗi nguồn {source}: {e}")

    save_seen_links(seen_list)
    return new_articles


def summarize_with_ai(articles):
    if not articles:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    raw_text = "\n\n".join(articles)

    prompt = f"""
    Bạn là biên tập viên tin tức cá nhân. Dưới đây là danh sách các tin tức thô vừa thu thập:
    
    {raw_text}
    
    Hãy lọc và tổng hợp lại thành bản tin súc tích theo gu: Chính trị, Công nghệ, Tin nóng. Chia làm 3 phần:
    <b>🏛 CHÍNH TRỊ & THẾ GIỚI</b>
    <b>💻 CÔNG NGHỆ NỔI BẬT</b>
    <b>🔥 TIN NÓNG TRONG NƯỚC</b>
    
    Quy tắc định dạng BẮT BUỘC (chỉ dùng HTML cơ bản của Telegram):
    - Chỉ sử dụng các thẻ: <b>in đậm</b>, <i>in nghiêng</i>, <a href="URL">Đọc gốc</a>. Tuyệt đối KHÔNG dùng Markdown (*, #, ```).
    - Chọn 8-12 tin đắt giá nhất, bỏ qua tin rác/giật gân vô thưởng vô phạt.
    - Mỗi tin gồm tiêu đề in đậm, 2 gạch đầu dòng tóm tắt cốt lõi (số liệu, tác động chính) và link <a href="link">Đọc gốc</a> ở cuối.
    - Dịch tin tiếng Anh sang tiếng Việt tự nhiên, chuẩn thuật ngữ công nghệ/chính trị.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = (response.text or "").strip()
    # Loại bỏ cặp code fence nếu model lỡ bọc kết quả trong ```html ... ```
    text = re.sub(r"^```(?:html)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text


def split_message(text, limit=4000):
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
                chunks.append(line[i:i + limit])
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

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = split_message(text, limit=4000)
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


if __name__ == "__main__":
    articles = fetch_latest_news()
    summary = summarize_with_ai(articles)
    send_telegram_message(summary)
