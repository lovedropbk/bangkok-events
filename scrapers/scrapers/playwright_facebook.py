"""
Playwright-based Facebook Events Scraper with Session Persistence.

Scrapes Facebook Events in Bangkok using a saved browser session.
"""

import os
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    title: str
    description: str
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    venue_name: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    district: Optional[str]
    category: Optional[str]
    tags: list
    source: str
    source_url: str
    source_id: str
    image_url: Optional[str]
    price_info: Optional[str]
    organizer_name: Optional[str]


DISTRICT_COORDS = {
    "Thonglor": (13.7307, 100.5844),
    "Ekkamai": (13.7234, 100.5874),
    "Sukhumvit": (13.7400, 100.5600),
    "Phrom Phong": (13.7312, 100.5698),
    "Silom": (13.7260, 100.5230),
    "Sathorn": (13.7200, 100.5280),
    "Siam": (13.7453, 100.5318),
    "Bangna": (13.6614, 100.6156),
    "RCA": (13.7567, 100.5623),
    "Ari": (13.7850, 100.5450),
    "Charoenkrung": (13.7235, 100.5136),
    "Central Bangkok": (13.7563, 100.5018),
}

# Search queries for Bangkok events
BANGKOK_SEARCHES = [
    "bangkok party",
    "bangkok nightlife",
    "bangkok techno",
    "bangkok underground",
    "thonglor event",
    "bangkok rooftop",
]

SESSION_FILE = "facebook_session.json"


class PlaywrightFacebookScraper:
    """
    Facebook Events scraper using Playwright with persistent session.
    """

    def __init__(self, session_dir: str = "."):
        self.session_dir = Path(session_dir)
        self.session_file = self.session_dir / SESSION_FILE
        self.browser = None
        self.context = None
        self.page = None

    async def initialize(self, headless: bool = True):
        """Initialize the browser"""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)

        # Load existing session if available
        if self.session_file.exists():
            logger.info("Loading saved Facebook session...")
            storage_state = json.loads(self.session_file.read_text())
            self.context = await self.browser.new_context(storage_state=storage_state)
        else:
            self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

    async def close(self):
        """Close the browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def save_session(self):
        """Save the current session"""
        if self.context:
            state = await self.context.storage_state()
            self.session_file.write_text(json.dumps(state))
            logger.info(f"Session saved to {self.session_file}")

    async def check_login(self) -> bool:
        """Check if we're logged into Facebook"""
        await self.page.goto("https://www.facebook.com/", wait_until="networkidle")

        # Check for login form
        login_form = await self.page.query_selector('input[name="email"]')
        return login_form is None

    async def manual_login(self):
        """Open browser for manual login"""
        logger.info("Opening browser for Facebook login...")
        logger.info("Please log in to Facebook in the browser window.")

        await self.close()

        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

        await self.page.goto("https://www.facebook.com/login")

        import asyncio
        logger.info("Waiting for login...")

        for _ in range(150):  # 5 minutes
            await asyncio.sleep(2)

            try:
                url = self.page.url
                if "/login" not in url and "facebook.com" in url:
                    # Check for profile elements
                    profile = await self.page.query_selector('[aria-label="Your profile"]')
                    if profile or "facebook.com/me" in url or "facebook.com/?ref" in url:
                        logger.info("Login detected! Saving session...")
                        await self.save_session()
                        return True
            except:
                pass

        logger.error("Login timeout")
        return False

    async def search_events(self, query: str, max_events: int = 10) -> List[ScrapedEvent]:
        """Search for events"""
        events = []
        logger.info(f"Searching: {query}")

        try:
            # Navigate to events search
            search_url = f"https://www.facebook.com/search/events/?q={query.replace(' ', '%20')}"
            await self.page.goto(search_url, wait_until="networkidle", timeout=30000)

            # Wait for results
            import asyncio
            await asyncio.sleep(2)

            # Scroll to load more
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            content = await self.page.content()

            # Find event links
            event_links = await self.page.query_selector_all('a[href*="/events/"]')

            event_ids = set()
            for link in event_links:
                href = await link.get_attribute("href")
                if href:
                    match = re.search(r'/events/(\d+)', href)
                    if match:
                        event_ids.add(match.group(1))

            logger.info(f"  Found {len(event_ids)} events")

            for event_id in list(event_ids)[:max_events]:
                event = await self._scrape_event(event_id)
                if event:
                    events.append(event)
                    logger.info(f"  Event: {event.title[:40]}...")

        except Exception as e:
            logger.error(f"Error searching '{query}': {e}")

        return events

    async def _scrape_event(self, event_id: str) -> Optional[ScrapedEvent]:
        """Scrape a single event page"""
        try:
            url = f"https://www.facebook.com/events/{event_id}/"
            await self.page.goto(url, wait_until="networkidle", timeout=20000)

            content = await self.page.content()

            # Extract title from og:title or page content
            title = ""
            title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', content)
            if title_match:
                title = title_match.group(1)
            if not title:
                title_el = await self.page.query_selector('h1, [role="heading"]')
                if title_el:
                    title = await title_el.inner_text()

            if not title:
                return None

            # Check if Bangkok related
            if not self._is_bangkok_event(title, content):
                return None

            # Extract description
            description = ""
            desc_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', content)
            if desc_match:
                description = desc_match.group(1)

            # Extract image
            image_url = None
            img_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', content)
            if img_match:
                image_url = img_match.group(1)

            # Extract datetime
            start_datetime = self._extract_datetime_from_page(content)
            if not start_datetime or start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Extract location
            district = self._detect_district(f"{title} {description}")
            venue = self._extract_venue(content)

            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title[:255],
                description=description[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=venue,
                address=None,
                latitude=lat,
                longitude=lng,
                district=district or "Central Bangkok",
                category=self._detect_category(f"{title} {description}"),
                tags=[],
                source="facebook",
                source_url=url,
                source_id=f"fb_{event_id}",
                image_url=image_url,
                price_info=self._extract_price(content),
                organizer_name=None,
            )

        except Exception as e:
            logger.debug(f"Error scraping event {event_id}: {e}")
            return None

    def _is_bangkok_event(self, title: str, content: str) -> bool:
        """Check if event is in Bangkok"""
        text = f"{title} {content}".lower()
        bangkok_keywords = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit',
                           'silom', 'siam', 'sathorn', 'rca', 'thailand']
        return any(k in text for k in bangkok_keywords)

    def _extract_datetime_from_page(self, content: str) -> Optional[datetime]:
        """Extract datetime from Facebook event page"""
        # Try various patterns

        # Pattern 1: "Saturday, January 25, 2025 at 9 PM"
        pattern1 = r'(\w+day),?\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}(?::\d{2})?)\s*(AM|PM)?'
        match = re.search(pattern1, content, re.I)
        if match:
            try:
                from dateutil.parser import parse
                date_str = f"{match.group(2)} {match.group(3)}, {match.group(4)} {match.group(5)} {match.group(6) or 'PM'}"
                return parse(date_str)
            except:
                pass

        # Pattern 2: ISO format in JSON
        iso_match = re.search(r'"startDate":\s*"([^"]+)"', content)
        if iso_match:
            try:
                return datetime.fromisoformat(iso_match.group(1).replace("Z", "+00:00"))
            except:
                pass

        # Pattern 3: Unix timestamp
        ts_match = re.search(r'"start_timestamp":\s*(\d+)', content)
        if ts_match:
            try:
                return datetime.fromtimestamp(int(ts_match.group(1)))
            except:
                pass

        return None

    def _detect_district(self, text: str) -> Optional[str]:
        if not text:
            return None
        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai', 'sukhumvit': 'Sukhumvit',
            'silom': 'Silom', 'sathorn': 'Sathorn', 'siam': 'Siam',
            'bangna': 'Bangna', 'rca': 'RCA', 'ari': 'Ari',
        }
        for k, v in districts.items():
            if k in text_lower:
                return v
        return None

    def _extract_venue(self, content: str) -> Optional[str]:
        """Extract venue from Facebook event page"""
        # Try location name from meta or JSON
        venue_match = re.search(r'"location_name":\s*"([^"]+)"', content)
        if venue_match:
            return venue_match.group(1)

        venue_match = re.search(r'"venue":\s*{\s*"name":\s*"([^"]+)"', content)
        if venue_match:
            return venue_match.group(1)

        return None

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj', 'rave', 'techno']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live', 'band']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition', 'gallery']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner', 'brunch']):
            return 'food'
        return 'party'

    def _extract_price(self, content: str) -> Optional[str]:
        if 'free' in content.lower():
            return 'Free'
        price_match = re.search(r'(\d+)\s*(THB|baht|฿)', content, re.I)
        if price_match:
            return f'{price_match.group(1)} THB'
        return None


async def run_facebook_scraper(force_login: bool = False) -> List[ScrapedEvent]:
    """Run the Facebook scraper"""
    scraper = PlaywrightFacebookScraper()
    all_events = []
    seen_ids = set()

    try:
        logger.info("=" * 60)
        logger.info("PLAYWRIGHT FACEBOOK SCRAPER")
        logger.info("=" * 60)

        await scraper.initialize(headless=True)

        is_logged_in = await scraper.check_login()

        if not is_logged_in or force_login:
            logger.info("Not logged in - initiating manual login...")
            success = await scraper.manual_login()
            if not success:
                return []
            await scraper.close()
            await scraper.initialize(headless=True)

        logger.info("\nSearching for Bangkok events...")

        for query in BANGKOK_SEARCHES[:3]:  # Start with first 3
            try:
                events = await scraper.search_events(query, max_events=5)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)

                import asyncio
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Failed '{query}': {e}")

        logger.info("=" * 60)
        logger.info(f"TOTAL: {len(all_events)} events found")

    finally:
        await scraper.close()

    return all_events


def run_sync() -> List[ScrapedEvent]:
    """Synchronous wrapper"""
    import asyncio
    return asyncio.run(run_facebook_scraper())


if __name__ == "__main__":
    import asyncio
    events = asyncio.run(run_facebook_scraper())

    print(f"\n{'='*60}")
    print(f"FOUND {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:15]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    URL: {e.source_url}")
