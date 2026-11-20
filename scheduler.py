import logging
import random
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from croniter import croniter

from bot import run_once, setup_logging
from src.config import (
    CRON_JITTER_MAX_SECONDS,
    CRON_SCHEDULE,
    RUN_ON_STARTUP,
    SOCIAL_CRON_JITTER_MAX_SECONDS,
    SOCIAL_CRON_SCHEDULE,
)

logger = logging.getLogger("scheduler")
stop_event = threading.Event()


@dataclass
class ScheduledJob:
    mode: str
    schedule: str
    jitter_max: int
    base_next_run: datetime = None
    actual_next_run: datetime = None
    jitter: int = 0

    def compute_next(self, reference_time):
        anchor = reference_time
        if self.base_next_run is not None and self.base_next_run > anchor:
            anchor = self.base_next_run
        self.base_next_run = croniter(self.schedule, anchor).get_next(datetime)
        self.jitter = (
            random.randint(0, self.jitter_max) if self.jitter_max > 0 else 0
        )
        self.actual_next_run = self.base_next_run + timedelta(seconds=self.jitter)


def _handle_shutdown(signum, _frame):
    logger.info("Nhận tín hiệu dừng (%s), đang tắt scheduler...", signum)
    stop_event.set()


def _build_jobs():
    specs = [
        ("news", CRON_SCHEDULE.strip(), max(0, CRON_JITTER_MAX_SECONDS)),
        (
            "social",
            SOCIAL_CRON_SCHEDULE.strip(),
            max(0, SOCIAL_CRON_JITTER_MAX_SECONDS),
        ),
    ]
    jobs = []
    for mode, schedule, jitter_max in specs:
        if not schedule:
            logger.info("Luồng [%s] đang tắt lịch chạy (biến cron rỗng).", mode)
            continue
        if not croniter.is_valid(schedule):
            raise ValueError(
                f"Biểu thức cron của luồng [{mode}] không hợp lệ: {schedule!r}"
            )
        jobs.append(ScheduledJob(mode=mode, schedule=schedule, jitter_max=jitter_max))

    if not jobs:
        raise ValueError("Không có luồng lịch chạy nào được cấu hình.")
    return jobs


def main():
    setup_logging()
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    jobs = _build_jobs()
    now = datetime.now().astimezone()

    logger.info("News Bot Scheduler đã khởi động với %d luồng độc lập:", len(jobs))
    for job in jobs:
        job.compute_next(now)
        logger.info(
            "  • Luồng [%s]: cron='%s' (jitter 0-%ds) -> chạy tiếp lúc %s (+%ds)",
            job.mode,
            job.schedule,
            job.jitter_max,
            job.actual_next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
            job.jitter,
        )

    if RUN_ON_STARTUP and not stop_event.is_set():
        logger.info("RUN_ON_STARTUP=true -> chạy ngay 1 phiên cho từng luồng...")
        for job in jobs:
            if stop_event.is_set():
                break
            try:
                run_once(mode=job.mode)
            except Exception:
                logger.error(
                    "Phiên khởi động [%s] thất bại, tiếp tục chờ lịch kế tiếp.",
                    job.mode,
                )

    while not stop_event.is_set():
        next_job = min(jobs, key=lambda j: j.actual_next_run)
        now = datetime.now().astimezone()
        wait_seconds = max(0.0, (next_job.actual_next_run - now).total_seconds())
        logger.info(
            "Đang chờ luồng [%s] lúc %s (còn %.0f giây).",
            next_job.mode,
            next_job.actual_next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
            wait_seconds,
        )

        if stop_event.wait(timeout=wait_seconds):
            break

        try:
            run_once(mode=next_job.mode)
        except Exception:
            logger.error(
                "Phiên chạy định kỳ [%s] thất bại, tiếp tục chờ lịch kế tiếp.",
                next_job.mode,
            )

        next_job.compute_next(datetime.now().astimezone())
        logger.info(
            "Lịch tiếp theo của [%s]: %s (+%ds jitter).",
            next_job.mode,
            next_job.actual_next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
            next_job.jitter,
        )

    logger.info("Scheduler đã dừng gọn gàng.")


if __name__ == "__main__":
    main()
