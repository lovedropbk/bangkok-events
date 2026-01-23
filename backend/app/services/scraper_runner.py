"""
Scraper runner - executes scrapers and saves results to database.
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from dataclasses import asdict
from sqlalchemy import text
from app.database import SessionLocal
from app.models.event import Event

logger = logging.getLogger(__name__)


def run_scrapers() -> int:
    """
    Run all scrapers and save events to database.

    Returns:
        Number of events saved
    """
    total_saved = 0

    # Add scrapers directory to path
    scrapers_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scrapers"))
    if scrapers_path not in sys.path:
        sys.path.insert(0, scrapers_path)

    # Try the combined scraper (Eventbrite + Apify)
    try:
        from scrapers.combined_scraper import run_all_scrapers

        logger.info("Running combined scraper...")
        events = run_all_scrapers()
        saved = save_scraped_events(events)
        total_saved += saved
        logger.info(f"Combined scraper: saved {saved} events")

    except Exception as e:
        logger.error(f"Combined scraper error: {e}")

    # Try the persistent browser scraper (Instagram + Facebook)
    try:
        import asyncio
        from scrapers.persistent_scraper import run_persistent_scraper

        logger.info("Running persistent browser scraper...")
        events = asyncio.run(run_persistent_scraper())
        saved = save_scraped_events(events)
        total_saved += saved
        logger.info(f"Browser scraper: saved {saved} events")

    except Exception as e:
        logger.error(f"Browser scraper error: {e}")

    return total_saved


def save_scraped_events(events: list) -> int:
    """
    Save scraped events to database.

    Args:
        events: List of ScrapedEvent dataclass instances

    Returns:
        Number of events saved
    """
    if not events:
        return 0

    saved = 0
    db = SessionLocal()

    try:
        for event in events:
            # Convert dataclass to dict
            if hasattr(event, '__dict__'):
                event_data = asdict(event) if hasattr(event, '__dataclass_fields__') else event.__dict__
            else:
                event_data = event

            # Skip if missing required fields
            if not event_data.get('title') or not event_data.get('source_id'):
                continue

            # Check for existing event
            existing = db.query(Event).filter(
                Event.source == event_data.get('source'),
                Event.source_id == event_data.get('source_id')
            ).first()

            # Build location WKT if coordinates available
            location_wkt = None
            lat = event_data.get('latitude')
            lng = event_data.get('longitude')
            if lat and lng:
                location_wkt = f"POINT({lng} {lat})"

            if existing:
                # Update existing event
                existing.title = event_data.get('title', existing.title)
                existing.description = event_data.get('description', existing.description)
                existing.start_datetime = event_data.get('start_datetime', existing.start_datetime)
                existing.end_datetime = event_data.get('end_datetime', existing.end_datetime)
                existing.venue_name = event_data.get('venue_name', existing.venue_name)
                existing.address = event_data.get('address', existing.address)
                existing.district = event_data.get('district', existing.district)
                existing.category = event_data.get('category', existing.category)
                existing.tags = event_data.get('tags', existing.tags)
                existing.image_url = event_data.get('image_url', existing.image_url)
                existing.price_info = event_data.get('price_info', existing.price_info)
                existing.organizer_name = event_data.get('organizer_name', existing.organizer_name)
                if location_wkt:
                    existing.location = location_wkt
            else:
                # Create new event
                event_obj = Event(
                    title=event_data.get('title', '')[:255],
                    description=event_data.get('description', '')[:2000] if event_data.get('description') else None,
                    start_datetime=event_data.get('start_datetime'),
                    end_datetime=event_data.get('end_datetime'),
                    venue_name=event_data.get('venue_name'),
                    address=event_data.get('address'),
                    location=location_wkt,
                    district=event_data.get('district'),
                    category=event_data.get('category'),
                    tags=event_data.get('tags', []),
                    source=event_data.get('source'),
                    source_url=event_data.get('source_url'),
                    source_id=event_data.get('source_id'),
                    image_url=event_data.get('image_url'),
                    price_info=event_data.get('price_info'),
                    organizer_name=event_data.get('organizer_name'),
                    status='approved',  # Auto-approve scraped events
                    is_featured=False,
                )
                db.add(event_obj)
                saved += 1

        db.commit()
        logger.info(f"Saved {saved} new events to database")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving events: {e}")
        raise
    finally:
        db.close()

    return saved


# Keep the old function for backwards compatibility
def save_events(raw_events: list, processor) -> int:
    """Save processed events to database"""
    if not raw_events:
        return 0

    saved = 0
    db = SessionLocal()

    try:
        for raw_event in raw_events:
            # Convert dataclass to dict if needed
            event_dict = raw_event.__dict__ if hasattr(raw_event, '__dict__') else raw_event
            processed = processor.process(event_dict)

            if not processed:
                continue

            # Check for existing event
            existing = db.query(Event).filter(
                Event.source == processed.source,
                Event.source_id == processed.source_id
            ).first()

            if existing:
                # Update existing event
                existing.title = processed.title
                existing.description = processed.description
                existing.start_datetime = processed.start_datetime
                existing.end_datetime = processed.end_datetime
                existing.venue_name = processed.venue_name
                existing.address = processed.address
                existing.district = processed.district
                existing.category = processed.category
                existing.tags = processed.tags
                existing.image_url = processed.image_url
                existing.price_info = processed.price_info
                existing.organizer_name = processed.organizer_name

                # Update location if available
                if processed.latitude and processed.longitude:
                    existing.location = f"POINT({processed.longitude} {processed.latitude})"

            else:
                # Create new event
                location_wkt = None
                if processed.latitude and processed.longitude:
                    location_wkt = f"POINT({processed.longitude} {processed.latitude})"

                event = Event(
                    title=processed.title,
                    description=processed.description,
                    start_datetime=processed.start_datetime,
                    end_datetime=processed.end_datetime,
                    venue_name=processed.venue_name,
                    address=processed.address,
                    location=location_wkt,
                    district=processed.district,
                    category=processed.category,
                    tags=processed.tags,
                    source=processed.source,
                    source_url=processed.source_url,
                    source_id=processed.source_id,
                    image_url=processed.image_url,
                    price_info=processed.price_info,
                    organizer_name=processed.organizer_name,
                    status='approved',  # Auto-approve scraped events
                    is_featured=False,
                )
                db.add(event)
                saved += 1

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving events: {e}")
        raise
    finally:
        db.close()

    return saved


def cleanup_old_events(days_ago: int = 7) -> int:
    """Delete events that ended more than X days ago"""
    db = SessionLocal()

    try:
        cutoff = datetime.now() - timedelta(days=days_ago)
        result = db.query(Event).filter(Event.start_datetime < cutoff).delete()
        db.commit()
        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up events: {e}")
        raise
    finally:
        db.close()
