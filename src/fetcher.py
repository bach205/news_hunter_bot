import feedparser

from src.config import (
    ARTICLE_SUMMARY_LIMIT,
    MAX_ARTICLES_PER_FEED,
    RSS_FEEDS,
)
from src.storage import load_seen_links, save_seen_links


def fetch_latest_news():
    seen_list = load_seen_links()
    seen_set = set(seen_list)
    new_articles = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= MAX_ARTICLES_PER_FEED:
                    break
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:ARTICLE_SUMMARY_LIMIT]

                if link and link not in seen_set:
                    new_articles.append(
                        f"[{source}] {title}\nMô tả: {summary}\nLink: {link}"
                    )
                    seen_set.add(link)
                    seen_list.append(link)
                    count += 1
        except Exception as e:
            print(f"Lỗi nguồn {source}: {e}")

    save_seen_links(seen_list)
    return new_articles
