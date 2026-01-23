"""
Playwright-based Instagram Scraper with Session Persistence.

This scraper uses Playwright to open a real browser, allowing the user to
log in once. The session is then saved and reused for future scraping.

Usage:
1. First run: Browser opens, user logs in manually
2. Session saved to 'instagram_session.json'
3. Subsequent runs: Uses saved session automatically

This is the most reliable free method for Instagram scraping.
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
}

BANGKOK_ACCOUNTS = [
    "sataniebkk",
    "kolorbkk",
    "saferoombangkok",
    "duenobkk",
    "mustachebkk",
    "beamthonglor",
    "thecommonsbkk",
    "warehouse30bkk",
    "bangkoknightlife",
    "bangkokinvader",
]

SESSION_FILE = "instagram_session.json"


class PlaywrightInstagramScraper:
    """
    Instagram scraper using Playwright with persistent session.
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
            logger.info("Loading saved session...")
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
        """Save the current session for future use"""
        if self.context:
            state = await self.context.storage_state()
            self.session_file.write_text(json.dumps(state))
            logger.info(f"Session saved to {self.session_file}")

    async def check_login(self) -> bool:
        """Check if we're logged into Instagram"""
        await self.page.goto("https://www.instagram.com/", wait_until="networkidle")

        # Check if login button is visible (means not logged in)
        try:
            login_button = await self.page.query_selector('a[href="/accounts/login/"]')
            return login_button is None
        except:
            return False

    async def manual_login(self):
        """Open browser for manual login"""
        logger.info("Opening browser for manual login...")
        logger.info("Please log in to Instagram in the browser window.")
        logger.info("After logging in, the session will be saved automatically.")

        # Close headless browser
        await self.close()

        # Reopen in visible mode
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

        await self.page.goto("https://www.instagram.com/accounts/login/")

        # Wait for user to log in (check every 2 seconds)
        import asyncio
        logger.info("Waiting for login... (will auto-detect when done)")

        for _ in range(150):  # 5 minutes max
            await asyncio.sleep(2)

            # Check if logged in by looking for profile link
            try:
                url = self.page.url
                if "/accounts/login" not in url and "instagram.com" in url:
                    # Check for logout button or profile elements
                    profile_link = await self.page.query_selector('a[href*="/accounts/edit/"]')
                    avatar = await self.page.query_selector('img[alt*="profile picture"]')
                    if profile_link or avatar:
                        logger.info("Login detected! Saving session...")
                        await self.save_session()
                        return True
            except:
                pass

        logger.error("Login timeout - please try again")
        return False

    async def scrape_profile(self, username: str, max_posts: int = 10) -> List[ScrapedEvent]:
        """Scrape a profile for events"""
        events = []
        logger.info(f"Scraping @{username}...")

        try:
            await self.page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="networkidle",
                timeout=30000
            )

            # Check if profile exists
            if "Page Not Found" in await self.page.content():
                logger.error(f"Profile @{username} not found")
                return events

            # Check if we need to log in
            if "/accounts/login" in self.page.url:
                logger.warning("Need to log in")
                return events

            # Get page content
            content = await self.page.content()

            # Extract post links
            post_links = await self.page.query_selector_all('a[href*="/p/"]')
            shortcodes = set()

            for link in post_links[:max_posts * 2]:  # Get extra in case some aren't events
                href = await link.get_attribute("href")
                if href:
                    match = re.search(r'/p/([A-Za-z0-9_-]+)/', href)
                    if match:
                        shortcodes.add(match.group(1))

            logger.info(f"  Found {len(shortcodes)} posts")

            # Scrape each post
            for shortcode in list(shortcodes)[:max_posts]:
                event = await self._scrape_post(shortcode, username)
                if event:
                    events.append(event)
                    logger.info(f"  Event: {event.title[:40]}...")

        except Exception as e:
            logger.error(f"Error scraping @{username}: {e}")

        return events

    async def _scrape_post(self, shortcode: str, account_username: str) -> Optional[ScrapedEvent]:
        """Scrape a single post"""
        try:
            await self.page.goto(
                f"https://www.instagram.com/p/{shortcode}/",
                wait_until="networkidle",
                timeout=20000
            )

            content = await self.page.content()

            # Extract caption
            caption = ""

            # Try meta description
            meta_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', content)
            if meta_match:
                caption = meta_match.group(1)
                # Decode HTML entities
                caption = caption.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                caption = caption.replace("&#39;", "'").replace("&quot;", '"')

            # Also try to get from page
            caption_els = await self.page.query_selector_all('div._a9zs, span._aacl')
            for el in caption_els:
                text = await el.inner_text()
                if len(text) > len(caption):
                    caption = text

            if not caption or not self._looks_like_event(caption):
                return None

            # Extract title
            title = self._extract_title(caption)
            if not title:
                return None

            # Extract datetime
            start_datetime = self._extract_datetime(caption)
            if not start_datetime:
                return None

            # Skip past events
            if start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Extract image
            image_url = None
            img_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', content)
            if img_match:
                image_url = img_match.group(1)

            # Location info
            district = self._detect_district(caption)
            venue = self._extract_venue(caption)

            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title,
                description=caption[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=venue,
                address=None,
                latitude=lat,
                longitude=lng,
                district=district,
                category=self._detect_category(caption),
                tags=self._extract_tags(caption),
                source="instagram",
                source_url=f"https://www.instagram.com/p/{shortcode}/",
                source_id=f"ig_{shortcode}",
                image_url=image_url,
                price_info=self._extract_price(caption),
                organizer_name=account_username,
            )

        except Exception as e:
            logger.debug(f"Error scraping post {shortcode}: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        if not text or len(text) < 30:
            return False
        text_lower = text.lower()
        locations = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit', 'silom', 'siam', 'rca']
        event_words = ['party', 'event', 'tonight', 'tomorrow', 'dj', 'live', 'tickets', 'rave', 'show']
        date_patterns = [r'\d{1,2}[\/\-]\d{1,2}', r'tonight|tomorrow|this saturday|this friday']
        has_location = any(loc in text_lower for loc in locations)
        has_event = any(word in text_lower for word in event_words)
        has_date = any(re.search(p, text_lower) for p in date_patterns)
        return (has_location or has_event) and has_date

    def _extract_title(self, text: str) -> Optional[str]:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines[:5]:
            clean = re.sub(r'[#@]\w+', '', line).strip()
            if 10 < len(clean) < 150:
                return clean
        return None

    def _extract_datetime(self, text: str) -> Optional[datetime]:
        text_lower = text.lower()
        now = datetime.now()

        if 'tonight' in text_lower:
            return now.replace(hour=21, minute=0, second=0, microsecond=0)
        if 'tomorrow' in text_lower:
            return (now + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)

        match = re.search(r'(\d{1,2})[\/\-](\d{1,2})', text_lower)
        if match:
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                year = now.year
                if month < now.month:
                    year += 1
                return datetime(year, month, day, 21, 0, 0)
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

    def _extract_venue(self, text: str) -> Optional[str]:
        m = re.search(r'(?:at|@|venue)[:\s]+([A-Za-z0-9\s\-\']+?)(?:\n|,|\.|#|$)', text, re.I)
        if m:
            v = m.group(1).strip()
            if 5 < len(v) < 60:
                return v
        return None

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj', 'rave']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition']):
            return 'art'
        return 'party'

    def _extract_tags(self, text: str) -> List[str]:
        tags = re.findall(r'#([A-Za-z0-9_]+)', text)
        return [t.lower() for t in tags if 2 < len(t) < 25][:10]

    def _extract_price(self, text: str) -> Optional[str]:
        if 'free' in text.lower():
            return 'Free'
        m = re.search(r'(\d+)\s*(THB|baht)', text, re.I)
        return f'{m.group(1)} THB' if m else None


async def run_playwright_scraper(force_login: bool = False) -> List[ScrapedEvent]:
    """Run the Playwright scraper"""
    scraper = PlaywrightInstagramScraper()
    all_events = []
    seen_ids = set()

    try:
        logger.info("=" * 60)
        logger.info("PLAYWRIGHT INSTAGRAM SCRAPER")
        logger.info("=" * 60)

        await scraper.initialize(headless=True)

        # Check if logged in
        is_logged_in = await scraper.check_login()

        if not is_logged_in or force_login:
            logger.info("Not logged in - initiating manual login...")
            success = await scraper.manual_login()
            if not success:
                return []
            # Reinitialize with saved session
            await scraper.close()
            await scraper.initialize(headless=True)

        logger.info("\nScraping Bangkok event accounts...")

        for account in BANGKOK_ACCOUNTS:
            try:
                events = await scraper.scrape_profile(account, max_posts=5)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)

                # Small delay between accounts
                import asyncio
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Failed @{account}: {e}")

        logger.info("=" * 60)
        logger.info(f"TOTAL: {len(all_events)} events found")

    finally:
        await scraper.close()

    return all_events


def run_sync() -> List[ScrapedEvent]:
    """Synchronous wrapper for the async scraper"""
    import asyncio
    return asyncio.run(run_playwright_scraper())


if __name__ == "__main__":
    import asyncio
    events = asyncio.run(run_playwright_scraper())

    print(f"\n{'='*60}")
    print(f"FOUND {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:15]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    URL: {e.source_url}")
