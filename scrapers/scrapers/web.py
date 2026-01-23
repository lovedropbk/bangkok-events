"""
Generic web scraper for event websites.
Scrapes Eventbrite, Meetup, and venue websites.

Usage:
    python -m scrapers.web --site eventbrite
    python -m scrapers.web --url https://example.com/events
"""

import re
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    """Represents a scraped event"""
    title: str
    description: str
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    venue_name: Optional[str]
    address: Optional[str]
    district: Optional[str]
    category: Optional[str]
    tags: list[str]
    source: str = "web"
    source_url: str = ""
    source_id: str = ""
    image_url: Optional[str] = None
    price_info: Optional[str] = None
    organizer_name: Optional[str] = None


class WebScraper:
    """Generic web scraper for event websites"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, timeout: float = 30.0):
        self.client = httpx.Client(headers=self.HEADERS, timeout=timeout, follow_redirects=True)

    def close(self):
        self.client.close()

    def scrape_eventbrite_bangkok(self, max_pages: int = 3) -> list[ScrapedEvent]:
        """Scrape Eventbrite Bangkok events"""
        events = []
        base_url = "https://www.eventbrite.com/d/thailand--bangkok/events/"

        for page in range(1, max_pages + 1):
            try:
                url = f"{base_url}?page={page}"
                logger.info(f"Scraping Eventbrite page {page}")

                response = self.client.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")
                event_cards = soup.select('[data-testid="event-card"]') or soup.select('.eds-event-card')

                for card in event_cards:
                    event = self._parse_eventbrite_card(card)
                    if event:
                        events.append(event)

            except Exception as e:
                logger.error(f"Error scraping Eventbrite page {page}: {e}")

        return events

    def _parse_eventbrite_card(self, card) -> Optional[ScrapedEvent]:
        """Parse an Eventbrite event card"""
        try:
            # Title
            title_el = card.select_one('[data-testid="event-card-title"]') or card.select_one('h3')
            title = title_el.text.strip() if title_el else None
            if not title:
                return None

            # Link
            link_el = card.select_one('a[href*="eventbrite.com/e/"]')
            url = link_el.get('href', '') if link_el else ''

            # Date
            date_el = card.select_one('[data-testid="event-card-date"]') or card.select_one('.eds-event-card__date')
            date_text = date_el.text.strip() if date_el else ''
            start_datetime = self._parse_date(date_text)

            # Location
            location_el = card.select_one('[data-testid="event-card-location"]')
            location = location_el.text.strip() if location_el else None

            # Image
            img_el = card.select_one('img')
            image_url = img_el.get('src') or img_el.get('data-src') if img_el else None

            # Price
            price_el = card.select_one('[data-testid="event-card-price"]')
            price = price_el.text.strip() if price_el else None

            # Generate source ID from URL
            source_id = f"eb_{url.split('/e/')[-1].split('?')[0]}" if '/e/' in url else ""

            return ScrapedEvent(
                title=title,
                description="",
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=location,
                address=None,
                district=self._extract_district(f"{title} {location or ''}"),
                category=self._guess_category(title),
                tags=[],
                source="eventbrite",
                source_url=url,
                source_id=source_id,
                image_url=image_url,
                price_info=price,
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error parsing Eventbrite card: {e}")
            return None

    def scrape_meetup_bangkok(self, max_pages: int = 2) -> list[ScrapedEvent]:
        """Scrape Meetup.com Bangkok events"""
        events = []
        base_url = "https://www.meetup.com/find/?location=th--Bangkok&source=EVENTS"

        try:
            logger.info("Scraping Meetup Bangkok")
            response = self.client.get(base_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            event_cards = soup.select('[data-testid="categoryResults-eventCard"]') or soup.select('.eventCard')

            for card in event_cards:
                event = self._parse_meetup_card(card)
                if event:
                    events.append(event)

        except Exception as e:
            logger.error(f"Error scraping Meetup: {e}")

        return events

    def _parse_meetup_card(self, card) -> Optional[ScrapedEvent]:
        """Parse a Meetup event card"""
        try:
            # Title
            title_el = card.select_one('h2') or card.select_one('.eventCardHead--title')
            title = title_el.text.strip() if title_el else None
            if not title:
                return None

            # Link
            link_el = card.select_one('a[href*="meetup.com/"]')
            url = link_el.get('href', '') if link_el else ''
            if url and not url.startswith('http'):
                url = f"https://www.meetup.com{url}"

            # Date/time
            date_el = card.select_one('time')
            date_text = date_el.get('datetime', '') if date_el else ''
            start_datetime = None
            if date_text:
                try:
                    start_datetime = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
                except Exception:
                    pass

            # Location
            location_el = card.select_one('[data-testid="venue-name"]')
            location = location_el.text.strip() if location_el else None

            # Image
            img_el = card.select_one('img')
            image_url = img_el.get('src') if img_el else None

            return ScrapedEvent(
                title=title,
                description="",
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=location,
                address=None,
                district=self._extract_district(f"{title} {location or ''}"),
                category="networking",  # Most Meetup events are networking
                tags=["meetup"],
                source="meetup",
                source_url=url,
                source_id=f"mu_{hash(url) % 10**10}",
                image_url=image_url,
                price_info=None,
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error parsing Meetup card: {e}")
            return None

    def scrape_url(self, url: str) -> list[ScrapedEvent]:
        """Scrape events from a generic URL"""
        events = []

        try:
            response = self.client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Look for JSON-LD structured data (many sites use this)
            scripts = soup.select('script[type="application/ld+json"]')
            for script in scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get("@type") == "Event":
                                event = self._parse_json_ld_event(item, url)
                                if event:
                                    events.append(event)
                    elif data.get("@type") == "Event":
                        event = self._parse_json_ld_event(data, url)
                        if event:
                            events.append(event)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")

        return events

    def _parse_json_ld_event(self, data: dict, source_url: str) -> Optional[ScrapedEvent]:
        """Parse JSON-LD Event schema"""
        try:
            title = data.get("name", "")
            if not title:
                return None

            description = data.get("description", "")

            # Parse dates
            start_date = data.get("startDate")
            end_date = data.get("endDate")
            start_datetime = None
            end_datetime = None

            if start_date:
                try:
                    start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                except Exception:
                    pass

            if end_date:
                try:
                    end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                except Exception:
                    pass

            # Location
            location = data.get("location", {})
            venue_name = None
            address = None

            if isinstance(location, dict):
                venue_name = location.get("name")
                addr = location.get("address", {})
                if isinstance(addr, dict):
                    address = addr.get("streetAddress")
                elif isinstance(addr, str):
                    address = addr

            # Image
            image = data.get("image")
            image_url = None
            if isinstance(image, str):
                image_url = image
            elif isinstance(image, list) and image:
                image_url = image[0] if isinstance(image[0], str) else image[0].get("url")

            # Price
            offers = data.get("offers", {})
            price_info = None
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency", "")
                if price:
                    price_info = f"{price} {currency}".strip()

            return ScrapedEvent(
                title=title[:255],
                description=description[:2000],
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                venue_name=venue_name,
                address=address,
                district=self._extract_district(f"{title} {venue_name or ''} {address or ''}"),
                category=self._guess_category(f"{title} {description}"),
                tags=[],
                source="web",
                source_url=source_url,
                source_id=f"web_{hash(source_url) % 10**10}",
                image_url=image_url,
                price_info=price_info,
                organizer_name=data.get("organizer", {}).get("name") if isinstance(data.get("organizer"), dict) else None,
            )

        except Exception as e:
            logger.error(f"Error parsing JSON-LD event: {e}")
            return None

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date from various text formats"""
        if not date_text:
            return None
        try:
            from dateutil.parser import parse
            return parse(date_text)
        except Exception:
            return None

    def _extract_district(self, text: str) -> Optional[str]:
        """Extract Bangkok district from text"""
        text_lower = text.lower()
        districts = {
            "thonglor": "Thonglor",
            "ekkamai": "Ekkamai",
            "sukhumvit": "Sukhumvit",
            "silom": "Silom",
            "sathorn": "Sathorn",
            "siam": "Siam",
            "bangna": "Bangna",
        }
        for key, value in districts.items():
            if key in text_lower:
                return value
        return None

    def _guess_category(self, text: str) -> Optional[str]:
        """Guess event category from text"""
        text_lower = text.lower()
        categories = {
            "party": ["party", "club", "dj", "nightlife"],
            "music": ["concert", "live music", "band", "jazz"],
            "art": ["art", "exhibition", "gallery"],
            "food": ["food", "dinner", "brunch", "cooking"],
            "workshop": ["workshop", "class", "learn", "training"],
            "networking": ["networking", "meetup", "social"],
        }
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        return None


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape websites for Bangkok events")
    parser.add_argument("--site", choices=["eventbrite", "meetup", "all"], help="Site to scrape")
    parser.add_argument("--url", help="Specific URL to scrape")
    args = parser.parse_args()

    scraper = WebScraper()

    try:
        all_events = []

        if args.url:
            events = scraper.scrape_url(args.url)
            all_events.extend(events)
        elif args.site == "eventbrite" or args.site == "all":
            events = scraper.scrape_eventbrite_bangkok()
            all_events.extend(events)
            logger.info(f"Eventbrite: {len(events)} events")
        elif args.site == "meetup" or args.site == "all":
            events = scraper.scrape_meetup_bangkok()
            all_events.extend(events)
            logger.info(f"Meetup: {len(events)} events")
        else:
            # Default: scrape all
            events = scraper.scrape_eventbrite_bangkok()
            all_events.extend(events)
            events = scraper.scrape_meetup_bangkok()
            all_events.extend(events)

        print(f"\nTotal events found: {len(all_events)}")
        for event in all_events:
            print(f"\n{'='*60}")
            print(f"Title: {event.title}")
            print(f"Date: {event.start_datetime}")
            print(f"Venue: {event.venue_name}")
            print(f"Source: {event.source}")
            print(f"URL: {event.source_url}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
