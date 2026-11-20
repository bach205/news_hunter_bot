import argparse
import logging
import sys

from src.config import RSSHUB_BASE_URL, SOCIAL_COOLDOWN_HOURS
from src.fetcher import fetch_latest_news
from src.storage import save_seen_links
from src.summarizer import summarize_with_ai
from src.telegram import send_alert_message, send_telegram_message

logger = logging.getLogger(__name__)

MODE_TO_CATEGORIES = {
    "news": {"news"},
    "social": {"social"},
    "all": None,
}


def setup_logging():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
        )


def _send_health_alerts(result, mode):
    alerts = []

    if result.rsshub_checked and not result.rsshub_healthy:
        alerts.append(
            f"RSSHub ({RSSHUB_BASE_URL}) không phản hồi. "
            "Kiểm tra: docker compose ps && docker compose logs --tail=50 rsshub"
        )
    else:
        for plat, reason in result.tripped_cooldowns.items():
            extra = (
                " Nếu cookie hết hạn, cập nhật TWITTER_AUTH_TOKEN trong .env rồi chạy: docker compose up -d rsshub"
                if plat == "x"
                else ""
            )
            alerts.append(
                f"Đã tự động tạm nghỉ nguồn {plat.upper()} trong {SOCIAL_COOLDOWN_HOURS:g} giờ "
                f"để tránh bị chặn ({reason[:120]}).{extra}"
            )

        x_total = result.platform_totals.get("x", 0)
        x_fail = result.platform_failures.get("x", 0)
        if (
            x_total > 0
            and x_fail == x_total
            and "x" not in result.tripped_cooldowns
        ):
            sample = next((e.message for e in result.errors if e.platform == "x"), "")
            alerts.append(
                f"Toàn bộ {x_total} nguồn X (Twitter) đều lỗi ({sample[:120]}). "
                "Có thể TWITTER_AUTH_TOKEN đã hết hạn hoặc bị giới hạn — "
                "cập nhật token mới trong .env rồi chạy: docker compose up -d rsshub"
            )

        threads_total = result.platform_totals.get("threads", 0)
        threads_fail = result.platform_failures.get("threads", 0)
        if (
            threads_total > 0
            and threads_fail == threads_total
            and "threads" not in result.tripped_cooldowns
        ):
            sample = next(
                (e.message for e in result.errors if e.platform == "threads"), ""
            )
            alerts.append(
                f"Toàn bộ {threads_total} nguồn Threads đều lỗi ({sample[:120]}). "
                "Kiểm tra container rsshub (và browserless nếu đang bật)."
            )

    total_feeds = sum(result.platform_totals.values())
    total_failures = sum(result.platform_failures.values())
    if total_feeds > 0 and total_failures == total_feeds and not alerts:
        alerts.append(
            f"Toàn bộ {total_feeds} nguồn [{mode}] đều không lấy được dữ liệu."
        )

    if alerts:
        send_alert_message(f"Cảnh báo sức khỏe News Bot ({mode})", alerts)


def run_once(mode="all"):
    if mode not in MODE_TO_CATEGORIES:
        raise ValueError(f"Chế độ không hợp lệ: {mode!r} (chỉ hỗ trợ news, social, all)")

    categories = MODE_TO_CATEGORIES[mode]
    logger.info("Bắt đầu phiên thu thập & tổng hợp [mode=%s]...", mode)
    try:
        result = fetch_latest_news(categories=categories)
        logger.info(
            "Hoàn tất thu thập [mode=%s]: %d tin mới, %d nguồn lỗi.",
            mode,
            len(result.articles),
            len(result.errors),
        )

        if result.articles:
            summary = summarize_with_ai(result.articles, mode=mode)
            sent = send_telegram_message(summary)
            if sent:
                save_seen_links(result.updated_seen_links)
                logger.info(
                    "Đã gửi bản tin Telegram [mode=%s] và lưu %d link vào lịch sử.",
                    mode,
                    len(result.updated_seen_links),
                )
            else:
                logger.error(
                    "Gửi Telegram thất bại [mode=%s] — giữ nguyên seen_links.json để thử lại lần sau.",
                    mode,
                )
        else:
            logger.info("Không có tin mới trong đợt này [mode=%s].", mode)

        _send_health_alerts(result, mode)
    except Exception as exc:
        logger.exception("Phiên chạy News Bot [mode=%s] gặp lỗi nghiêm trọng: %s", mode, exc)
        send_alert_message(f"News Bot [{mode}] gặp lỗi nghiêm trọng", str(exc)[:300])
        raise


def main():
    parser = argparse.ArgumentParser(description="News Digest Bot")
    parser.add_argument(
        "--mode",
        choices=("all", "news", "social"),
        default="all",
        help="Chọn luồng chạy: news (báo chí), social (X & Threads), hoặc all (tất cả).",
    )
    args = parser.parse_args()

    setup_logging()
    run_once(mode=args.mode)


if __name__ == "__main__":
    main()
