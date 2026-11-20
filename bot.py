import logging
import sys

from src.config import RSSHUB_BASE_URL
from src.fetcher import fetch_latest_news
from src.storage import save_seen_links
from src.summarizer import summarize_with_ai
from src.telegram import send_alert_message, send_telegram_message

logger = logging.getLogger(__name__)


def setup_logging():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
        )


def _send_health_alerts(result):
    alerts = []

    if result.rsshub_checked and not result.rsshub_healthy:
        alerts.append(
            f"RSSHub ({RSSHUB_BASE_URL}) không phản hồi. "
            "Kiểm tra: docker compose ps && docker compose logs --tail=50 rsshub"
        )
    else:
        x_total = result.platform_totals.get("x", 0)
        x_fail = result.platform_failures.get("x", 0)
        if x_total > 0 and x_fail == x_total:
            sample = next((e.message for e in result.errors if e.platform == "x"), "")
            alerts.append(
                f"Toàn bộ {x_total} nguồn X (Twitter) đều lỗi ({sample[:120]}). "
                "Có thể TWITTER_AUTH_TOKEN đã hết hạn hoặc bị giới hạn — "
                "cập nhật token mới trong .env rồi chạy: docker compose up -d rsshub"
            )

        threads_total = result.platform_totals.get("threads", 0)
        threads_fail = result.platform_failures.get("threads", 0)
        if threads_total > 0 and threads_fail == threads_total:
            sample = next(
                (e.message for e in result.errors if e.platform == "threads"), ""
            )
            alerts.append(
                f"Toàn bộ {threads_total} nguồn Threads đều lỗi ({sample[:120]}). "
                "Kiểm tra container browserless & rsshub."
            )

    total_feeds = sum(result.platform_totals.values())
    total_failures = sum(result.platform_failures.values())
    if total_feeds > 0 and total_failures == total_feeds and not alerts:
        alerts.append(f"Toàn bộ {total_feeds} nguồn RSS đều không lấy được dữ liệu.")

    if alerts:
        send_alert_message("Cảnh báo sức khỏe News Bot", alerts)


def run_once():
    logger.info("Bắt đầu phiên thu thập & tổng hợp tin tức...")
    try:
        result = fetch_latest_news()
        logger.info(
            "Hoàn tất thu thập: %d tin mới, %d nguồn lỗi.",
            len(result.articles),
            len(result.errors),
        )

        if result.articles:
            summary = summarize_with_ai(result.articles)
            sent = send_telegram_message(summary)
            if sent:
                save_seen_links(result.updated_seen_links)
                logger.info(
                    "Đã gửi bản tin Telegram và lưu %d link vào lịch sử.",
                    len(result.updated_seen_links),
                )
            else:
                logger.error(
                    "Gửi Telegram thất bại — giữ nguyên seen_links.json để thử lại lần sau."
                )
        else:
            logger.info("Không có tin mới trong đợt này.")

        _send_health_alerts(result)
    except Exception as exc:
        logger.exception("Phiên chạy News Bot gặp lỗi nghiêm trọng: %s", exc)
        send_alert_message("News Bot gặp lỗi nghiêm trọng", str(exc)[:300])
        raise


def main():
    setup_logging()
    run_once()


if __name__ == "__main__":
    main()
