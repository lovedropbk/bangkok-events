"""
Scheduler for running scrapers periodically.
Uses APScheduler to run scraping jobs.

Usage:
    python -m scrapers.scheduler
"""

import os
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_instagram_scraper():
    """Run the Instagram scraper job"""
    logger.info("Starting Instagram scraper job...")
    try:
        from scrapers.scrapers.instagram import InstagramScraper
        from scrapers.processors.event_parser import EventProcessor
        from scrapers.pipeline import save_events_to_db

        scraper = InstagramScraper()
        processor = EventProcessor()
        all_events = []

        # Scrape top hashtags
        for hashtag in InstagramScraper.HASHTAGS[:5]:
            try:
                events = scraper.scrape_hashtag(hashtag, max_posts=30)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Error scraping hashtag {hashtag}: {e}")

        # Process and save events
        processed = []
        for event in all_events:
            processed_event = processor.process(event.__dict__ if hasattr(event, '__dict__') else event)
            if processed_event:
                processed.append(processed_event)

        if processed:
            save_events_to_db(processed)
            logger.info(f"Saved {len(processed)} events from Instagram")
        else:
            logger.info("No new events from Instagram")

    except Exception as e:
        logger.error(f"Instagram scraper job failed: {e}")


def run_web_scraper():
    """Run the web scraper job"""
    logger.info("Starting web scraper job...")
    try:
        from scrapers.scrapers.web import WebScraper
        from scrapers.processors.event_parser import EventProcessor
        from scrapers.pipeline import save_events_to_db

        scraper = WebScraper()
        processor = EventProcessor()
        all_events = []

        try:
            # Scrape Eventbrite
            events = scraper.scrape_eventbrite_bangkok(max_pages=2)
            all_events.extend(events)
        except Exception as e:
            logger.error(f"Error scraping Eventbrite: {e}")

        try:
            # Scrape Meetup
            events = scraper.scrape_meetup_bangkok()
            all_events.extend(events)
        except Exception as e:
            logger.error(f"Error scraping Meetup: {e}")

        scraper.close()

        # Process and save events
        processed = []
        for event in all_events:
            processed_event = processor.process(event.__dict__ if hasattr(event, '__dict__') else event)
            if processed_event:
                processed.append(processed_event)

        if processed:
            save_events_to_db(processed)
            logger.info(f"Saved {len(processed)} events from web sources")
        else:
            logger.info("No new events from web sources")

    except Exception as e:
        logger.error(f"Web scraper job failed: {e}")


def run_cleanup_job():
    """Clean up old/past events"""
    logger.info("Starting cleanup job...")
    try:
        from scrapers.pipeline import cleanup_past_events
        deleted = cleanup_past_events()
        logger.info(f"Cleaned up {deleted} past events")
    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")


def main():
    """Main scheduler entry point"""
    logger.info("Starting scraper scheduler...")

    scheduler = BlockingScheduler()

    # Run Instagram scraper every 6 hours
    scheduler.add_job(
        run_instagram_scraper,
        CronTrigger(hour="*/6"),
        id="instagram_scraper",
        name="Instagram Scraper",
        replace_existing=True,
    )

    # Run web scraper every 12 hours
    scheduler.add_job(
        run_web_scraper,
        CronTrigger(hour="*/12"),
        id="web_scraper",
        name="Web Scraper",
        replace_existing=True,
    )

    # Run cleanup daily at 3 AM
    scheduler.add_job(
        run_cleanup_job,
        CronTrigger(hour=3),
        id="cleanup",
        name="Cleanup Past Events",
        replace_existing=True,
    )

    # Run initial scrape on startup
    logger.info("Running initial scrape...")
    try:
        run_web_scraper()
    except Exception as e:
        logger.error(f"Initial web scrape failed: {e}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
