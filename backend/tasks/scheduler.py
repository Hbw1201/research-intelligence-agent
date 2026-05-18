from apscheduler.schedulers.asyncio import AsyncIOScheduler


def create_scheduler() -> AsyncIOScheduler:
    """Create an APScheduler instance for MVP scheduled jobs."""
    return AsyncIOScheduler(timezone="Asia/Shanghai")


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register scheduled jobs once workflows are implemented."""
    _ = scheduler
