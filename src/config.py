import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

HISTORY_FILE = "seen_links.json"
MAX_SEEN_LINKS = 500
MAX_ARTICLES_PER_FEED = 5
ARTICLE_SUMMARY_LIMIT = 350
TELEGRAM_MESSAGE_LIMIT = 4000

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
GEMINI_FALLBACK_CODES = {404, 429, 500, 502, 503, 504}
OPENROUTER_FREE_MODEL = "openrouter/free"

RSS_FEEDS = {
    # --- NHÓM REUTERS (Ưu tiên lấy nhiều) ---
    "Reuters - Tin Hot Trong Ngày": {
        "url": "https://news.google.com/rss/search?q=site:reuters.com+when:12h&hl=en-US&gl=US&ceid=US:en",
        "limit": 5,
    },
    "Reuters - Chính trị & Thế giới": {
        "url": "https://news.google.com/rss/search?q=site:reuters.com/world+when:1d&hl=en-US&gl=US&ceid=US:en",
        "limit": 5,
    },
    "Reuters - Công nghệ": {
        "url": "https://news.google.com/rss/search?q=site:reuters.com/technology+when:1d&hl=en-US&gl=US&ceid=US:en",
        "limit": 5,
    },
    # --- CÁC NGUỒN BỔ SUNG (Giảm nhẹ để không lấn át Reuters) ---
    "VnExpress - Thời sự": {
        "url": "https://vnexpress.net/rss/thoi-su.rss",
        "limit": 5,
    },
    "VnExpress - Thế giới": {
        "url": "https://vnexpress.net/rss/the-gioi.rss",
        "limit": 5,
    },
    "VnExpress - Công nghệ": {
        "url": "https://vnexpress.net/rss/so-hoa.rss",
        "limit": 5,
    },
    "VietNamNet - Tin nóng": {
        "url": "https://vietnamnet.vn/home.rss",
        "limit": 5,
    },
    "Hacker News (Hot Tech)": {
        "url": "https://hnrss.org/frontpage?points=100",
        "limit": 4,
    },
    # Thêm tài khoản X hoặc Threads qua RSSHub tại đây (ví dụ):
    # "X - Reuters": {"url": "https://rsshub.app/twitter/user/reuters", "limit": 5},
    # "Threads - Zuckerberg": {"url": "https://rsshub.app/threads/zuck", "limit": 5},
}
