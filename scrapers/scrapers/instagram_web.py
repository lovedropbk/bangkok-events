"""
Instagram scraper using web scraping approach for public data.
This scraper works without authentication by scraping public hashtag pages.
"""

import re
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    """Represents an event scraped from Instagram"""
    title: str
    description: str
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    venue_name: Optional[str]
    address: Optional[str]
    district: Optional[str]
    category: Optional[str]
    tags: list
    source: str = "instagram"
    source_url: str = ""
    source_id: str = ""
    image_url: Optional[str] = None
    price_info: Optional[str] = None
    organizer_name: Optional[str] = None


class InstagramWebScraper:
    """
    Instagram scraper using public web endpoints.
    Works without authentication by using public GraphQL endpoints.
    """

    # Bangkok event hashtags - curated for underground/small events
    HASHTAGS = [
        "bangkokparty",
        "bangkokunderground",
        "bkkparty",
        "thonglornightlife",
        "bangkokrooftop",
        "bangkokpopup",
        "bangkokrave",
        "bkknightlife",
        "bangkoklivemusic",
        "bangkokdj",
    ]

    # Known Bangkok venue accounts to monitor
    VENUE_ACCOUNTS = [
        "thecommonsbkk",
        "warehouse30bkk",
        "beamthonglor",
        "safehousebkk",
        "mustachebkk",
    ]

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    def __init__(self, rate_limit_delay: float = 3.0):
        """Initialize the scraper with rate limiting"""
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)
        self.rate_limit_delay = rate_limit_delay

    def close(self):
        self.client.close()

    def scrape_hashtag(self, hashtag: str, max_posts: int = 20) -> list[ScrapedEvent]:
        """
        Scrape public posts from a hashtag.

        Args:
            hashtag: The hashtag to scrape (without #)
            max_posts: Maximum posts to process

        Returns:
            List of ScrapedEvent objects
        """
        events = []
        logger.info(f"Scraping hashtag: #{hashtag}")

        try:
            # Try to get posts from hashtag explore page
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            response = self.client.get(url)

            if response.status_code == 200:
                # Extract shared_data from page
                html = response.text
                events.extend(self._parse_hashtag_page(html, hashtag))

        except Exception as e:
            logger.error(f"Error scraping hashtag {hashtag}: {e}")

        return events[:max_posts]

    def _parse_hashtag_page(self, html: str, hashtag: str) -> list[ScrapedEvent]:
        """Parse Instagram hashtag page HTML for event data"""
        events = []

        try:
            # Try to find embedded JSON data
            patterns = [
                r'window\._sharedData\s*=\s*({.*?});</script>',
                r'window\.__additionalDataLoaded\([^,]+,\s*({.*?})\);',
                r'"edge_hashtag_to_media":\s*({.*?}),',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        events.extend(self._extract_events_from_json(data, hashtag))
                        break
                    except json.JSONDecodeError:
                        continue

            # Fallback: parse HTML directly
            if not events:
                soup = BeautifulSoup(html, 'lxml')
                # Look for image posts and their metadata
                for meta in soup.find_all('meta', {'property': 'og:description'}):
                    content = meta.get('content', '')
                    if content and self._looks_like_event(content):
                        event = self._parse_caption_to_event(content, f"ig_hashtag_{hashtag}")
                        if event:
                            events.append(event)

        except Exception as e:
            logger.error(f"Error parsing hashtag page: {e}")

        return events

    def _extract_events_from_json(self, data: dict, hashtag: str) -> list[ScrapedEvent]:
        """Extract events from Instagram's JSON data structure"""
        events = []

        def find_edges(obj, depth=0):
            """Recursively find edge data in nested structure"""
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

        for edge in edges[:30]:  # Limit to avoid processing too many
            try:
                node = edge.get('node', edge)
                caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
                caption = caption_edges[0]['node']['text'] if caption_edges else ''

                if self._looks_like_event(caption):
                    event = self._parse_caption_to_event(
                        caption,
                        source_id=f"ig_{node.get('id', node.get('shortcode', ''))}",
                        image_url=node.get('display_url'),
                        shortcode=node.get('shortcode'),
                        owner_username=node.get('owner', {}).get('username'),
                        timestamp=node.get('taken_at_timestamp'),
                    )
                    if event:
                        events.append(event)
            except Exception as e:
                logger.debug(f"Error processing edge: {e}")

        return events

    def _looks_like_event(self, text: str) -> bool:
        """Check if text looks like an event announcement"""
        text_lower = text.lower()

        # Must mention Bangkok or Thai location
        location_keywords = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit', 'silom', 'siam', 'sathorn']
        has_location = any(kw in text_lower for kw in location_keywords)

        # Must have event-like keywords
        event_keywords = [
            'party', 'event', 'tonight', 'this saturday', 'this friday',
            'join us', 'doors open', 'line up', 'lineup', 'tickets',
            'free entry', 'admission', 'dj', 'live', 'show', 'popup',
            'pop-up', 'exhibition', 'opening', 'launch', 'festival'
        ]
        has_event_keyword = any(kw in text_lower for kw in event_keywords)

        # Should have date/time indication
        date_patterns = [
            r'\d{1,2}[\/\-\.]\d{1,2}',  # 15/01 or 15-01
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'tonight|tomorrow|this weekend',
            r'\d{1,2}(pm|am|:00)',
        ]
        has_date = any(re.search(p, text_lower) for p in date_patterns)

        return has_location and has_event_keyword and has_date

    def _parse_caption_to_event(
        self,
        caption: str,
        source_id: str,
        image_url: Optional[str] = None,
        shortcode: Optional[str] = None,
        owner_username: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> Optional[ScrapedEvent]:
        """Parse Instagram caption into an event"""
        try:
            # Extract title (first line, cleaned)
            lines = caption.strip().split('\n')
            title = re.sub(r'[#@]\w+', '', lines[0]).strip()
            if len(title) > 150:
                title = title[:147] + "..."
            if len(title) < 5:
                title = "Event in Bangkok"

            # Extract date/time
            start_datetime = self._extract_datetime(caption, timestamp)
            if not start_datetime or start_datetime < datetime.now():
                return None

            # Extract venue
            venue = self._extract_venue(caption)

            # Extract district
            district = self._extract_district(caption)

            # Extract category
            category = self._extract_category(caption)

            # Extract tags
            tags = re.findall(r'#(\w+)', caption)
            tags = [t.lower() for t in tags if len(t) > 2 and len(t) < 25][:8]

            # Extract price
            price = self._extract_price(caption)

            source_url = f"https://instagram.com/p/{shortcode}" if shortcode else ""

            return ScrapedEvent(
                title=title,
                description=caption[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=venue,
                address=None,
                district=district,
                category=category,
                tags=tags,
                source="instagram",
                source_url=source_url,
                source_id=source_id,
                image_url=image_url,
                price_info=price,
                organizer_name=owner_username,
            )

        except Exception as e:
            logger.error(f"Error parsing caption: {e}")
            return None

    def _extract_datetime(self, text: str, timestamp: Optional[int] = None) -> Optional[datetime]:
        """Extract event datetime from text"""
        text_lower = text.lower()
        base_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()

        # Relative dates
        if 'tonight' in text_lower or 'today' in text_lower:
            return base_date.replace(hour=20, minute=0)
        if 'tomorrow' in text_lower:
            return (base_date + timedelta(days=1)).replace(hour=20, minute=0)

        # Day of week
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if day in text_lower or f'this {day}' in text_lower:
                days_ahead = i - base_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (base_date + timedelta(days=days_ahead)).replace(hour=20, minute=0)

        # Specific date patterns
        patterns = [
            (r'(\d{1,2})[\/\-](\d{1,2})[\/\-]?(\d{2,4})?', '%d-%m-%Y'),
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d{4})?', None),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    from dateutil.parser import parse
                    date_str = match.group(0)
                    parsed = parse(date_str, dayfirst=True, fuzzy=True)

                    # Look for time
                    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(pm|am)?', text_lower[match.end():match.end()+20])
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2) or 0)
                        if time_match.group(3) == 'pm' and hour < 12:
                            hour += 12
                        parsed = parsed.replace(hour=hour, minute=minute)

                    return parsed
                except Exception:
                    continue

        return None

    def _extract_venue(self, text: str) -> Optional[str]:
        """Extract venue name from text"""
        patterns = [
            r'(?:at|@|venue|location)[:\s]+([A-Za-z0-9\s\-\']+?)(?:\n|,|\.|\||$)',
            r'([A-Za-z0-9\s]+(?:rooftop|bar|club|lounge|venue|hotel|restaurant|cafe))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                venue = match.group(1).strip()
                if 5 < len(venue) < 100:
                    return venue
        return None

    def _extract_district(self, text: str) -> Optional[str]:
        """Extract Bangkok district from text"""
        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'thong lo': 'Thonglor',
            'ekkamai': 'Ekkamai', 'ekamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit', 'silom': 'Silom',
            'sathorn': 'Sathorn', 'siam': 'Siam',
            'bangna': 'Bangna', 'ari': 'Ari',
            'phrom phong': 'Phrom Phong', 'asok': 'Sukhumvit',
            'rca': 'Ratchada', 'ratchada': 'Ratchada',
        }
        for key, value in districts.items():
            if key in text_lower:
                return value
        return None

    def _extract_category(self, text: str) -> str:
        """Extract event category from text"""
        text_lower = text.lower()
        if any(w in text_lower for w in ['techno', 'rave', 'underground', 'warehouse']):
            return 'music'
        if any(w in text_lower for w in ['party', 'club', 'dj', 'dance']):
            return 'party'
        if any(w in text_lower for w in ['art', 'exhibition', 'gallery']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner', 'popup', 'pop-up']):
            return 'food'
        if any(w in text_lower for w in ['yoga', 'meditation', 'wellness']):
            return 'wellness'
        if any(w in text_lower for w in ['workshop', 'class', 'learn']):
            return 'workshop'
        return 'party'

    def _extract_price(self, text: str) -> Optional[str]:
        """Extract price info from text"""
        patterns = [
            r'(\d+(?:,\d{3})*)\s*(?:THB|thb|baht|฿)',
            r'฿\s*(\d+(?:,\d{3})*)',
            r'free\s*(?:entry|admission)?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if 'free' in match.group(0).lower():
                    return 'Free'
                return f"{match.group(1)} THB"
        return None

    def scrape_all_hashtags(self, max_posts_per_tag: int = 15) -> list[ScrapedEvent]:
        """Scrape all configured hashtags"""
        all_events = []
        seen_ids = set()

        for hashtag in self.HASHTAGS:
            try:
                events = self.scrape_hashtag(hashtag, max_posts_per_tag)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)
                logger.info(f"Hashtag #{hashtag}: found {len(events)} events")
            except Exception as e:
                logger.error(f"Error with hashtag {hashtag}: {e}")

        return all_events


if __name__ == "__main__":
    scraper = InstagramWebScraper()
    try:
        events = scraper.scrape_all_hashtags()
        print(f"\nTotal events found: {len(events)}")
        for event in events[:10]:
            print(f"\n{'='*60}")
            print(f"Title: {event.title}")
            print(f"Date: {event.start_datetime}")
            print(f"District: {event.district}")
            print(f"Category: {event.category}")
    finally:
        scraper.close()
