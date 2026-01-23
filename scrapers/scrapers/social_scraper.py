"""
Robust Instagram and Facebook scrapers using multiple approaches.
This module combines several techniques to reliably extract events.
"""

import re
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    """Represents a scraped event with all required details"""
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


class InstagramGraphQLScraper:
    """
    Instagram scraper using GraphQL endpoints.
    Works by accessing Instagram's public GraphQL API for hashtag data.
    """

    # Instagram's GraphQL endpoint for hashtags
    GRAPHQL_URL = "https://www.instagram.com/graphql/query/"

    # Query hash for hashtag posts (these change periodically, need to update)
    HASHTAG_QUERY_HASH = "9b498c08113f1e09617a1703c22b2f32"  # May need updating

    # Bangkok event hashtags - curated for underground/niche events
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
        "bangkokevent",
        "satanievent",  # Popular Bangkok party organizer
        "safespacbkk",
        "kolorbkk",
    ]

    # Bangkok district coordinates for geo-enrichment
    DISTRICT_COORDS = {
        "Thonglor": (13.7307, 100.5844),
        "Ekkamai": (13.7234, 100.5874),
        "Sukhumvit": (13.7400, 100.5600),
        "Phrom Phong": (13.7312, 100.5698),
        "Silom": (13.7260, 100.5230),
        "Sathorn": (13.7200, 100.5280),
        "Siam": (13.7453, 100.5318),
        "Bangna": (13.6614, 100.6156),
        "Central Bangkok": (13.7563, 100.5018),
        "Ratchada": (13.7580, 100.5740),
        "Ari": (13.7850, 100.5450),
        "RCA": (13.7567, 100.5623),
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "X-IG-App-ID": "936619743392459",  # Instagram web app ID
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/",
    }

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)
        self.session_cookies = {}

    def close(self):
        self.client.close()

    def _init_session(self):
        """Initialize session with Instagram cookies"""
        try:
            # Get initial page to get cookies
            resp = self.client.get("https://www.instagram.com/")
            if resp.status_code == 200:
                # Extract csrftoken from cookies
                for cookie in resp.cookies:
                    self.session_cookies[cookie.name] = cookie.value
                logger.info(f"Session initialized with cookies: {list(self.session_cookies.keys())}")
        except Exception as e:
            logger.error(f"Failed to init session: {e}")

    def scrape_hashtag_api(self, hashtag: str, max_posts: int = 30) -> List[ScrapedEvent]:
        """
        Scrape hashtag using Instagram's API endpoints.
        This accesses the mobile/web API which has fewer restrictions.
        """
        events = []
        logger.info(f"Scraping #{hashtag} via API...")

        try:
            # Try the web info endpoint first
            url = f"https://www.instagram.com/api/v1/tags/web_info/?tag_name={hashtag}"
            resp = self.client.get(url)

            if resp.status_code == 200:
                data = resp.json()
                events.extend(self._parse_api_response(data, hashtag))
            else:
                logger.warning(f"API returned {resp.status_code} for #{hashtag}")

                # Fallback: try the explore page with JSON extraction
                events.extend(self._scrape_explore_page(hashtag, max_posts))

        except Exception as e:
            logger.error(f"Error scraping #{hashtag}: {e}")

        return events[:max_posts]

    def _scrape_explore_page(self, hashtag: str, max_posts: int) -> List[ScrapedEvent]:
        """Fallback: scrape the explore page directly"""
        events = []

        try:
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            resp = self.client.get(url)

            if resp.status_code != 200:
                return events

            html = resp.text

            # Try to find JSON data in the page
            # Instagram embeds post data in script tags
            patterns = [
                r'"edge_hashtag_to_media"\s*:\s*({.+?})\s*,\s*"edge_hashtag_to_top_posts"',
                r'"recent"\s*:\s*({.+?})\s*,',
                r'window\.__additionalDataLoaded\([^,]+,\s*({.+?})\);',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        events.extend(self._parse_media_data(data, hashtag))
                        break
                    except json.JSONDecodeError:
                        continue

            # Also look for og:description which may contain event info
            og_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
            if og_match:
                description = og_match.group(1)
                if self._looks_like_event(description):
                    event = self._create_event_from_description(description, hashtag)
                    if event:
                        events.append(event)

        except Exception as e:
            logger.error(f"Error scraping explore page: {e}")

        return events

    def _parse_api_response(self, data: dict, hashtag: str) -> List[ScrapedEvent]:
        """Parse Instagram API response"""
        events = []

        try:
            # Navigate the response structure
            sections = data.get("data", {}).get("recent", {}).get("sections", [])

            for section in sections:
                medias = section.get("layout_content", {}).get("medias", [])
                for media_item in medias:
                    media = media_item.get("media", {})
                    event = self._parse_media_to_event(media, hashtag)
                    if event:
                        events.append(event)

        except Exception as e:
            logger.error(f"Error parsing API response: {e}")

        return events

    def _parse_media_data(self, data: dict, hashtag: str) -> List[ScrapedEvent]:
        """Parse media data from page JSON"""
        events = []

        try:
            edges = data.get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                event = self._parse_node_to_event(node, hashtag)
                if event:
                    events.append(event)
        except Exception as e:
            logger.error(f"Error parsing media data: {e}")

        return events

    def _parse_media_to_event(self, media: dict, hashtag: str) -> Optional[ScrapedEvent]:
        """Parse a single media item into an event"""
        try:
            caption_text = ""
            caption = media.get("caption", {})
            if isinstance(caption, dict):
                caption_text = caption.get("text", "")
            elif isinstance(caption, str):
                caption_text = caption

            if not caption_text or not self._looks_like_event(caption_text):
                return None

            return self._create_event_from_caption(
                caption=caption_text,
                media_id=media.get("pk", media.get("id", "")),
                shortcode=media.get("code", ""),
                image_url=media.get("image_versions2", {}).get("candidates", [{}])[0].get("url"),
                owner=media.get("user", {}).get("username"),
                timestamp=media.get("taken_at"),
                hashtag=hashtag,
            )
        except Exception as e:
            logger.debug(f"Error parsing media: {e}")
            return None

    def _parse_node_to_event(self, node: dict, hashtag: str) -> Optional[ScrapedEvent]:
        """Parse a graph node into an event"""
        try:
            # Get caption
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            caption_text = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""

            if not caption_text or not self._looks_like_event(caption_text):
                return None

            return self._create_event_from_caption(
                caption=caption_text,
                media_id=node.get("id", ""),
                shortcode=node.get("shortcode", ""),
                image_url=node.get("display_url") or node.get("thumbnail_src"),
                owner=node.get("owner", {}).get("username"),
                timestamp=node.get("taken_at_timestamp"),
                hashtag=hashtag,
            )
        except Exception as e:
            logger.debug(f"Error parsing node: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        """Check if text looks like an event announcement"""
        if not text or len(text) < 50:
            return False

        text_lower = text.lower()

        # Must have location context (Bangkok area)
        location_keywords = [
            'bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit',
            'silom', 'siam', 'sathorn', 'rca', 'ratchada', 'ari',
            'bangna', 'onnut', 'asok', 'phrom phong'
        ]
        has_location = any(kw in text_lower for kw in location_keywords)

        # Must have event indicators
        event_keywords = [
            'party', 'event', 'tonight', 'this saturday', 'this friday',
            'join us', 'doors', 'line up', 'lineup', 'tickets',
            'free entry', 'entry', 'dj', 'live', 'show', 'popup',
            'pop-up', 'exhibition', 'opening', 'launch', 'festival',
            'rave', 'warehouse', 'rooftop', 'underground'
        ]
        has_event = any(kw in text_lower for kw in event_keywords)

        # Should have time/date reference
        date_patterns = [
            r'\d{1,2}[\/\-\.]\d{1,2}',
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'tonight|tomorrow|this weekend',
            r'\d{1,2}\s*(pm|am)',
        ]
        has_date = any(re.search(p, text_lower) for p in date_patterns)

        return has_location and has_event and has_date

    def _create_event_from_caption(
        self,
        caption: str,
        media_id: str,
        shortcode: str,
        image_url: Optional[str],
        owner: Optional[str],
        timestamp: Optional[int],
        hashtag: str,
    ) -> Optional[ScrapedEvent]:
        """Create a full event object from caption data"""
        try:
            # Extract title (first meaningful line)
            lines = [l.strip() for l in caption.split('\n') if l.strip()]
            title = ""
            for line in lines[:3]:
                clean = re.sub(r'[#@]\w+', '', line).strip()
                if len(clean) > 10:
                    title = clean[:150]
                    break
            if not title:
                title = f"Event in Bangkok"

            # Extract datetime
            start_datetime = self._extract_datetime(caption, timestamp)
            if not start_datetime:
                return None

            # Skip past events
            if start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Extract venue and location
            venue = self._extract_venue(caption)
            district = self._extract_district(caption)

            # Get coordinates from district
            lat, lng = None, None
            if district and district in self.DISTRICT_COORDS:
                lat, lng = self.DISTRICT_COORDS[district]

            # Extract other details
            category = self._extract_category(caption)
            tags = self._extract_tags(caption)
            price = self._extract_price(caption)

            source_id = f"ig_{shortcode or media_id or hashlib.md5(caption[:100].encode()).hexdigest()[:16]}"
            source_url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""

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
                category=category,
                tags=tags,
                source="instagram",
                source_url=source_url,
                source_id=source_id,
                image_url=image_url,
                price_info=price,
                organizer_name=owner,
            )

        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return None

    def _create_event_from_description(self, description: str, hashtag: str) -> Optional[ScrapedEvent]:
        """Create event from og:description meta tag"""
        if not self._looks_like_event(description):
            return None

        return self._create_event_from_caption(
            caption=description,
            media_id=hashlib.md5(description.encode()).hexdigest()[:16],
            shortcode="",
            image_url=None,
            owner=None,
            timestamp=None,
            hashtag=hashtag,
        )

    def _extract_datetime(self, text: str, timestamp: Optional[int] = None) -> Optional[datetime]:
        """Extract event datetime from text"""
        text_lower = text.lower()
        base_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()

        # Relative dates
        if 'tonight' in text_lower:
            return base_date.replace(hour=21, minute=0, second=0, microsecond=0)
        if 'tomorrow' in text_lower:
            return (base_date + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)

        # Day of week
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if f'this {day}' in text_lower or (day in text_lower and 'last' not in text_lower):
                days_ahead = i - base_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (base_date + timedelta(days=days_ahead)).replace(hour=21, minute=0, second=0, microsecond=0)

        # Specific date patterns
        date_patterns = [
            (r'(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?', True),  # DD/MM or DD/MM/YYYY
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*(?:\s*(\d{4}))?', False),
        ]

        for pattern, is_numeric in date_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    from dateutil.parser import parse
                    date_str = match.group(0)
                    parsed = parse(date_str, dayfirst=True, fuzzy=True)

                    # If year is in past, assume next year
                    if parsed.year < base_date.year:
                        parsed = parsed.replace(year=base_date.year)

                    # Look for time in nearby text
                    time_match = re.search(
                        r'(\d{1,2})(?::(\d{2}))?\s*(pm|am|PM|AM)?',
                        text_lower[max(0, match.start()-20):match.end()+30]
                    )
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2) or 0)
                        if time_match.group(3) and 'pm' in time_match.group(3).lower() and hour < 12:
                            hour += 12
                        elif time_match.group(3) and 'am' in time_match.group(3).lower() and hour == 12:
                            hour = 0
                        parsed = parsed.replace(hour=hour, minute=minute)
                    else:
                        # Default to evening
                        parsed = parsed.replace(hour=21, minute=0)

                    return parsed
                except Exception:
                    continue

        return None

    def _extract_venue(self, text: str) -> Optional[str]:
        """Extract venue name"""
        patterns = [
            r'(?:at|@|venue|location)\s*[:\s]+\s*([A-Za-z0-9\s\-\'&]+?)(?:\n|,|\.|\||\#|$)',
            r'(?:^|\n)([A-Za-z0-9\s]+(?:rooftop|bar|club|lounge|venue|warehouse|hotel|restaurant|cafe|space))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                venue = match.group(1).strip()
                # Clean up
                venue = re.sub(r'\s+', ' ', venue)
                if 5 < len(venue) < 80:
                    return venue
        return None

    def _extract_district(self, text: str) -> Optional[str]:
        """Extract Bangkok district"""
        text_lower = text.lower()
        district_map = {
            'thonglor': 'Thonglor', 'thong lo': 'Thonglor', 'thong lor': 'Thonglor',
            'ekkamai': 'Ekkamai', 'ekamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit', 'suk': 'Sukhumvit',
            'silom': 'Silom',
            'sathorn': 'Sathorn',
            'siam': 'Siam',
            'bangna': 'Bangna', 'bang na': 'Bangna',
            'rca': 'RCA', 'ratchada': 'Ratchada',
            'ari': 'Ari',
            'phrom phong': 'Phrom Phong', 'prompong': 'Phrom Phong',
            'asok': 'Sukhumvit', 'asoke': 'Sukhumvit',
            'onnut': 'Sukhumvit', 'on nut': 'Sukhumvit',
        }
        for key, value in district_map.items():
            if key in text_lower:
                return value
        return "Central Bangkok"

    def _extract_category(self, text: str) -> str:
        """Extract event category"""
        text_lower = text.lower()

        categories = {
            'party': ['party', 'club', 'dance', 'nightlife', 'rave', 'warehouse'],
            'music': ['concert', 'live music', 'band', 'dj set', 'vinyl', 'jazz', 'techno', 'house'],
            'art': ['art', 'exhibition', 'gallery', 'artist', 'creative'],
            'food': ['food', 'dinner', 'popup', 'pop-up', 'brunch', 'dining'],
            'wellness': ['yoga', 'meditation', 'wellness', 'fitness'],
            'workshop': ['workshop', 'class', 'learn', 'masterclass'],
        }

        for cat, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return cat
        return 'party'

    def _extract_tags(self, text: str) -> list:
        """Extract hashtags as tags"""
        tags = re.findall(r'#([A-Za-z0-9_]+)', text)
        # Filter and clean
        clean_tags = []
        skip = {'instagram', 'instagood', 'love', 'follow', 'like', 'bangkok', 'thailand', 'reels', 'fyp'}
        for tag in tags:
            tag_lower = tag.lower()
            if len(tag) > 2 and len(tag) < 25 and tag_lower not in skip:
                clean_tags.append(tag_lower)
        return clean_tags[:10]

    def _extract_price(self, text: str) -> Optional[str]:
        """Extract price information"""
        patterns = [
            (r'(\d{1,3}(?:,\d{3})*)\s*(?:THB|thb|baht|฿)', 'THB'),
            (r'฿\s*(\d{1,3}(?:,\d{3})*)', 'THB'),
            (r'free\s*(?:entry|admission|entrance)?', 'FREE'),
            (r'no\s*cover', 'FREE'),
        ]
        for pattern, suffix in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if suffix == 'FREE':
                    return 'Free'
                return f"{match.group(1)} THB"
        return None

    def scrape_all_hashtags(self, max_per_tag: int = 20) -> List[ScrapedEvent]:
        """Scrape all configured hashtags"""
        all_events = []
        seen_ids = set()

        self._init_session()

        for hashtag in self.HASHTAGS:
            try:
                events = self.scrape_hashtag_api(hashtag, max_per_tag)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)
                logger.info(f"#{hashtag}: found {len(events)} events")
            except Exception as e:
                logger.error(f"Error with #{hashtag}: {e}")

        return all_events


class FacebookEventScraper:
    """
    Facebook event scraper using Graph API and public page access.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Known Bangkok event organizers and venues on Facebook
    EVENT_PAGES = [
        "BangkokEventGuide",
        "bangkokunderground",
        "kolorbangkok",
        "SafeRoomBangkok",
    ]

    SEARCH_QUERIES = [
        "bangkok party event",
        "thonglor event tonight",
        "bangkok underground party",
        "bangkok rooftop party",
    ]

    # District coordinates
    DISTRICT_COORDS = {
        "Thonglor": (13.7307, 100.5844),
        "Ekkamai": (13.7234, 100.5874),
        "Sukhumvit": (13.7400, 100.5600),
        "Silom": (13.7260, 100.5230),
        "Sathorn": (13.7200, 100.5280),
        "Siam": (13.7453, 100.5318),
        "RCA": (13.7567, 100.5623),
    }

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)

    def close(self):
        self.client.close()

    def scrape_public_events(self, max_events: int = 50) -> List[ScrapedEvent]:
        """Scrape publicly accessible Facebook events"""
        events = []

        # Try mobile Facebook which is more accessible
        for query in self.SEARCH_QUERIES:
            try:
                page_events = self._search_events_mobile(query)
                events.extend(page_events)
            except Exception as e:
                logger.error(f"Error searching '{query}': {e}")

        # Deduplicate
        seen = set()
        unique_events = []
        for e in events:
            if e.source_id not in seen:
                seen.add(e.source_id)
                unique_events.append(e)

        return unique_events[:max_events]

    def _search_events_mobile(self, query: str) -> List[ScrapedEvent]:
        """Search for events using mobile Facebook"""
        events = []

        try:
            # Use mobile Facebook search
            url = f"https://m.facebook.com/search/events/?q={query.replace(' ', '%20')}"
            resp = self.client.get(url)

            if resp.status_code != 200:
                return events

            # Parse HTML for event links and data
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'lxml')

            # Find event links
            event_links = soup.find_all('a', href=re.compile(r'/events/\d+'))

            for link in event_links[:20]:
                try:
                    event = self._parse_event_link(link)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.debug(f"Error parsing event link: {e}")

        except Exception as e:
            logger.error(f"Error in mobile search: {e}")

        return events

    def _parse_event_link(self, link) -> Optional[ScrapedEvent]:
        """Parse an event link element"""
        try:
            href = link.get('href', '')
            event_id_match = re.search(r'/events/(\d+)', href)
            if not event_id_match:
                return None

            event_id = event_id_match.group(1)

            # Get text content
            text = link.get_text(separator=' ', strip=True)
            if len(text) < 10:
                return None

            # Extract what we can from the link text
            title = text[:150]

            return ScrapedEvent(
                title=title,
                description="",
                start_datetime=None,  # Will need enrichment
                end_datetime=None,
                venue_name=None,
                address=None,
                latitude=None,
                longitude=None,
                district=self._detect_district(title),
                category=self._detect_category(title),
                tags=[],
                source="facebook",
                source_url=f"https://facebook.com/events/{event_id}",
                source_id=f"fb_{event_id}",
                image_url=None,
                price_info=None,
                organizer_name=None,
            )
        except Exception:
            return None

    def scrape_event_page(self, event_url: str) -> Optional[ScrapedEvent]:
        """Scrape a single event page for full details"""
        try:
            # Convert to mobile URL for better access
            if 'm.facebook.com' not in event_url:
                event_url = event_url.replace('www.facebook.com', 'm.facebook.com')
                event_url = event_url.replace('facebook.com', 'm.facebook.com')

            resp = self.client.get(event_url)
            if resp.status_code != 200:
                return None

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'lxml')

            # Extract structured data if available
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Event':
                        return self._parse_structured_event(data, event_url)
                except:
                    pass

            # Fallback to meta tags
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = re.sub(r'\s*\|\s*Facebook.*$', '', title_tag.text).strip()

            description = ""
            desc_meta = soup.find('meta', {'property': 'og:description'})
            if desc_meta:
                description = desc_meta.get('content', '')

            image_url = None
            img_meta = soup.find('meta', {'property': 'og:image'})
            if img_meta:
                image_url = img_meta.get('content')

            # Extract event ID
            event_id = re.search(r'/events/(\d+)', event_url)
            source_id = f"fb_{event_id.group(1)}" if event_id else f"fb_{hash(event_url) % 10**10}"

            district = self._detect_district(f"{title} {description}")
            lat, lng = None, None
            if district and district in self.DISTRICT_COORDS:
                lat, lng = self.DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title[:255] if title else "Facebook Event",
                description=description[:2000],
                start_datetime=self._extract_datetime(resp.text),
                end_datetime=None,
                venue_name=self._extract_venue(resp.text),
                address=None,
                latitude=lat,
                longitude=lng,
                district=district,
                category=self._detect_category(f"{title} {description}"),
                tags=self._extract_tags(description),
                source="facebook",
                source_url=event_url,
                source_id=source_id,
                image_url=image_url,
                price_info=self._extract_price(description),
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error scraping event page: {e}")
            return None

    def _parse_structured_event(self, data: dict, url: str) -> Optional[ScrapedEvent]:
        """Parse JSON-LD structured data"""
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
                if isinstance(geo, dict):
                    lat = geo.get('latitude')
                    lng = geo.get('longitude')

            description = data.get('description', '')
            district = self._detect_district(f"{title} {venue_name or ''} {address or ''}")

            if not lat and district and district in self.DISTRICT_COORDS:
                lat, lng = self.DISTRICT_COORDS[district]

            # Image
            image_url = None
            images = data.get('image')
            if isinstance(images, list) and images:
                image_url = images[0] if isinstance(images[0], str) else images[0].get('url')
            elif isinstance(images, str):
                image_url = images

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
                source_id=f"fb_{hash(url) % 10**10}",
                image_url=image_url,
                price_info=None,
                organizer_name=data.get('organizer', {}).get('name') if isinstance(data.get('organizer'), dict) else None,
            )
        except Exception as e:
            logger.error(f"Error parsing structured data: {e}")
            return None

    def _detect_district(self, text: str) -> Optional[str]:
        if not text:
            return None
        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit', 'silom': 'Silom',
            'sathorn': 'Sathorn', 'siam': 'Siam',
            'rca': 'RCA', 'ratchada': 'RCA',
        }
        for key, value in districts.items():
            if key in text_lower:
                return value
        return None

    def _detect_category(self, text: str) -> str:
        if not text:
            return 'party'
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner']):
            return 'food'
        return 'party'

    def _extract_datetime(self, html: str) -> Optional[datetime]:
        patterns = [
            r'"startDate"\s*:\s*"([^"]+)"',
            r'datetime="([^"]+)"',
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
        match = re.search(r'"location"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)
        return None

    def _extract_tags(self, text: str) -> list:
        return re.findall(r'#(\w+)', text)[:10]

    def _extract_price(self, text: str) -> Optional[str]:
        if 'free' in text.lower():
            return 'Free'
        match = re.search(r'(\d+)\s*(THB|baht)', text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} THB"
        return None


def run_all_scrapers() -> List[ScrapedEvent]:
    """Run all scrapers and return combined events"""
    all_events = []

    # Instagram
    logger.info("=" * 60)
    logger.info("Starting Instagram scraper...")
    try:
        ig = InstagramGraphQLScraper()
        ig_events = ig.scrape_all_hashtags()
        all_events.extend(ig_events)
        logger.info(f"Instagram: {len(ig_events)} events")
        ig.close()
    except Exception as e:
        logger.error(f"Instagram failed: {e}")

    # Facebook
    logger.info("=" * 60)
    logger.info("Starting Facebook scraper...")
    try:
        fb = FacebookEventScraper()
        fb_events = fb.scrape_public_events()
        all_events.extend(fb_events)
        logger.info(f"Facebook: {len(fb_events)} events")
        fb.close()
    except Exception as e:
        logger.error(f"Facebook failed: {e}")

    logger.info("=" * 60)
    logger.info(f"TOTAL: {len(all_events)} events scraped")

    return all_events


if __name__ == "__main__":
    events = run_all_scrapers()

    print(f"\n{'='*60}")
    print(f"SCRAPED {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:10]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    Venue: {e.venue_name}")
        print(f"    District: {e.district}")
        print(f"    Category: {e.category}")
        print(f"    Price: {e.price_info}")
        print(f"    Image: {'Yes' if e.image_url else 'No'}")
        print(f"    URL: {e.source_url}")
