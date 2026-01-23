"""
Master Event Scraper - Combines all scraping methods.

This is the main entry point for scraping Bangkok events.
It uses multiple methods in order of reliability:
1. Playwright with saved sessions (Instagram + Facebook)
2. Eventbrite (public API)
3. Manual submissions (from web app)

Prerequisites:
- Run `python setup_sessions.py` once to save IG/FB login sessions
- Or set APIFY_TOKEN for Apify-based scraping

Usage:
    python -m scrapers.master_scraper
"""

import asyncio
import json
import os
import logging
from datetime import datetime
from typing import List
from pathlib import Path
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    title: str
    description: str
    start_datetime: datetime
    end_datetime: datetime
    venue_name: str
    address: str
    latitude: float
    longitude: float
    district: str
    category: str
    tags: list
    source: str
    source_url: str
    source_id: str
    image_url: str
    price_info: str
    organizer_name: str


INSTAGRAM_SESSION = Path(__file__).parent / "instagram_session.json"
FACEBOOK_SESSION = Path(__file__).parent / "facebook_session.json"


async def scrape_instagram_playwright() -> List[ScrapedEvent]:
    """Scrape Instagram using Playwright with saved session"""
    if not INSTAGRAM_SESSION.exists():
        logger.warning("No Instagram session found. Run setup_sessions.py first.")
        return []

    from scrapers.playwright_instagram import PlaywrightInstagramScraper, BANGKOK_ACCOUNTS

    scraper = PlaywrightInstagramScraper(session_dir=str(INSTAGRAM_SESSION.parent))
    events = []
    seen_ids = set()

    try:
        await scraper.initialize(headless=True)

        # Check if session is still valid
        is_logged_in = await scraper.check_login()
        if not is_logged_in:
            logger.warning("Instagram session expired. Run setup_sessions.py to refresh.")
            return []

        logger.info("Scraping Instagram accounts...")

        for account in BANGKOK_ACCOUNTS[:5]:
            try:
                account_events = await scraper.scrape_profile(account, max_posts=5)
                for e in account_events:
                    if e.source_id not in seen_ids:
                        seen_ids.add(e.source_id)
                        events.append(e)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error scraping @{account}: {e}")

    except Exception as e:
        logger.error(f"Instagram scraping error: {e}")
    finally:
        await scraper.close()

    return events


async def scrape_facebook_playwright() -> List[ScrapedEvent]:
    """Scrape Facebook using Playwright with saved session"""
    if not FACEBOOK_SESSION.exists():
        logger.warning("No Facebook session found. Run setup_sessions.py first.")
        return []

    from scrapers.playwright_facebook import PlaywrightFacebookScraper, BANGKOK_SEARCHES

    scraper = PlaywrightFacebookScraper(session_dir=str(FACEBOOK_SESSION.parent))
    events = []
    seen_ids = set()

    try:
        await scraper.initialize(headless=True)

        is_logged_in = await scraper.check_login()
        if not is_logged_in:
            logger.warning("Facebook session expired. Run setup_sessions.py to refresh.")
            return []

        logger.info("Searching Facebook events...")

        for query in BANGKOK_SEARCHES[:3]:
            try:
                query_events = await scraper.search_events(query, max_events=5)
                for e in query_events:
                    if e.source_id not in seen_ids:
                        seen_ids.add(e.source_id)
                        events.append(e)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error searching '{query}': {e}")

    except Exception as e:
        logger.error(f"Facebook scraping error: {e}")
    finally:
        await scraper.close()

    return events


def scrape_eventbrite() -> List[ScrapedEvent]:
    """Scrape Eventbrite (no auth required)"""
    from scrapers.combined_scraper import EventbriteScraper

    scraper = EventbriteScraper()
    events = []

    try:
        logger.info("Scraping Eventbrite...")
        events = scraper.scrape_bangkok_events()
    except Exception as e:
        logger.error(f"Eventbrite error: {e}")
    finally:
        scraper.close()

    return events


def scrape_apify() -> List[ScrapedEvent]:
    """Scrape using Apify (if token available)"""
    apify_token = os.getenv("APIFY_TOKEN")
    if not apify_token:
        return []

    from scrapers.combined_scraper import ApifyIntegration

    apify = ApifyIntegration(apify_token)
    events = []
    seen_ids = set()

    try:
        logger.info("Scraping via Apify...")

        for hashtag in ["bangkokparty", "bangkokunderground", "thonglornightlife"]:
            try:
                hashtag_events = apify.scrape_instagram_hashtag(hashtag, max_posts=10)
                for e in hashtag_events:
                    if e.source_id not in seen_ids:
                        seen_ids.add(e.source_id)
                        events.append(e)
            except Exception as e:
                logger.error(f"Apify error for #{hashtag}: {e}")

    finally:
        apify.close()

    return events


async def run_all_scrapers() -> List[ScrapedEvent]:
    """Run all available scrapers"""
    all_events = []
    seen_ids = set()

    logger.info("=" * 70)
    logger.info("BANGKOK EVENT MASTER SCRAPER")
    logger.info("=" * 70)

    # 1. Instagram (Playwright)
    logger.info("\n" + "-" * 50)
    logger.info("INSTAGRAM (Playwright)")
    logger.info("-" * 50)
    try:
        ig_events = await scrape_instagram_playwright()
        for e in ig_events:
            if e.source_id not in seen_ids:
                seen_ids.add(e.source_id)
                all_events.append(e)
        logger.info(f"Instagram: {len(ig_events)} events")
    except Exception as e:
        logger.error(f"Instagram failed: {e}")

    # 2. Facebook (Playwright)
    logger.info("\n" + "-" * 50)
    logger.info("FACEBOOK (Playwright)")
    logger.info("-" * 50)
    try:
        fb_events = await scrape_facebook_playwright()
        for e in fb_events:
            if e.source_id not in seen_ids:
                seen_ids.add(e.source_id)
                all_events.append(e)
        logger.info(f"Facebook: {len(fb_events)} events")
    except Exception as e:
        logger.error(f"Facebook failed: {e}")

    # 3. Eventbrite
    logger.info("\n" + "-" * 50)
    logger.info("EVENTBRITE")
    logger.info("-" * 50)
    try:
        eb_events = scrape_eventbrite()
        for e in eb_events:
            if e.source_id not in seen_ids:
                seen_ids.add(e.source_id)
                all_events.append(e)
        logger.info(f"Eventbrite: {len(eb_events)} events")
    except Exception as e:
        logger.error(f"Eventbrite failed: {e}")

    # 4. Apify (if available)
    if os.getenv("APIFY_TOKEN"):
        logger.info("\n" + "-" * 50)
        logger.info("APIFY")
        logger.info("-" * 50)
        try:
            apify_events = scrape_apify()
            for e in apify_events:
                if e.source_id not in seen_ids:
                    seen_ids.add(e.source_id)
                    all_events.append(e)
            logger.info(f"Apify: {len(apify_events)} events")
        except Exception as e:
            logger.error(f"Apify failed: {e}")

    logger.info("\n" + "=" * 70)
    logger.info(f"TOTAL: {len(all_events)} unique events")
    logger.info("=" * 70)

    return all_events


def save_events_to_json(events: List[ScrapedEvent], filename: str = "scraped_events.json"):
    """Save events to JSON file"""
    data = []
    for e in events:
        event_dict = asdict(e)
        # Convert datetime to string
        if event_dict.get('start_datetime'):
            event_dict['start_datetime'] = event_dict['start_datetime'].isoformat()
        if event_dict.get('end_datetime'):
            event_dict['end_datetime'] = event_dict['end_datetime'].isoformat()
        data.append(event_dict)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(events)} events to {filename}")


if __name__ == "__main__":
    events = asyncio.run(run_all_scrapers())

    # Save to JSON
    save_events_to_json(events)

    # Print summary
    print(f"\n{'='*70}")
    print(f"SCRAPED {len(events)} EVENTS")
    print('='*70)

    # Group by source
    by_source = {}
    for e in events:
        by_source.setdefault(e.source, []).append(e)

    for source, source_events in by_source.items():
        print(f"\n{source.upper()}: {len(source_events)} events")
        for i, e in enumerate(source_events[:3]):
            print(f"  [{i+1}] {e.title[:50]}...")
            print(f"      Date: {e.start_datetime}")
            print(f"      District: {e.district} | Category: {e.category}")
