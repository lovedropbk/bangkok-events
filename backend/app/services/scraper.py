"""
Background tasks and scraper integration for the FastAPI backend.
Runs scrapers on a schedule and populates the database.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class ScraperService:
    """Service to run scrapers in the background"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.last_run: dict[str, datetime] = {}
        self.is_running = False

    async def start(self):
        """Start the scraper scheduler"""
        if self.is_running:
            return

        logger.info("Starting scraper service...")

        # Schedule web scraper every 4 hours
        self.scheduler.add_job(
            self.run_web_scraper,
            IntervalTrigger(hours=4),
            id="web_scraper",
            replace_existing=True,
        )

        # Schedule cleanup daily
        self.scheduler.add_job(
            self.run_cleanup,
            IntervalTrigger(days=1),
            id="cleanup",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        # Run initial scrape after a short delay
        asyncio.create_task(self._initial_scrape())

    async def stop(self):
        """Stop the scraper scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        self.is_running = False
        logger.info("Scraper service stopped")

    async def _initial_scrape(self):
        """Run initial scrape after startup"""
        await asyncio.sleep(10)  # Wait for app to fully start
        logger.info("Running initial scrape...")
        await self.run_web_scraper()

    async def run_web_scraper(self):
        """Run the web scraper"""
        logger.info("Starting web scraper job...")
        try:
            # Import here to avoid circular imports
            from app.services.scraper_runner import run_scrapers
            count = await asyncio.to_thread(run_scrapers)
            self.last_run["web"] = datetime.now()
            logger.info(f"Web scraper completed, saved {count} events")
        except Exception as e:
            logger.error(f"Web scraper failed: {e}")

    async def run_cleanup(self):
        """Run cleanup of past events"""
        logger.info("Starting cleanup job...")
        try:
            from app.services.scraper_runner import cleanup_old_events
            deleted = await asyncio.to_thread(cleanup_old_events)
            self.last_run["cleanup"] = datetime.now()
            logger.info(f"Cleanup completed, deleted {deleted} events")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def get_status(self) -> dict:
        """Get scraper status"""
        return {
            "is_running": self.is_running,
            "last_run": {k: v.isoformat() for k, v in self.last_run.items()},
            "jobs": [
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in self.scheduler.get_jobs()
            ] if self.is_running else [],
        }


# Global scraper service instance
scraper_service = ScraperService()


@asynccontextmanager
async def lifespan_scraper(app):
    """Lifespan context manager for scraper service"""
    await scraper_service.start()
    yield
    await scraper_service.stop()
