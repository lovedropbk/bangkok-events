"""
Pipeline for saving scraped events to the database.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://eventapp:eventapp_dev@localhost:5432/eventapp")


def get_db_connection():
    """Get a database connection"""
    return psycopg2.connect(DATABASE_URL)


def save_events_to_db(events: list) -> int:
    """
    Save processed events to the database.

    Args:
        events: List of ProcessedEvent objects

    Returns:
        Number of events saved
    """
    if not events:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    saved = 0

    try:
        for event in events:
            # Check for existing event by source_id
            cursor.execute(
                "SELECT id FROM events WHERE source = %s AND source_id = %s",
                (event.source, event.source_id)
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
                        location = CASE
                            WHEN %s IS NOT NULL AND %s IS NOT NULL
                            THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                            ELSE location
                        END,
                        district = %s,
                        category = %s,
                        tags = %s,
                        image_url = %s,
                        price_info = %s,
                        organizer_name = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    event.title,
                    event.description,
                    event.start_datetime,
                    event.end_datetime,
                    event.venue_name,
                    event.address,
                    event.longitude, event.latitude,
                    event.longitude, event.latitude,
                    event.district,
                    event.category,
                    event.tags,
                    event.image_url,
                    event.price_info,
                    event.organizer_name,
                    existing[0]
                ))
            else:
                # Insert new event
                location_sql = "NULL"
                location_params = []
                if event.latitude and event.longitude:
                    location_sql = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
                    location_params = [event.longitude, event.latitude]

                cursor.execute(f"""
                    INSERT INTO events (
                        title, description, start_datetime, end_datetime,
                        venue_name, address, location, district,
                        category, tags, source, source_url, source_id,
                        image_url, price_info, organizer_name,
                        status, is_featured, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, {location_sql}, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        'approved', FALSE, NOW(), NOW()
                    )
                """, (
                    event.title,
                    event.description,
                    event.start_datetime,
                    event.end_datetime,
                    event.venue_name,
                    event.address,
                    *location_params,
                    event.district,
                    event.category,
                    event.tags,
                    event.source,
                    event.source_url,
                    event.source_id,
                    event.image_url,
                    event.price_info,
                    event.organizer_name,
                ))
                saved += 1

        conn.commit()
        logger.info(f"Saved {saved} new events to database")
        return saved

    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving events to database: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def cleanup_past_events(days_ago: int = 7) -> int:
    """
    Delete events that ended more than X days ago.

    Args:
        days_ago: Number of days after which to delete past events

    Returns:
        Number of deleted events
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cutoff = datetime.now() - timedelta(days=days_ago)
        cursor.execute(
            "DELETE FROM events WHERE start_datetime < %s",
            (cutoff,)
        )
        deleted = cursor.rowcount
        conn.commit()
        logger.info(f"Deleted {deleted} past events")
        return deleted

    except Exception as e:
        conn.rollback()
        logger.error(f"Error cleaning up past events: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_event_count() -> int:
    """Get total number of events in database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM events WHERE status = 'approved'")
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        conn.close()
