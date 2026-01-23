"""
Playwright-based browser scraper for Instagram and Facebook.
This provides the most reliable scraping by automating a real browser.

Setup:
    pip install playwright
    playwright install chromium
"""

import re
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    """Scraped event with all required details"""
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


# Bangkok district coordinates
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
}


class PlaywrightScraper:
    """
    Browser-based scraper using Playwright.
    Can handle JavaScript-heavy sites like Instagram and Facebook.
    """

    INSTAGRAM_HASHTAGS = [
        "bangkokparty",
        "bangkokunderground",
        "thonglornightlife",
        "bangkokrooftop",
        "bkknightlife",
        "bangkokdj",
        "bangkokrave",
    ]

    FACEBOOK_SEARCHES = [
        "bangkok party event",
        "thonglor nightlife event",
        "bangkok underground party",
    ]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    async def init_browser(self):
        """Initialize Playwright browser"""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
            )
            self.page = await self.context.new_page()
            logger.info("Browser initialized")
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"Browser init failed: {e}")
            raise

    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape_instagram_hashtag(self, hashtag: str, max_posts: int = 20) -> List[ScrapedEvent]:
        """
        Scrape Instagram hashtag page with browser.
        Extracts event-like posts from public hashtag pages.
        """
        events = []
        logger.info(f"Scraping Instagram #{hashtag}...")

        try:
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # Check if we're redirected to login
            if "/accounts/login" in self.page.url:
                logger.warning("Instagram requires login - trying without auth...")
                # Try to get what's visible without login
                content = await self.page.content()
                events.extend(self._parse_instagram_html(content, hashtag))
                return events

            # Scroll to load more posts
            for _ in range(3):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(2000)

            # Get page content
            content = await self.page.content()

            # Try to extract posts from the page
            events.extend(self._parse_instagram_html(content, hashtag))

            # Also try clicking on individual posts for more details
            posts = await self.page.query_selector_all('article a[href*="/p/"]')
            for post in posts[:min(len(posts), max_posts)]:
                try:
                    href = await post.get_attribute('href')
                    if href:
                        event = await self._scrape_instagram_post(href, hashtag)
                        if event and event.source_id not in [e.source_id for e in events]:
                            events.append(event)
                except Exception as e:
                    logger.debug(f"Error with post: {e}")

        except Exception as e:
            logger.error(f"Error scraping #{hashtag}: {e}")

        return events[:max_posts]

    async def _scrape_instagram_post(self, post_url: str, hashtag: str) -> Optional[ScrapedEvent]:
        """Scrape a single Instagram post"""
        try:
            if not post_url.startswith('http'):
                post_url = f"https://www.instagram.com{post_url}"

            # Open in new tab
            page = await self.context.new_page()
            await page.goto(post_url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(1000)

            content = await page.content()
            await page.close()

            # Extract post data
            # Find caption
            caption_match = re.search(r'"caption"\s*:\s*\{[^}]*"text"\s*:\s*"([^"]+)"', content)
            if not caption_match:
                caption_match = re.search(r'<meta property="og:description" content="([^"]+)"', content)

            if not caption_match:
                return None

            caption = caption_match.group(1)
            caption = caption.encode().decode('unicode_escape')

            if not self._looks_like_event(caption):
                return None

            # Extract shortcode
            shortcode_match = re.search(r'/p/([A-Za-z0-9_-]+)', post_url)
            shortcode = shortcode_match.group(1) if shortcode_match else ""

            # Extract image
            image_match = re.search(r'"display_url"\s*:\s*"([^"]+)"', content)
            if not image_match:
                image_match = re.search(r'<meta property="og:image" content="([^"]+)"', content)
            image_url = image_match.group(1).replace('\\u0026', '&') if image_match else None

            # Extract owner
            owner_match = re.search(r'"username"\s*:\s*"([^"]+)"', content)
            owner = owner_match.group(1) if owner_match else None

            return self._create_event(
                caption=caption,
                shortcode=shortcode,
                image_url=image_url,
                owner=owner,
                source="instagram",
            )

        except Exception as e:
            logger.debug(f"Error scraping post: {e}")
            return None

    def _parse_instagram_html(self, html: str, hashtag: str) -> List[ScrapedEvent]:
        """Parse Instagram HTML for events"""
        events = []

        # Try to find JSON data
        patterns = [
            r'window\._sharedData\s*=\s*({.*?});</script>',
            r'"edge_hashtag_to_media"\s*:\s*({.+?})\s*,\s*"edge',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    events.extend(self._extract_events_from_json(data))
                    break
                except:
                    continue

        return events

    def _extract_events_from_json(self, data: dict) -> List[ScrapedEvent]:
        """Extract events from Instagram JSON data"""
        events = []

        def find_edges(obj, depth=0):
            if depth > 10:
                return []
            edges = []
            if isinstance(obj, dict):
                if 'edges' in obj:
                    edges.extend(obj['edges'])
                for value in obj.values():
                    edges.extend(find_edges(value, depth + 1))
            elif isinstance(obj, list):
                for item in obj:
                    edges.extend(find_edges(item, depth + 1))
            return edges

        edges = find_edges(data)

        for edge in edges[:50]:
            try:
                node = edge.get('node', edge)
                caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
                caption = caption_edges[0]['node']['text'] if caption_edges else ''

                if self._looks_like_event(caption):
                    event = self._create_event(
                        caption=caption,
                        shortcode=node.get('shortcode', ''),
                        image_url=node.get('display_url'),
                        owner=node.get('owner', {}).get('username'),
                        source="instagram",
                    )
                    if event:
                        events.append(event)
            except:
                continue

        return events

    async def scrape_facebook_events(self, query: str, max_events: int = 20) -> List[ScrapedEvent]:
        """Scrape Facebook event search results"""
        events = []
        logger.info(f"Scraping Facebook for: {query}")

        try:
            # Use Facebook's event search
            search_url = f"https://www.facebook.com/events/search/?q={query.replace(' ', '%20')}"
            await self.page.goto(search_url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # Scroll to load more
            for _ in range(2):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(2000)

            # Find event links
            event_links = await self.page.query_selector_all('a[href*="/events/"]')

            for link in event_links[:max_events]:
                try:
                    href = await link.get_attribute('href')
                    if href and '/events/' in href and re.search(r'/events/\d+', href):
                        event = await self._scrape_facebook_event(href)
                        if event and event.source_id not in [e.source_id for e in events]:
                            events.append(event)
                except Exception as e:
                    logger.debug(f"Error with event link: {e}")

        except Exception as e:
            logger.error(f"Error searching Facebook: {e}")

        return events

    async def _scrape_facebook_event(self, event_url: str) -> Optional[ScrapedEvent]:
        """Scrape a single Facebook event page"""
        try:
            if not event_url.startswith('http'):
                event_url = f"https://www.facebook.com{event_url}"

            page = await self.context.new_page()
            await page.goto(event_url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(1000)

            content = await page.content()
            await page.close()

            # Try to get structured data
            ld_match = re.search(r'<script type="application/ld\+json">({.*?})</script>', content, re.DOTALL)
            if ld_match:
                try:
                    data = json.loads(ld_match.group(1))
                    if data.get('@type') == 'Event':
                        return self._parse_facebook_ld_json(data, event_url)
                except:
                    pass

            # Fallback to meta tags
            title = ""
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', content)
            if title_match:
                title = title_match.group(1)

            desc = ""
            desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', content)
            if desc_match:
                desc = desc_match.group(1)

            image_url = None
            img_match = re.search(r'<meta property="og:image" content="([^"]+)"', content)
            if img_match:
                image_url = img_match.group(1)

            event_id = re.search(r'/events/(\d+)', event_url)
            source_id = f"fb_{event_id.group(1)}" if event_id else f"fb_{hash(event_url) % 10**10}"

            if not title:
                return None

            district = self._detect_district(f"{title} {desc}")
            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title[:255],
                description=desc[:2000],
                start_datetime=self._extract_datetime(content),
                end_datetime=None,
                venue_name=self._extract_venue(content),
                address=None,
                latitude=lat,
                longitude=lng,
                district=district,
                category=self._detect_category(f"{title} {desc}"),
                tags=[],
                source="facebook",
                source_url=event_url,
                source_id=source_id,
                image_url=image_url,
                price_info=self._extract_price(desc),
                organizer_name=None,
            )

        except Exception as e:
            logger.debug(f"Error scraping FB event: {e}")
            return None

    def _parse_facebook_ld_json(self, data: dict, url: str) -> Optional[ScrapedEvent]:
        """Parse Facebook's JSON-LD event data"""
        try:
            title = data.get('name', 'Event')

            start_datetime = None
            if data.get('startDate'):
                try:
                    from dateutil.parser import parse
                    start_datetime = parse(data['startDate'])
                except:
                    pass

            location = data.get('location', {})
            venue_name = location.get('name') if isinstance(location, dict) else None
            address = None
            lat, lng = None, None

            if isinstance(location, dict):
                addr = location.get('address')
                if isinstance(addr, dict):
                    address = addr.get('streetAddress')
                elif isinstance(addr, str):
                    address = addr

                geo = location.get('geo', {})
                lat = geo.get('latitude')
                lng = geo.get('longitude')

            description = data.get('description', '')
            district = self._detect_district(f"{title} {venue_name or ''} {address or ''}")

            if not lat and district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            image_url = data.get('image')
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None

            event_id = re.search(r'/events/(\d+)', url)

            return ScrapedEvent(
                title=title[:255],
                description=description[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=venue_name,
                address=address,
                latitude=float(lat) if lat else None,
                longitude=float(lng) if lng else None,
                district=district,
                category=self._detect_category(f"{title} {description}"),
                tags=[],
                source="facebook",
                source_url=url,
                source_id=f"fb_{event_id.group(1)}" if event_id else f"fb_{hash(url) % 10**10}",
                image_url=image_url,
                price_info=self._extract_price(description),
                organizer_name=data.get('organizer', {}).get('name') if isinstance(data.get('organizer'), dict) else None,
            )
        except Exception as e:
            logger.error(f"Error parsing LD+JSON: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        """Check if text is event-like"""
        if not text or len(text) < 50:
            return False

        text_lower = text.lower()

        # Location context
        locations = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit', 'silom', 'siam', 'rca']
        has_location = any(loc in text_lower for loc in locations)

        # Event keywords
        event_words = ['party', 'event', 'tonight', 'dj', 'live', 'show', 'tickets', 'doors', 'lineup', 'rave', 'rooftop']
        has_event = any(word in text_lower for word in event_words)

        # Date reference
        date_patterns = [r'\d{1,2}[\/\-]\d{1,2}', r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', r'tonight|tomorrow']
        has_date = any(re.search(p, text_lower) for p in date_patterns)

        return has_location and has_event and has_date

    def _create_event(self, caption: str, shortcode: str, image_url: Optional[str], owner: Optional[str], source: str) -> Optional[ScrapedEvent]:
        """Create event from caption"""
        try:
            # Title from first line
            lines = [l.strip() for l in caption.split('\n') if l.strip()]
            title = ""
            for line in lines[:3]:
                clean = re.sub(r'[#@]\w+', '', line).strip()
                if len(clean) > 10:
                    title = clean[:150]
                    break
            if not title:
                title = "Bangkok Event"

            # Datetime
            start_datetime = self._extract_datetime(caption)
            if not start_datetime or start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Location
            venue = self._extract_venue(caption)
            district = self._detect_district(caption)
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
                source=source,
                source_url=f"https://instagram.com/p/{shortcode}/" if shortcode else "",
                source_id=f"ig_{shortcode}" if shortcode else f"ig_{hash(caption[:100]) % 10**10}",
                image_url=image_url,
                price_info=self._extract_price(caption),
                organizer_name=owner,
            )
        except:
            return None

    def _extract_datetime(self, text: str) -> Optional[datetime]:
        """Extract datetime from text"""
        text_lower = text.lower()
        now = datetime.now()

        if 'tonight' in text_lower:
            return now.replace(hour=21, minute=0, second=0, microsecond=0)
        if 'tomorrow' in text_lower:
            return (now + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)

        # Day of week
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if f'this {day}' in text_lower:
                days_ahead = i - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).replace(hour=21, minute=0, second=0, microsecond=0)

        # Date patterns
        match = re.search(r'(\d{1,2})[\/\-](\d{1,2})', text_lower)
        if match:
            try:
                from dateutil.parser import parse
                return parse(match.group(0), dayfirst=True).replace(hour=21, minute=0)
            except:
                pass

        return None

    def _extract_venue(self, text: str) -> Optional[str]:
        patterns = [
            r'(?:at|@|venue)\s*[:\s]+([A-Za-z0-9\s\-\']+?)(?:\n|,|\.|\#|$)',
            r'([A-Za-z0-9\s]+(?:rooftop|bar|club|warehouse|venue))',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                v = m.group(1).strip()
                if 5 < len(v) < 60:
                    return v
        return None

    def _detect_district(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit', 'silom': 'Silom',
            'sathorn': 'Sathorn', 'siam': 'Siam',
            'rca': 'RCA', 'ari': 'Ari', 'bangna': 'Bangna',
        }
        for k, v in districts.items():
            if k in text_lower:
                return v
        return None

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj', 'rave']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live', 'band']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner', 'popup']):
            return 'food'
        return 'party'

    def _extract_tags(self, text: str) -> list:
        tags = re.findall(r'#([A-Za-z0-9_]+)', text)
        return [t.lower() for t in tags if 2 < len(t) < 25][:10]

    def _extract_price(self, text: str) -> Optional[str]:
        if 'free' in text.lower():
            return 'Free'
        m = re.search(r'(\d+)\s*(THB|baht)', text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} THB"
        return None

    async def scrape_all(self) -> List[ScrapedEvent]:
        """Run all scrapers"""
        all_events = []

        # Instagram
        for hashtag in self.INSTAGRAM_HASHTAGS[:5]:
            try:
                events = await self.scrape_instagram_hashtag(hashtag, max_posts=10)
                all_events.extend(events)
                logger.info(f"IG #{hashtag}: {len(events)} events")
            except Exception as e:
                logger.error(f"IG #{hashtag} failed: {e}")

        # Facebook
        for query in self.FACEBOOK_SEARCHES[:3]:
            try:
                events = await self.scrape_facebook_events(query, max_events=10)
                all_events.extend(events)
                logger.info(f"FB '{query}': {len(events)} events")
            except Exception as e:
                logger.error(f"FB '{query}' failed: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for e in all_events:
            if e.source_id not in seen:
                seen.add(e.source_id)
                unique.append(e)

        return unique


async def run_playwright_scrapers():
    """Main entry point for Playwright scraping"""
    scraper = PlaywrightScraper(headless=True)

    try:
        await scraper.init_browser()
        events = await scraper.scrape_all()

        print(f"\n{'='*60}")
        print(f"SCRAPED {len(events)} EVENTS")
        print('='*60)

        for i, e in enumerate(events[:10]):
            print(f"\n[{i+1}] {e.title}")
            print(f"    Date: {e.start_datetime}")
            print(f"    District: {e.district} | Category: {e.category}")
            print(f"    Price: {e.price_info} | Image: {'Yes' if e.image_url else 'No'}")
            print(f"    URL: {e.source_url}")

        return events

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(run_playwright_scrapers())
