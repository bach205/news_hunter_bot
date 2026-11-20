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
