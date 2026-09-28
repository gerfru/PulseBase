"""Taegliche Einplanung und Verarbeitung der Insights-Berichte."""

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db.insight_jobs import (
    claim_daily_jobs,
    complete_daily_job,
    enqueue_daily_jobs,
    fail_daily_job,
    requeue_stale_daily_jobs,
)
from src.insights.store import get_or_generate
from src.insights.window import REPORT_ZONE, current_period_end

logger = structlog.get_logger(__name__)


def daily_trigger() -> CronTrigger:
    return CronTrigger(hour=5, minute=0, timezone=REPORT_ZONE)


async def enqueue_reports() -> int:
    period_end = current_period_end()
    count = await enqueue_daily_jobs(period_end)
    logger.info(
        "insights.daily_enqueued", period_end=period_end.isoformat(), count=count
    )
    return count


async def process_daily_jobs() -> int:
    recovered = await requeue_stale_daily_jobs()
    if recovered:
        logger.warning("insights.jobs_recovered", count=recovered)
    jobs = await claim_daily_jobs(limit=1)
    for job in jobs:
        user_id = job["user_id"]
        period_end = job["period_end"]
        attempts = job["attempts"]
        try:
            await get_or_generate(user_id, period_end)
            await complete_daily_job(user_id, period_end, attempts)
        except Exception as error:
            failure = type(error).__name__
            status = await fail_daily_job(user_id, period_end, attempts, failure)
            logger.warning(
                "insights.job_failed",
                period_end=period_end.isoformat(),
                attempts=attempts,
                status=status,
                reason=failure,
            )
    return len(jobs)


async def run_daily_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            processed = await process_daily_jobs()
        except Exception as error:
            logger.error("insights.worker_failed", reason=type(error).__name__)
            processed = 0
        if not processed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30)
            except TimeoutError:
                pass


def start_daily_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=REPORT_ZONE)
    scheduler.add_job(
        enqueue_reports,
        daily_trigger(),
        id="daily_insights",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.start()
    return scheduler
