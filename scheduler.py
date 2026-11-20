import logging
import signal
import threading
from datetime import datetime

from croniter import croniter

from bot import run_once, setup_logging
from src.config import CRON_SCHEDULE, RUN_ON_STARTUP

logger = logging.getLogger("scheduler")
stop_event = threading.Event()


def _handle_shutdown(signum, _frame):
    logger.info("Nhận tín hiệu dừng (%s), đang tắt scheduler...", signum)
    stop_event.set()


def main():
    setup_logging()
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    if not croniter.is_valid(CRON_SCHEDULE):
        raise ValueError(f"Biểu thức CRON_SCHEDULE không hợp lệ: {CRON_SCHEDULE!r}")

    logger.info("News Bot Scheduler đã khởi động. Lịch chạy: '%s'", CRON_SCHEDULE)

    if RUN_ON_STARTUP and not stop_event.is_set():
        logger.info("RUN_ON_STARTUP=true -> chạy ngay 1 phiên đầu tiên...")
        try:
            run_once()
        except Exception:
            logger.error("Phiên chạy khi khởi động thất bại, tiếp tục chờ lịch tiếp theo.")

    while not stop_event.is_set():
        now = datetime.now().astimezone()
        next_run = croniter(CRON_SCHEDULE, now).get_next(datetime)
        wait_seconds = max(0.0, (next_run - now).total_seconds())
        logger.info(
            "Lần chạy tiếp theo: %s (còn %.0f giây).",
            next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
            wait_seconds,
        )

        if stop_event.wait(timeout=wait_seconds):
            break

        try:
            run_once()
        except Exception:
            logger.error("Phiên chạy định kỳ thất bại, tiếp tục chờ lịch tiếp theo.")

    logger.info("Scheduler đã dừng gọn gàng.")


if __name__ == "__main__":
    main()
