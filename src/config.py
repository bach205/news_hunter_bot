import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALERT_CHAT_ID = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "") or CHAT_ID
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

RSSHUB_BASE_URL = os.environ.get("RSSHUB_BASE_URL", "http://127.0.0.1:1200").rstrip("/")
FEEDS_FILE = Path(os.environ.get("FEEDS_FILE", str(BASE_DIR / "feeds.json")))
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", str(BASE_DIR / "seen_links.json")))

MAX_SEEN_LINKS = int(os.environ.get("MAX_SEEN_LINKS", "1000"))
MAX_ARTICLES_PER_FEED = int(os.environ.get("MAX_ARTICLES_PER_FEED", "5"))
ARTICLE_SUMMARY_LIMIT = int(os.environ.get("ARTICLE_SUMMARY_LIMIT", "350"))
TELEGRAM_MESSAGE_LIMIT = 4000

FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "25"))
FETCH_RETRIES = int(os.environ.get("FETCH_RETRIES", "2"))
SEND_ERROR_ALERTS = os.environ.get("SEND_ERROR_ALERTS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

CRON_SCHEDULE = os.environ.get("CRON_SCHEDULE", "17 6,14,22 * * *")
RUN_ON_STARTUP = os.environ.get("RUN_ON_STARTUP", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
GEMINI_FALLBACK_CODES = {404, 429, 500, 502, 503, 504}
OPENROUTER_FREE_MODEL = "openrouter/free"

DEFAULT_FEEDS = [
    {
        "name": "Reuters - Tin Hot Trong Ngày",
        "url": "https://news.google.com/rss/search?q=site:reuters.com+when:12h&hl=en-US&gl=US&ceid=US:en",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "Reuters - Chính trị & Thế giới",
        "url": "https://news.google.com/rss/search?q=site:reuters.com/world+when:1d&hl=en-US&gl=US&ceid=US:en",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "Reuters - Công nghệ",
        "url": "https://news.google.com/rss/search?q=site:reuters.com/technology+when:1d&hl=en-US&gl=US&ceid=US:en",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "VnExpress - Thời sự",
        "url": "https://vnexpress.net/rss/thoi-su.rss",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "VnExpress - Thế giới",
        "url": "https://vnexpress.net/rss/the-gioi.rss",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "VnExpress - Công nghệ",
        "url": "https://vnexpress.net/rss/so-hoa.rss",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "VietNamNet - Tin nóng",
        "url": "https://vietnamnet.vn/home.rss",
        "platform": "rss",
        "category": "news",
        "limit": 5,
        "enabled": True,
    },
    {
        "name": "Hacker News (Hot Tech)",
        "url": "https://hnrss.org/frontpage?points=100",
        "platform": "rss",
        "category": "news",
        "limit": 4,
        "enabled": True,
    },
]


def load_feeds(path=FEEDS_FILE):
    """Đọc danh sách RSS feeds từ feeds.json (fallback về DEFAULT_FEEDS nếu chưa có)."""
    feed_path = Path(path)
    if feed_path.exists():
        with feed_path.open("r", encoding="utf-8") as f:
            raw_feeds = json.load(f)
    else:
        raw_feeds = DEFAULT_FEEDS

    resolved = []
    for item in raw_feeds:
        if not item.get("enabled", True):
            continue
        url = str(item["url"]).replace("{RSSHUB_BASE_URL}", RSSHUB_BASE_URL)
        uses_rsshub = "{RSSHUB_BASE_URL}" in str(item["url"]) or url.startswith(
            RSSHUB_BASE_URL
        )
        resolved.append(
            {
                "name": item["name"],
                "url": url,
                "platform": item.get("platform", "rss").lower(),
                "category": item.get("category", "news").lower(),
                "limit": int(item.get("limit", MAX_ARTICLES_PER_FEED)),
                "skip_retweets": bool(item.get("skip_retweets", False)),
                "uses_rsshub": uses_rsshub,
            }
        )
    return resolved
