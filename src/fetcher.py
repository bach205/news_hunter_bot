import html
import logging
import random
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser

import feedparser
import requests

from src.config import (
    ARTICLE_SUMMARY_LIMIT,
    FETCH_RETRIES,
    FETCH_TIMEOUT,
    RSSHUB_BASE_URL,
    SOCIAL_COOLDOWN_HOURS,
    SOCIAL_REQUEST_DELAY_MAX,
    SOCIAL_REQUEST_DELAY_MIN,
    load_feeds,
)
from src.storage import load_cooldowns, load_seen_links, save_cooldowns

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; NewsDigestBot/2.0; +https://github.com/news-digest-bot)"
)
SOCIAL_PLATFORMS = {"x", "threads"}
RATE_LIMIT_STATUS_CODES = {401, 403, 429}
RATE_LIMIT_KEYWORDS = (
    "429",
    "rate limit",
    "too many requests",
    "unauthorized",
    "forbidden",
    "auth_token",
    "invalid twitter configs",
    "account is locked",
    "suspended",
    "login required",
)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip_depth += 1
        elif tag in {"br", "p", "div", "li", "blockquote"}:
            self._chunks.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in {"p", "div", "li", "blockquote"}:
            self._chunks.append(" ")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self):
        raw = html.unescape("".join(self._chunks))
        return re.sub(r"\s+", " ", raw).strip()


def clean_html(raw_html):
    """Loại bỏ thẻ HTML từ RSS/RSSHub (đặc biệt là bài X & Threads) trước khi cắt ngắn."""
    if not raw_html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    parser.close()
    return parser.get_text()


def _truncate(text, limit):
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def is_rate_limit_or_auth_error(status_code=None, message=""):
    if status_code in RATE_LIMIT_STATUS_CODES:
        return True
    lowered = (message or "").lower()
    return any(keyword in lowered for keyword in RATE_LIMIT_KEYWORDS)


@dataclass
class FeedError:
    source: str
    platform: str
    uses_rsshub: bool
    message: str


@dataclass
class FetchResult:
    articles: list = field(default_factory=list)
    updated_seen_links: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    platform_totals: dict = field(default_factory=dict)
    platform_failures: dict = field(default_factory=dict)
    tripped_cooldowns: dict = field(default_factory=dict)
    skipped_cooldown_platforms: set = field(default_factory=set)
    rsshub_checked: bool = False
    rsshub_healthy: bool = True


def check_rsshub_health(session, base_url=RSSHUB_BASE_URL):
    try:
        res = session.get(f"{base_url}/healthz", timeout=10)
        return res.ok
    except requests.RequestException as e:
        logger.error("Không kết nối được RSSHub (%s): %s", base_url, e)
        return False


def _fetch_feed_bytes(
    session, url, retries=FETCH_RETRIES, timeout=FETCH_TIMEOUT, allow_retry=True
):
    max_attempts = retries if allow_retry else 1
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code in RATE_LIMIT_STATUS_CODES:
                resp.raise_for_status()
            if resp.status_code in {502, 504} and attempt < max_attempts:
                time.sleep(2 * attempt)
                continue
            resp.raise_for_status()
            return resp.content
        except requests.HTTPError as exc:
            # Tuyệt đối không retry khi bị 4xx/503 từ X/Threads để tránh kích hoạt chặn
            raise exc
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_attempts:
                time.sleep(2 * attempt)
    raise last_exc


def fetch_latest_news(categories=None):
    seen_list = load_seen_links()
    seen_set = set(seen_list)
    feeds = load_feeds(categories=categories)
    cooldowns = load_cooldowns()
    now_ts = time.time()

    # Dọn các cooldown đã hết hạn
    active_cooldowns = {
        plat: float(until)
        for plat, until in cooldowns.items()
        if isinstance(until, (int, float)) and float(until) > now_ts
    }
    cooldowns_changed = len(active_cooldowns) != len(cooldowns)

    result = FetchResult(updated_seen_links=seen_list)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    needs_rsshub = any(f["uses_rsshub"] for f in feeds)
    if needs_rsshub:
        result.rsshub_checked = True
        result.rsshub_healthy = check_rsshub_health(session)
        if not result.rsshub_healthy:
            logger.warning(
                "RSSHub (%s) không phản hồi /healthz — bỏ qua các nguồn phụ thuộc RSSHub.",
                RSSHUB_BASE_URL,
            )

    social_requests_made = 0

    for feed_cfg in feeds:
        source = feed_cfg["name"]
        url = feed_cfg["url"]
        platform = feed_cfg["platform"]
        category = feed_cfg["category"]
        limit = feed_cfg["limit"]
        skip_retweets = feed_cfg["skip_retweets"]
        uses_rsshub = feed_cfg["uses_rsshub"]
        is_social = platform in SOCIAL_PLATFORMS or uses_rsshub

        result.platform_totals[platform] = result.platform_totals.get(platform, 0) + 1

        if uses_rsshub and not result.rsshub_healthy:
            result.platform_failures[platform] = (
                result.platform_failures.get(platform, 0) + 1
            )
            result.errors.append(
                FeedError(
                    source=source,
                    platform=platform,
                    uses_rsshub=True,
                    message="RSSHub không phản hồi /healthz",
                )
            )
            continue

        # Circuit breaker: nếu platform đang trong thời gian tạm nghỉ (cooldown), bỏ qua hoàn toàn
        if platform in SOCIAL_PLATFORMS and platform in active_cooldowns:
            remain_hours = (active_cooldowns[platform] - time.time()) / 3600
            if platform not in result.skipped_cooldown_platforms:
                logger.warning(
                    "Platform [%s] đang tạm nghỉ chống chặn (còn %.1f giờ) — bỏ qua.",
                    platform.upper(),
                    max(0.0, remain_hours),
                )
                result.skipped_cooldown_platforms.add(platform)
            continue

        # Giãn cách ngẫu nhiên giữa các request mạng xã hội (X/Threads) để tránh bắn dồn dập
        if is_social and social_requests_made > 0 and SOCIAL_REQUEST_DELAY_MAX > 0:
            low = max(0.0, min(SOCIAL_REQUEST_DELAY_MIN, SOCIAL_REQUEST_DELAY_MAX))
            high = max(low, SOCIAL_REQUEST_DELAY_MAX)
            delay = random.uniform(low, high)
            logger.info(
                "Nghỉ %.1f giây trước khi gọi nguồn [%s] để tránh rate-limit...",
                delay,
                source,
            )
            time.sleep(delay)

        try:
            if is_social:
                social_requests_made += 1
            # Không retry cho nguồn mạng xã hội để tránh gửi lặp khi X/Threads đang siết
            raw_content = _fetch_feed_bytes(
                session, url, allow_retry=not is_social
            )
            feed = feedparser.parse(raw_content)

            if feed.bozo and not feed.entries:
                raise RuntimeError(f"RSS không hợp lệ: {feed.bozo_exception}")

            count = 0
            for entry in feed.entries:
                if count >= limit:
                    break

                link = (entry.get("link") or "").strip()
                title = clean_html(entry.get("title") or "")
                raw_summary = entry.get("summary") or entry.get("description") or ""
                summary = _truncate(clean_html(raw_summary), ARTICLE_SUMMARY_LIMIT)

                if skip_retweets and (
                    title.startswith("RT @")
                    or title.startswith("Re ")
                    or summary.startswith("RT @")
                ):
                    continue

                if link and link not in seen_set:
                    tag = f"{category.upper()} | {platform.upper()} | {source}"
                    entry_lines = [f"[{tag}] {title}"]
                    if summary and summary != title:
                        entry_lines.append(f"Nội dung: {summary}")
                    entry_lines.append(f"Link: {link}")
                    result.articles.append("\n".join(entry_lines))

                    seen_set.add(link)
                    result.updated_seen_links.append(link)
                    count += 1

            logger.info("Nguồn [%s]: lấy được %d tin mới.", source, count)
        except Exception as exc:
            status_code = None
            err_msg = str(exc)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                status_code = exc.response.status_code
                snippet = clean_html(exc.response.text)[:160]
                if snippet:
                    err_msg = f"HTTP {status_code}: {snippet}"
            logger.error("Lỗi nguồn [%s]: %s", source, err_msg)
            result.platform_failures[platform] = (
                result.platform_failures.get(platform, 0) + 1
            )
            result.errors.append(
                FeedError(
                    source=source,
                    platform=platform,
                    uses_rsshub=uses_rsshub,
                    message=err_msg,
                )
            )

            # Kích hoạt circuit breaker nếu phát hiện 429/401/403 hoặc thông báo rate-limit/auth
            if platform in SOCIAL_PLATFORMS and is_rate_limit_or_auth_error(
                status_code, err_msg
            ):
                cooldown_until = time.time() + SOCIAL_COOLDOWN_HOURS * 3600
                active_cooldowns[platform] = cooldown_until
                cooldowns_changed = True
                result.tripped_cooldowns[platform] = err_msg
                logger.warning(
                    "Kích hoạt chế độ tạm nghỉ %s giờ cho [%s] để bảo vệ tài khoản: %s",
                    SOCIAL_COOLDOWN_HOURS,
                    platform.upper(),
                    err_msg,
                )

    if cooldowns_changed:
        save_cooldowns(active_cooldowns)

    session.close()
    return result
