"""
Unified scraper runner that combines all event sources.
This is the main entry point for scraping real Bangkok events.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_all_scrapers() -> int:
    """
    Run all available scrapers and return total events saved.
    This is the main function to populate the database with real events.
    """
    total_saved = 0

    # Import scrapers
    try:
        from scrapers.instagram_web import InstagramWebScraper
        from scrapers.facebook_web import FacebookWebScraper
        from scrapers.web import WebScraper
        from processors.event_parser import EventProcessor

        processor = EventProcessor()

        # 1. Instagram - Primary source for underground/mid-sized events
        logger.info("=" * 60)
        logger.info("Starting Instagram scraper...")
        try:
            ig_scraper = InstagramWebScraper()
            ig_events = ig_scraper.scrape_all_hashtags()
            ig_scraper.close()

            saved = save_events(ig_events, processor)
            total_saved += saved
            logger.info(f"Instagram: Found {len(ig_events)} events, saved {saved}")
        except Exception as e:
            logger.error(f"Instagram scraper failed: {e}")

        # 2. Facebook - Secondary source
        logger.info("=" * 60)
        logger.info("Starting Facebook scraper...")
        try:
            fb_scraper = FacebookWebScraper()
            fb_events = fb_scraper.scrape_all_queries()
            fb_scraper.close()

            saved = save_events(fb_events, processor)
            total_saved += saved
            logger.info(f"Facebook: Found {len(fb_events)} events, saved {saved}")
        except Exception as e:
            logger.error(f"Facebook scraper failed: {e}")

        # 3. Web sources (Eventbrite, Meetup)
        logger.info("=" * 60)
        logger.info("Starting web scraper...")
        try:
            web_scraper = WebScraper()
            web_events = []

            # Eventbrite
            try:
                eb_events = web_scraper.scrape_eventbrite_bangkok(max_pages=3)
                web_events.extend(eb_events)
            except Exception as e:
                logger.error(f"Eventbrite error: {e}")

            # Meetup
            try:
                mu_events = web_scraper.scrape_meetup_bangkok()
                web_events.extend(mu_events)
            except Exception as e:
                logger.error(f"Meetup error: {e}")

            web_scraper.close()

            saved = save_events(web_events, processor)
            total_saved += saved
            logger.info(f"Web sources: Found {len(web_events)} events, saved {saved}")
        except Exception as e:
            logger.error(f"Web scraper failed: {e}")

    except ImportError as e:
        logger.error(f"Failed to import scrapers: {e}")
        logger.info("Make sure you're running from the scrapers directory")

    logger.info("=" * 60)
    logger.info(f"TOTAL EVENTS SAVED: {total_saved}")
    return total_saved


def save_events(raw_events: list, processor) -> int:
    """Save processed events to database"""
    if not raw_events:
        return 0

    # Get database connection
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://eventapp:eventapp_dev@localhost:5432/eventapp"
    )

    import psycopg2

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    saved = 0

    try:
        for raw_event in raw_events:
            # Convert dataclass to dict if needed
            event_dict = raw_event.__dict__ if hasattr(raw_event, '__dict__') else raw_event
            processed = processor.process(event_dict)

            if not processed:
                continue

            # Skip events without valid datetime
            if not processed.start_datetime:
                continue

            # Skip past events
            if processed.start_datetime < datetime.now():
                continue

            # Check for existing event (deduplication)
            cursor.execute(
                "SELECT id FROM events WHERE source = %s AND source_id = %s",
                (processed.source, processed.source_id)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing event
                cursor.execute("""
                    UPDATE events SET
                        title = %s,
                        description = %s,
                        start_datetime = %s,
                        end_datetime = %s,
                        venue_name = %s,
                        address = %s,
                        district = %s,
                        category = %s,
                        tags = %s,
                        image_url = %s,
                        price_info = %s,
                        organizer_name = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    processed.title,
                    processed.description,
                    processed.start_datetime,
                    processed.end_datetime,
                    processed.venue_name,
                    processed.address,
                    processed.district,
                    processed.category,
                    processed.tags,
                    processed.image_url,
                    processed.price_info,
                    processed.organizer_name,
                    existing[0]
                ))
            else:
                # Insert new event with location
                location_sql = "NULL"
                location_params = []
                if processed.latitude and processed.longitude:
                    location_sql = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
                    location_params = [processed.longitude, processed.latitude]

                cursor.execute(f"""
                    INSERT INTO events (
                        title, description, start_datetime, end_datetime,
                        venue_name, address, location, district,
                        category, tags, source, source_url, source_id,
                        image_url, price_info, organizer_name,
                        status, is_featured
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, {location_sql}, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        'approved', FALSE
                    )
                """, (
                    processed.title,
                    processed.description,
                    processed.start_datetime,
                    processed.end_datetime,
                    processed.venue_name,
                    processed.address,
                    *location_params,
                    processed.district,
                    processed.category,
                    processed.tags,
                    processed.source,
                    processed.source_url,
                    processed.source_id,
                    processed.image_url,
                    processed.price_info,
                    processed.organizer_name,
                ))
                saved += 1

        conn.commit()
        return saved

    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving events: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("BANGKOK EVENT SCRAPER")
    print("Scraping real events from Instagram, Facebook, and web sources")
    print("=" * 60)

    total = run_all_scrapers()

    print(f"\nDone! Saved {total} real events to the database.")
    print("Start the backend to see events: uvicorn app.main:app --reload")
