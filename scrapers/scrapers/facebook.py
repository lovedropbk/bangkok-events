"""
Facebook Events scraper using Playwright.
Scrapes public Facebook event pages.

Note: Facebook aggressively blocks scraping. This scraper uses Playwright
to render JavaScript and requires careful rate limiting.

Usage:
    python -m scrapers.facebook --search "Bangkok events"
"""

import re
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    """Represents an event scraped from Facebook"""
    title: str
    description: str
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    venue_name: Optional[str]
    address: Optional[str]
    district: Optional[str]
    category: Optional[str]
    tags: list[str]
    source: str = "facebook"
    source_url: str = ""
    source_id: str = ""
    image_url: Optional[str] = None
    price_info: Optional[str] = None
    organizer_name: Optional[str] = None


class FacebookScraper:
    """
    Scrapes Facebook Events using Playwright.

    Note: Due to Facebook's anti-scraping measures, this scraper may
    require adjustments and is provided as a starting point.
    """

    # Bangkok-related search queries
    SEARCH_QUERIES = [
        "Bangkok events this week",
        "Bangkok nightlife events",
        "Bangkok party tonight",
        "Thonglor events",
        "Bangkok rooftop party",
    ]

    # Known Bangkok event pages/groups
    EVENT_PAGES = [
        # Add known event page URLs here
    ]

    def __init__(self, headless: bool = True):
        """
        Initialize the Facebook scraper.

        Args:
            headless: Run browser in headless mode
        """
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
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            self.page = await self.context.new_page()
            logger.info("Browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    async def close(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def search_events(self, query: str, max_results: int = 20) -> list[ScrapedEvent]:
        """
        Search for events on Facebook.

        Args:
            query: Search query
            max_results: Maximum events to return

        Returns:
            List of ScrapedEvent objects
        """
        events = []

        try:
            # Navigate to Facebook events search
            search_url = f"https://www.facebook.com/events/search?q={query}"
            await self.page.goto(search_url, wait_until="networkidle")

            # Wait for events to load
            await self.page.wait_for_timeout(3000)

            # Scroll to load more events
            for _ in range(3):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(2000)

            # Extract event cards
            event_cards = await self.page.query_selector_all('[data-testid="event-card"]')

            for card in event_cards[:max_results]:
                try:
                    event = await self._parse_event_card(card)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.error(f"Error parsing event card: {e}")

        except Exception as e:
            logger.error(f"Error searching events: {e}")

        return events

    async def scrape_event_page(self, url: str) -> Optional[ScrapedEvent]:
        """
        Scrape a single Facebook event page.

        Args:
            url: Facebook event URL

        Returns:
            ScrapedEvent or None
        """
        try:
            await self.page.goto(url, wait_until="networkidle")
            await self.page.wait_for_timeout(2000)

            # Extract event details
            title_el = await self.page.query_selector('h1, [data-testid="event-header-title"]')
            title = await title_el.text_content() if title_el else "Untitled Event"

            desc_el = await self.page.query_selector('[data-testid="event-description"]')
            description = await desc_el.text_content() if desc_el else ""

            # Extract datetime (Facebook uses various formats)
            date_el = await self.page.query_selector('[data-testid="event-time"]')
            date_text = await date_el.text_content() if date_el else ""
            start_datetime = self._parse_facebook_date(date_text)

            # Extract location
            location_el = await self.page.query_selector('[data-testid="event-location"]')
            location_text = await location_el.text_content() if location_el else ""

            # Extract image
            image_el = await self.page.query_selector('img[data-testid="event-cover-photo"]')
            image_url = await image_el.get_attribute("src") if image_el else None

            # Extract event ID from URL
            event_id = self._extract_event_id(url)

            return ScrapedEvent(
                title=title.strip(),
                description=description[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=location_text.strip() if location_text else None,
                address=None,
                district=self._extract_district(f"{title} {description} {location_text}"),
                category=self._guess_category(f"{title} {description}"),
                tags=self._extract_tags(f"{title} {description}"),
                source="facebook",
                source_url=url,
                source_id=f"fb_{event_id}",
                image_url=image_url,
                price_info=self._extract_price(description),
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error scraping event page {url}: {e}")
            return None

    async def _parse_event_card(self, card) -> Optional[ScrapedEvent]:
        """Parse a Facebook event card element"""
        try:
            # Extract link
            link_el = await card.query_selector("a[href*='/events/']")
            if not link_el:
                return None

            href = await link_el.get_attribute("href")
            if not href:
                return None

            # Make absolute URL
            if href.startswith("/"):
                href = f"https://www.facebook.com{href}"

            # Get event details from card
            title_el = await card.query_selector("span")
            title = await title_el.text_content() if title_el else "Untitled"

            return ScrapedEvent(
                title=title.strip(),
                description="",
                start_datetime=None,
                end_datetime=None,
                venue_name=None,
                address=None,
                district=None,
                category=None,
                tags=[],
                source="facebook",
                source_url=href,
                source_id=f"fb_{self._extract_event_id(href)}",
                image_url=None,
                price_info=None,
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error parsing event card: {e}")
            return None

    def _parse_facebook_date(self, date_text: str) -> Optional[datetime]:
        """Parse Facebook's date format"""
        if not date_text:
            return None

        try:
            from dateutil.parser import parse
            # Facebook uses formats like "Saturday, February 15, 2025 at 7:00 PM"
            cleaned = re.sub(r'\s+at\s+', ' ', date_text)
            return parse(cleaned)
        except Exception:
            return None

    def _extract_event_id(self, url: str) -> str:
        """Extract event ID from Facebook URL"""
        match = re.search(r'/events/(\d+)', url)
        return match.group(1) if match else ""

    def _extract_district(self, text: str) -> Optional[str]:
        """Extract Bangkok district from text"""
        text_lower = text.lower()
        districts = {
            "thonglor": "Thonglor",
            "ekkamai": "Ekkamai",
            "sukhumvit": "Sukhumvit",
            "silom": "Silom",
            "siam": "Siam",
        }
        for key, value in districts.items():
            if key in text_lower:
                return value
        return None

    def _guess_category(self, text: str) -> Optional[str]:
        """Guess event category from text"""
        text_lower = text.lower()
        categories = {
            "party": ["party", "club", "dj"],
            "music": ["concert", "live music", "band"],
            "art": ["art", "exhibition", "gallery"],
            "food": ["food", "dinner", "brunch"],
        }
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        return None

    def _extract_tags(self, text: str) -> list[str]:
        """Extract hashtags from text"""
        tags = re.findall(r'#(\w+)', text)
        return [tag.lower() for tag in tags[:10]]

    def _extract_price(self, text: str) -> Optional[str]:
        """Extract price from text"""
        patterns = [
            r'(\d+(?:,\d{3})*\s*(?:THB|baht|฿))',
            r'(free\s*(?:entry|admission)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Facebook for Bangkok events")
    parser.add_argument("--search", help="Search query")
    parser.add_argument("--url", help="Single event URL to scrape")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    scraper = FacebookScraper(headless=args.headless)

    try:
        await scraper.init_browser()

        if args.url:
            event = await scraper.scrape_event_page(args.url)
            if event:
                print(f"Title: {event.title}")
                print(f"Date: {event.start_datetime}")
                print(f"URL: {event.source_url}")
        elif args.search:
            events = await scraper.search_events(args.search)
            print(f"Found {len(events)} events")
            for event in events:
                print(f"- {event.title}: {event.source_url}")
        else:
            # Default: search for Bangkok events
            for query in FacebookScraper.SEARCH_QUERIES[:2]:
                events = await scraper.search_events(query)
                print(f"Query '{query}': {len(events)} events")

    finally:
        await scraper.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
