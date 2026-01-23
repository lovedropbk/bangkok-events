"""
Manual Instagram Post Scraper

This script lets you manually add Instagram post URLs that you find interesting.
It will fetch the post details and save them as events.

Usage:
    python manual_ig_scraper.py

Then paste Instagram post URLs like:
    https://www.instagram.com/p/ABC123/
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from playwright.async_api import async_playwright


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


DISTRICT_COORDS = {
    "Thonglor": (13.7307, 100.5844),
    "Ekkamai": (13.7234, 100.5874),
    "Sukhumvit": (13.7400, 100.5600),
    "Silom": (13.7260, 100.5230),
    "Siam": (13.7453, 100.5318),
    "RCA": (13.7567, 100.5623),
    "Ari": (13.7850, 100.5450),
    "Central Bangkok": (13.7563, 100.5018),
}


def detect_district(text: str):
    if not text:
        return None
    text_lower = text.lower()
    for k, v in {
        'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai', 'sukhumvit': 'Sukhumvit',
        'silom': 'Silom', 'siam': 'Siam', 'rca': 'RCA', 'ari': 'Ari',
    }.items():
        if k in text_lower:
            return v
    return "Central Bangkok"


def detect_category(text: str):
    text_lower = text.lower()
    if any(w in text_lower for w in ['party', 'club', 'dj', 'rave']):
        return 'party'
    if any(w in text_lower for w in ['music', 'concert', 'live']):
        return 'music'
    if any(w in text_lower for w in ['art', 'exhibition']):
        return 'art'
    return 'party'


def extract_price(text: str):
    if 'free' in text.lower():
        return 'Free'
    m = re.search(r'(\d+)\s*(THB|baht)', text, re.I)
    return f'{m.group(1)} THB' if m else None


def extract_datetime(text: str):
    text_lower = text.lower()
    now = datetime.now()

    if 'tonight' in text_lower:
        return now.replace(hour=21, minute=0, second=0)
    if 'tomorrow' in text_lower:
        return (now + timedelta(days=1)).replace(hour=21, minute=0, second=0)

    # Look for date patterns
    match = re.search(r'(\d{1,2})[\/\-](\d{1,2})', text_lower)
    if match:
        try:
            day = int(match.group(1))
            month = int(match.group(2))
            year = now.year
            if month < now.month:
                year += 1
            return datetime(year, month, day, 21, 0)
        except:
            pass

    # Default to next Saturday
    days_until_saturday = (5 - now.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    return (now + timedelta(days=days_until_saturday)).replace(hour=21, minute=0, second=0)


async def scrape_post(url: str) -> ScrapedEvent:
    """Scrape a single Instagram post"""

    # Extract shortcode from URL
    match = re.search(r'/p/([A-Za-z0-9_-]+)', url)
    if not match:
        print(f"Invalid URL: {url}")
        return None

    shortcode = match.group(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Fetching {shortcode}...")
        await page.goto(url, timeout=30000)
        await asyncio.sleep(3)

        html = await page.content()

        # Extract caption
        desc_match = re.search(r'property="og:description" content="([^"]+)"', html)
        caption = desc_match.group(1) if desc_match else ""
        caption = caption.replace("&amp;", "&").replace("&#39;", "'")

        # Extract image
        img_match = re.search(r'property="og:image" content="([^"]+)"', html)
        image_url = img_match.group(1) if img_match else None

        # Extract title from caption
        lines = [l.strip() for l in caption.split('\n') if l.strip()]
        title = ""
        for line in lines[:3]:
            clean = re.sub(r'[#@]\w+', '', line).strip()
            if 10 < len(clean) < 150:
                title = clean
                break

        if not title:
            title = caption[:100] + "..." if len(caption) > 100 else caption

        district = detect_district(caption)
        lat, lng = None, None
        if district and district in DISTRICT_COORDS:
            lat, lng = DISTRICT_COORDS[district]

        event = ScrapedEvent(
            title=title,
            description=caption[:2000],
            start_datetime=extract_datetime(caption),
            end_datetime=None,
            venue_name=None,
            address=None,
            latitude=lat,
            longitude=lng,
            district=district,
            category=detect_category(caption),
            tags=re.findall(r'#([A-Za-z0-9_]+)', caption)[:10],
            source="instagram",
            source_url=url,
            source_id=f"ig_{shortcode}",
            image_url=image_url,
            price_info=extract_price(caption),
            organizer_name=None,
        )

        await browser.close()
        return event


async def main():
    print("=" * 60)
    print("MANUAL INSTAGRAM POST SCRAPER")
    print("=" * 60)
    print()
    print("Paste Instagram post URLs, one per line.")
    print("Enter 'done' when finished.")
    print()

    events = []
    events_file = Path("manual_events.json")

    # Load existing events
    if events_file.exists():
        existing = json.loads(events_file.read_text())
        print(f"Loaded {len(existing)} existing events")
    else:
        existing = []

    existing_ids = {e.get('source_id') for e in existing}

    while True:
        try:
            url = input("URL (or 'done'): ").strip()
        except EOFError:
            break

        if url.lower() == 'done' or not url:
            break

        if 'instagram.com/p/' not in url:
            print("Invalid URL - must be instagram.com/p/...")
            continue

        event = await scrape_post(url)

        if event:
            if event.source_id in existing_ids:
                print(f"Already have: {event.title[:50]}")
            else:
                events.append(event)
                print(f"Added: {event.title[:50]}")
                print(f"  Date: {event.start_datetime}")
                print(f"  District: {event.district}")

    if events:
        # Convert to dict for JSON
        new_events = []
        for e in events:
            d = asdict(e)
            if d['start_datetime']:
                d['start_datetime'] = d['start_datetime'].isoformat()
            if d['end_datetime']:
                d['end_datetime'] = d['end_datetime'].isoformat()
            new_events.append(d)

        # Merge with existing
        all_events = existing + new_events
        events_file.write_text(json.dumps(all_events, indent=2, ensure_ascii=False))

        print(f"\nSaved {len(new_events)} new events (total: {len(all_events)})")


if __name__ == "__main__":
    asyncio.run(main())
