"""
Facebook Events scraper using public event pages.
Scrapes publicly visible event information without authentication.
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

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
    tags: list
    source: str = "facebook"
    source_url: str = ""
    source_id: str = ""
    image_url: Optional[str] = None
    price_info: Optional[str] = None
    organizer_name: Optional[str] = None


class FacebookWebScraper:
    """
    Facebook Events scraper using public web endpoints.
    Works by scraping public event pages and search results.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # Bangkok event search URLs and pages
    SEARCH_QUERIES = [
        "bangkok party this weekend",
        "bangkok underground event",
        "bangkok rooftop party",
        "thonglor event tonight",
        "bangkok live music",
    ]

    # Known Bangkok event pages/organizers
    EVENT_PAGES = [
        "BangkokNightlife",
        "ThonglörEvents",
        "BangkokPartyScene",
    ]

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)

    def close(self):
        self.client.close()

    def search_events(self, query: str = "bangkok events", max_results: int = 20) -> list[ScrapedEvent]:
        """
        Search for public Facebook events.

        Note: Facebook's public event search is limited.
        This uses mobile.facebook.com which has better public access.
        """
        events = []
        logger.info(f"Searching Facebook for: {query}")

        try:
            # Try mobile Facebook (more permissive)
            search_url = f"https://m.facebook.com/events/search/?q={query.replace(' ', '%20')}"
            response = self.client.get(search_url)

            if response.status_code == 200:
                events.extend(self._parse_search_results(response.text))

        except Exception as e:
            logger.error(f"Error searching Facebook: {e}")

        return events[:max_results]

    def scrape_event_page(self, event_url: str) -> Optional[ScrapedEvent]:
        """Scrape a single public Facebook event page"""
        logger.info(f"Scraping event: {event_url}")

        try:
            # Use mobile version for better access
            if 'facebook.com' in event_url and 'm.facebook.com' not in event_url:
                event_url = event_url.replace('www.facebook.com', 'm.facebook.com')
                event_url = event_url.replace('facebook.com', 'm.facebook.com')

            response = self.client.get(event_url)
            if response.status_code != 200:
                return None

            return self._parse_event_page(response.text, event_url)

        except Exception as e:
            logger.error(f"Error scraping event page: {e}")
            return None

    def _parse_search_results(self, html: str) -> list[ScrapedEvent]:
        """Parse Facebook event search results page"""
        events = []
        soup = BeautifulSoup(html, 'lxml')

        # Look for event links
        event_links = soup.find_all('a', href=re.compile(r'/events/\d+'))

        for link in event_links[:20]:
            try:
                href = link.get('href', '')
                event_id = re.search(r'/events/(\d+)', href)
                if not event_id:
                    continue

                # Get event title from link text or parent
                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    parent = link.find_parent()
                    if parent:
                        title = parent.get_text(strip=True)[:100]

                if not title:
                    continue

                events.append(ScrapedEvent(
                    title=title[:255],
                    description="",
                    start_datetime=None,  # Will be enriched later
                    end_datetime=None,
                    venue_name=None,
                    address=None,
                    district=self._detect_district(title),
                    category=self._detect_category(title),
                    tags=[],
                    source="facebook",
                    source_url=f"https://facebook.com/events/{event_id.group(1)}",
                    source_id=f"fb_{event_id.group(1)}",
                ))
            except Exception as e:
                logger.debug(f"Error parsing event link: {e}")

        return events

    def _parse_event_page(self, html: str, url: str) -> Optional[ScrapedEvent]:
        """Parse a Facebook event page"""
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract title
            title_el = soup.find('title')
            title = title_el.text if title_el else "Event"
            title = re.sub(r'\s*\|\s*Facebook.*$', '', title).strip()

            # Try to extract from JSON-LD
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Event':
                        return self._parse_json_ld_event(data, url)
                except:
                    pass

            # Extract description from meta
            desc_el = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
            description = desc_el.get('content', '') if desc_el else ''

            # Extract image
            img_el = soup.find('meta', {'property': 'og:image'})
            image_url = img_el.get('content') if img_el else None

            # Extract event ID
            event_id = re.search(r'/events/(\d+)', url)
            source_id = f"fb_{event_id.group(1)}" if event_id else f"fb_{hash(url)}"

            return ScrapedEvent(
                title=title[:255],
                description=description[:2000],
                start_datetime=self._extract_datetime(html),
                end_datetime=None,
                venue_name=self._extract_venue(html),
                address=None,
                district=self._detect_district(f"{title} {description}"),
                category=self._detect_category(f"{title} {description}"),
                tags=self._extract_hashtags(description),
                source="facebook",
                source_url=url,
                source_id=source_id,
                image_url=image_url,
                price_info=self._extract_price(description),
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error parsing event page: {e}")
            return None

    def _parse_json_ld_event(self, data: dict, url: str) -> Optional[ScrapedEvent]:
        """Parse JSON-LD event data"""
        try:
            title = data.get('name', 'Event')

            # Parse date
            start_datetime = None
            if data.get('startDate'):
                try:
                    start_datetime = datetime.fromisoformat(data['startDate'].replace('Z', '+00:00'))
                except:
                    pass

            end_datetime = None
            if data.get('endDate'):
                try:
                    end_datetime = datetime.fromisoformat(data['endDate'].replace('Z', '+00:00'))
                except:
                    pass

            # Location
            location = data.get('location', {})
            venue_name = location.get('name') if isinstance(location, dict) else None
            address = None
            if isinstance(location, dict) and location.get('address'):
                addr = location['address']
                address = addr if isinstance(addr, str) else addr.get('streetAddress')

            return ScrapedEvent(
                title=title[:255],
                description=data.get('description', '')[:2000],
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                venue_name=venue_name,
                address=address,
                district=self._detect_district(f"{title} {venue_name or ''} {address or ''}"),
                category=self._detect_category(f"{title} {data.get('description', '')}"),
                tags=[],
                source="facebook",
                source_url=url,
                source_id=f"fb_{hash(url) % 10**10}",
                image_url=data.get('image', [None])[0] if isinstance(data.get('image'), list) else data.get('image'),
                price_info=None,
                organizer_name=data.get('organizer', {}).get('name') if isinstance(data.get('organizer'), dict) else None,
            )
        except Exception as e:
            logger.error(f"Error parsing JSON-LD: {e}")
            return None

    def _extract_datetime(self, html: str) -> Optional[datetime]:
        """Try to extract datetime from page content"""
        # Look for common date patterns in the HTML
        patterns = [
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})',  # ISO format
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}\s+\d{1,2}:\d{2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    from dateutil.parser import parse
                    return parse(match.group(1))
                except:
                    pass
        return None

    def _extract_venue(self, html: str) -> Optional[str]:
        """Extract venue from page"""
        soup = BeautifulSoup(html, 'lxml')
        # Look for location-related elements
        for text in soup.stripped_strings:
            if any(kw in text.lower() for kw in ['rooftop', 'bar', 'club', 'venue', 'hotel']):
                if len(text) < 100:
                    return text
        return None

    def _detect_district(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit', 'silom': 'Silom',
            'sathorn': 'Sathorn', 'siam': 'Siam',
            'bangna': 'Bangna', 'ari': 'Ari',
        }
        for key, value in districts.items():
            if key in text_lower:
                return value
        return None

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner']):
            return 'food'
        return 'other'

    def _extract_hashtags(self, text: str) -> list:
        return re.findall(r'#(\w+)', text)[:10]

    def _extract_price(self, text: str) -> Optional[str]:
        match = re.search(r'(\d+)\s*(THB|baht|฿)', text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} THB"
        if 'free' in text.lower():
            return 'Free'
        return None

    def scrape_all_queries(self) -> list[ScrapedEvent]:
        """Scrape all configured search queries"""
        all_events = []
        seen_ids = set()

        for query in self.SEARCH_QUERIES:
            try:
                events = self.search_events(query, max_results=10)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)
            except Exception as e:
                logger.error(f"Error with query '{query}': {e}")

        return all_events


if __name__ == "__main__":
    scraper = FacebookWebScraper()
    try:
        events = scraper.scrape_all_queries()
        print(f"\nTotal events found: {len(events)}")
        for event in events[:5]:
            print(f"\n{'='*60}")
            print(f"Title: {event.title}")
            print(f"Date: {event.start_datetime}")
            print(f"URL: {event.source_url}")
    finally:
        scraper.close()
