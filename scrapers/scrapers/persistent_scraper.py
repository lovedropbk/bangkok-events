"""
Auto-login Instagram/Facebook scraper using persistent browser profile.

This uses Chromium's user data directory which persists cookies automatically.
The first time you run it, log in manually. After that, it remembers the login.

This is the RECOMMENDED approach - no manual session saving needed!
"""

import asyncio
import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass, asdict
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

BANGKOK_IG_ACCOUNTS = [
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

BANGKOK_FB_SEARCHES = [
    "bangkok party",
    "bangkok nightlife",
    "bangkok underground event",
    "thonglor party",
]


class PersistentBrowserScraper:
    """
    Scraper using a persistent Chromium profile.
    Login once, and it remembers forever.
    """

    def __init__(self, user_data_dir: str = None):
        self.user_data_dir = user_data_dir or str(Path(__file__).parent / "browser_profile")
        self.browser = None
        self.context = None
        self.page = None

    async def initialize(self, headless: bool = True):
        """Initialize persistent browser context"""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()

        # Create user data directory
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)

        # Launch with persistent context
        self.context = await self.playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def close(self):
        """Close browser (keeps profile data for next run)"""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def check_instagram_login(self) -> bool:
        """Check if logged into Instagram"""
        await self.page.goto("https://www.instagram.com/", timeout=30000)
        await asyncio.sleep(2)

        # If we see login button, not logged in
        login_btn = await self.page.query_selector('a[href="/accounts/login/"]')
        content = await self.page.content()

        return login_btn is None and "Log in" not in content[:2000]

    async def check_facebook_login(self) -> bool:
        """Check if logged into Facebook"""
        await self.page.goto("https://www.facebook.com/", timeout=30000)
        await asyncio.sleep(2)

        # Check for login form
        email_input = await self.page.query_selector('input[name="email"]')
        return email_input is None

    async def prompt_login(self, platform: str):
        """Open browser for manual login"""
        logger.info(f"Need to log in to {platform}...")
        logger.info("Please log in in the browser window that opened.")

        # Reopen in visible mode
        await self.close()
        await self.initialize(headless=False)

        if platform == "instagram":
            await self.page.goto("https://www.instagram.com/accounts/login/")
        else:
            await self.page.goto("https://www.facebook.com/login")

        logger.info(f"Waiting for {platform} login... (checking every 5 seconds)")

        for _ in range(60):  # 5 minutes
            await asyncio.sleep(5)

            if platform == "instagram":
                cookies = await self.context.cookies()
                if any(c["name"] == "sessionid" for c in cookies):
                    logger.info("Instagram login detected!")
                    return True
            else:
                cookies = await self.context.cookies()
                if any(c["name"] == "c_user" for c in cookies):
                    logger.info("Facebook login detected!")
                    return True

        logger.error("Login timeout")
        return False

    async def scrape_instagram_profile(self, username: str, max_posts: int = 10) -> List[ScrapedEvent]:
        """Scrape an Instagram profile for events"""
        events = []
        logger.info(f"Scraping IG @{username}...")

        try:
            await self.page.goto(f"https://www.instagram.com/{username}/", timeout=30000)
            await asyncio.sleep(3)

            # Check for "Profile not available"
            content = await self.page.content()
            if "Profile isn't available" in content or "Page Not Found" in content:
                logger.warning(f"  Profile @{username} not available")
                return events

            # Scroll to load posts
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1)

            # Find post shortcodes
            content = await self.page.content()
            shortcodes = set(re.findall(r'/p/([A-Za-z0-9_-]+)/', content))

            # Also try links
            links = await self.page.query_selector_all('a[href*="/p/"]')
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    match = re.search(r'/p/([A-Za-z0-9_-]+)', href)
                    if match:
                        shortcodes.add(match.group(1))

            logger.info(f"  Found {len(shortcodes)} posts")

            for sc in list(shortcodes)[:max_posts]:
                event = await self._scrape_ig_post(sc, username)
                if event:
                    events.append(event)
                    logger.info(f"  Event: {event.title[:40]}...")

                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error scraping @{username}: {e}")

        return events

    async def _scrape_ig_post(self, shortcode: str, account: str) -> Optional[ScrapedEvent]:
        """Scrape a single Instagram post"""
        try:
            await self.page.goto(f"https://www.instagram.com/p/{shortcode}/", timeout=20000)
            await asyncio.sleep(2)

            content = await self.page.content()

            # Get caption from og:description
            match = re.search(r'property="og:description" content="([^"]+)"', content)
            if not match:
                return None

            caption = match.group(1)
            caption = caption.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')

            if not self._looks_like_event(caption):
                return None

            title = self._extract_title(caption)
            if not title:
                return None

            start_datetime = self._extract_datetime(caption)
            if not start_datetime or start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Image
            img_match = re.search(r'property="og:image" content="([^"]+)"', content)
            image_url = img_match.group(1) if img_match else None

            district = self._detect_district(caption)
            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title,
                description=caption[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=self._extract_venue(caption),
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
                organizer_name=account,
            )

        except Exception as e:
            logger.debug(f"Error scraping post {shortcode}: {e}")
            return None

    async def scrape_facebook_events(self, query: str, max_events: int = 10) -> List[ScrapedEvent]:
        """Search Facebook for events"""
        events = []
        logger.info(f"Searching FB: {query}")

        try:
            url = f"https://www.facebook.com/search/events/?q={query.replace(' ', '%20')}"
            await self.page.goto(url, timeout=30000)
            await asyncio.sleep(3)

            # Scroll to load
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1)

            # Find event links
            content = await self.page.content()
            event_ids = set(re.findall(r'/events/(\d+)', content))

            logger.info(f"  Found {len(event_ids)} events")

            for event_id in list(event_ids)[:max_events]:
                event = await self._scrape_fb_event(event_id)
                if event:
                    events.append(event)
                    logger.info(f"  Event: {event.title[:40]}...")

                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error searching FB '{query}': {e}")

        return events

    async def _scrape_fb_event(self, event_id: str) -> Optional[ScrapedEvent]:
        """Scrape a single Facebook event"""
        try:
            url = f"https://www.facebook.com/events/{event_id}/"
            await self.page.goto(url, timeout=20000)
            await asyncio.sleep(2)

            content = await self.page.content()

            # Title
            title_match = re.search(r'property="og:title" content="([^"]+)"', content)
            if not title_match:
                return None
            title = title_match.group(1)

            # Check if Bangkok-related
            if not self._is_bangkok_event(title, content):
                return None

            # Description
            desc_match = re.search(r'property="og:description" content="([^"]+)"', content)
            description = desc_match.group(1) if desc_match else ""

            # Image
            img_match = re.search(r'property="og:image" content="([^"]+)"', content)
            image_url = img_match.group(1) if img_match else None

            # DateTime
            start_datetime = self._extract_fb_datetime(content)
            if not start_datetime or start_datetime < datetime.now() - timedelta(hours=6):
                return None

            district = self._detect_district(f"{title} {description}")
            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title[:255],
                description=description[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=self._extract_fb_venue(content),
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
            logger.debug(f"Error scraping FB event {event_id}: {e}")
            return None

    # Helper methods
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

    def _extract_fb_datetime(self, content: str) -> Optional[datetime]:
        # ISO format
        match = re.search(r'"startDate":\s*"([^"]+)"', content)
        if match:
            try:
                return datetime.fromisoformat(match.group(1).replace("Z", "+00:00")).replace(tzinfo=None)
            except:
                pass

        # Timestamp
        match = re.search(r'"start_timestamp":\s*(\d+)', content)
        if match:
            try:
                return datetime.fromtimestamp(int(match.group(1)))
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
            'charoenkrung': 'Charoenkrung',
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

    def _extract_fb_venue(self, content: str) -> Optional[str]:
        match = re.search(r'"location_name":\s*"([^"]+)"', content)
        return match.group(1) if match else None

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

    def _extract_tags(self, text: str) -> List[str]:
        tags = re.findall(r'#([A-Za-z0-9_]+)', text)
        return [t.lower() for t in tags if 2 < len(t) < 25][:10]

    def _extract_price(self, text: str) -> Optional[str]:
        if 'free' in text.lower():
            return 'Free'
        m = re.search(r'(\d+)\s*(THB|baht|฿)', text, re.I)
        return f'{m.group(1)} THB' if m else None

    def _is_bangkok_event(self, title: str, content: str) -> bool:
        text = f"{title} {content}".lower()
        keywords = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit', 'silom', 'siam', 'thailand']
        return any(k in text for k in keywords)


async def run_persistent_scraper(force_visible: bool = False) -> List[ScrapedEvent]:
    """Run the scraper with persistent profile"""
    scraper = PersistentBrowserScraper()
    all_events = []
    seen_ids = set()

    try:
        logger.info("=" * 70)
        logger.info("BANGKOK EVENT SCRAPER (Persistent Browser)")
        logger.info("=" * 70)

        await scraper.initialize(headless=not force_visible)

        # Check Instagram login
        logger.info("\nChecking Instagram login...")
        ig_logged_in = await scraper.check_instagram_login()

        if not ig_logged_in:
            logger.info("Not logged into Instagram. Opening browser for login...")
            ig_logged_in = await scraper.prompt_login("instagram")
            if ig_logged_in:
                # Reinitialize in headless mode
                await scraper.close()
                await scraper.initialize(headless=True)

        if ig_logged_in:
            logger.info("\n" + "-" * 50)
            logger.info("SCRAPING INSTAGRAM")
            logger.info("-" * 50)

            for account in BANGKOK_IG_ACCOUNTS[:5]:
                try:
                    events = await scraper.scrape_instagram_profile(account, max_posts=5)
                    for e in events:
                        if e.source_id not in seen_ids:
                            seen_ids.add(e.source_id)
                            all_events.append(e)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Failed @{account}: {e}")

        # Check Facebook login
        logger.info("\nChecking Facebook login...")
        fb_logged_in = await scraper.check_facebook_login()

        if not fb_logged_in:
            logger.info("Not logged into Facebook. Opening browser for login...")
            fb_logged_in = await scraper.prompt_login("facebook")
            if fb_logged_in:
                await scraper.close()
                await scraper.initialize(headless=True)

        if fb_logged_in:
            logger.info("\n" + "-" * 50)
            logger.info("SCRAPING FACEBOOK")
            logger.info("-" * 50)

            for query in BANGKOK_FB_SEARCHES[:3]:
                try:
                    events = await scraper.scrape_facebook_events(query, max_events=5)
                    for e in events:
                        if e.source_id not in seen_ids:
                            seen_ids.add(e.source_id)
                            all_events.append(e)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Failed '{query}': {e}")

        logger.info("\n" + "=" * 70)
        logger.info(f"TOTAL: {len(all_events)} unique events")
        logger.info("=" * 70)

    finally:
        await scraper.close()

    return all_events


def save_events(events: List[ScrapedEvent], filename: str = "scraped_events.json"):
    """Save events to JSON"""
    data = []
    for e in events:
        d = asdict(e)
        if d.get('start_datetime'):
            d['start_datetime'] = d['start_datetime'].isoformat()
        if d.get('end_datetime'):
            d['end_datetime'] = d['end_datetime'].isoformat()
        data.append(d)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(events)} events to {filename}")


if __name__ == "__main__":
    events = asyncio.run(run_persistent_scraper())
    save_events(events)

    print(f"\n{'='*60}")
    print(f"SCRAPED {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:10]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    Source: {e.source}")
