"""
Browser Session-based Instagram Scraper.

This scraper extracts session cookies from the user's browser (Chrome/Firefox)
where they are already logged into Instagram. This is the most reliable
free method for Instagram scraping.

Supported browsers:
- Google Chrome
- Mozilla Firefox
- Microsoft Edge

Usage:
1. Log into Instagram in your browser (stay logged in)
2. Run this script - it will automatically find your session
3. Events will be scraped using your authenticated session

Note: This only works on the machine where you're logged in.
"""

import os
import sys
import json
import sqlite3
import shutil
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass
from pathlib import Path

import httpx

# Try to import browser cookie libraries
try:
    import browser_cookie3
    HAS_BROWSER_COOKIE = True
except ImportError:
    HAS_BROWSER_COOKIE = False

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


def get_instagram_cookies_from_browser() -> Optional[Dict[str, str]]:
    """
    Extract Instagram cookies from installed browsers.
    Tries Chrome, Firefox, Edge in order.
    """
    if not HAS_BROWSER_COOKIE:
        logger.warning("browser_cookie3 not installed. Run: pip install browser-cookie3")
        return None

    cookies = {}

    # Try different browsers
    browsers = [
        ('Chrome', browser_cookie3.chrome),
        ('Firefox', browser_cookie3.firefox),
        ('Edge', browser_cookie3.edge),
    ]

    for browser_name, browser_func in browsers:
        try:
            logger.info(f"Trying {browser_name}...")
            cj = browser_func(domain_name='.instagram.com')

            for cookie in cj:
                cookies[cookie.name] = cookie.value

            # Check if we got the essential cookies
            if 'sessionid' in cookies:
                logger.info(f"Found Instagram session in {browser_name}")
                return cookies

        except Exception as e:
            logger.debug(f"{browser_name} failed: {e}")
            continue

    logger.warning("No Instagram session found in any browser")
    return None


class BrowserSessionScraper:
    """
    Instagram scraper using browser session cookies.
    """

    GRAPHQL_URL = "https://www.instagram.com/graphql/query/"

    # GraphQL query hashes (these may need updating periodically)
    PROFILE_QUERY_HASH = "c9100bf9110dd6361671f113dd02e7d6"
    HASHTAG_QUERY_HASH = "9b498c08113f1a09f24a15c77b9f4e66"

    def __init__(self, cookies: Dict[str, str] = None):
        """
        Initialize with cookies.

        Args:
            cookies: Dict of cookies (must include 'sessionid')
        """
        self.cookies = cookies or {}
        self.authenticated = 'sessionid' in self.cookies

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
        }

        self.client = httpx.Client(
            headers=headers,
            cookies=self.cookies,
            timeout=30.0,
            follow_redirects=True
        )

    def close(self):
        self.client.close()

    def get_profile_posts(self, username: str, max_posts: int = 12) -> List[dict]:
        """Get recent posts from a profile"""
        posts = []

        try:
            # First get the profile page to extract user ID and initial data
            resp = self.client.get(f"https://www.instagram.com/{username}/")

            if resp.status_code == 404:
                logger.error(f"Profile @{username} not found")
                return posts

            if "login" in resp.url.path.lower():
                logger.warning("Redirected to login - session may be invalid")
                return posts

            html = resp.text

            # Try to extract shared_data JSON
            import re
            match = re.search(r'window\._sharedData\s*=\s*({.+?});', html)
            if match:
                try:
                    shared_data = json.loads(match.group(1))
                    user_data = shared_data.get('entry_data', {}).get('ProfilePage', [{}])[0].get('graphql', {}).get('user', {})

                    edges = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
                    for edge in edges[:max_posts]:
                        posts.append(edge.get('node', {}))

                    if posts:
                        return posts
                except json.JSONDecodeError:
                    pass

            # Try alternate pattern for newer Instagram
            match = re.search(r'"user":\s*({.+?})\s*,\s*"viewer"', html)
            if match:
                try:
                    # This won't work for complex nested JSON, but worth trying
                    pass
                except:
                    pass

            # Try extracting post shortcodes from HTML and fetch individually
            shortcodes = re.findall(r'/p/([A-Za-z0-9_-]+)/', html)
            shortcodes = list(set(shortcodes))[:max_posts]

            for shortcode in shortcodes:
                post_data = self._get_post_data(shortcode)
                if post_data:
                    posts.append(post_data)

        except Exception as e:
            logger.error(f"Error getting profile posts: {e}")

        return posts

    def _get_post_data(self, shortcode: str) -> Optional[dict]:
        """Get data for a single post"""
        try:
            resp = self.client.get(f"https://www.instagram.com/p/{shortcode}/")
            if resp.status_code != 200:
                return None

            html = resp.text

            import re
            # Try to extract post data
            match = re.search(r'"graphql":\s*{\s*"shortcode_media":\s*({.+?})\s*}\s*}', html)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass

            # Extract basic info from HTML
            caption_match = re.search(r'"caption":\s*{\s*"text":\s*"(.+?)"', html)
            caption = caption_match.group(1) if caption_match else ""
            caption = caption.encode().decode('unicode_escape')

            owner_match = re.search(r'"username":\s*"([^"]+)"', html)
            owner = owner_match.group(1) if owner_match else ""

            timestamp_match = re.search(r'"taken_at_timestamp":\s*(\d+)', html)
            timestamp = int(timestamp_match.group(1)) if timestamp_match else None

            image_match = re.search(r'"display_url":\s*"([^"]+)"', html)
            image_url = image_match.group(1).replace('\\u0026', '&') if image_match else None

            return {
                'shortcode': shortcode,
                'edge_media_to_caption': {'edges': [{'node': {'text': caption}}]} if caption else {'edges': []},
                'owner': {'username': owner},
                'taken_at_timestamp': timestamp,
                'display_url': image_url,
            }

        except Exception as e:
            logger.debug(f"Error getting post {shortcode}: {e}")
            return None

    def scrape_profile(self, username: str, max_posts: int = 10) -> List[ScrapedEvent]:
        """Scrape a profile for event posts"""
        events = []
        logger.info(f"Scraping @{username}...")

        try:
            posts = self.get_profile_posts(username, max_posts)
            logger.info(f"  Found {len(posts)} posts")

            for post in posts:
                event = self._parse_post(post, username)
                if event:
                    events.append(event)
                    logger.info(f"  Event: {event.title[:40]}...")

        except Exception as e:
            logger.error(f"Error scraping @{username}: {e}")

        return events

    def _parse_post(self, post: dict, account_username: str = None) -> Optional[ScrapedEvent]:
        """Parse Instagram post data into event"""
        try:
            # Get caption
            caption_edges = post.get('edge_media_to_caption', {}).get('edges', [])
            caption = caption_edges[0].get('node', {}).get('text', '') if caption_edges else ''

            if not caption or not self._looks_like_event(caption):
                return None

            # Extract title
            title = self._extract_title(caption)
            if not title:
                return None

            # Get timestamp
            timestamp = post.get('taken_at_timestamp')
            post_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()

            # Extract datetime
            start_datetime = self._extract_datetime(caption, post_date)
            if not start_datetime:
                return None

            # Skip past events
            if start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Location
            district = self._detect_district(caption)
            venue = self._extract_venue(caption)

            lat, lng = None, None
            location = post.get('location', {})
            if location:
                lat = location.get('lat')
                lng = location.get('lng')
            if not lat and district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            # Image
            image_url = post.get('display_url') or post.get('thumbnail_src')

            # Shortcode
            shortcode = post.get('shortcode', '')

            return ScrapedEvent(
                title=title,
                description=caption[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=venue,
                address=None,
                latitude=float(lat) if lat else None,
                longitude=float(lng) if lng else None,
                district=district,
                category=self._detect_category(caption),
                tags=self._extract_tags(caption),
                source="instagram",
                source_url=f"https://www.instagram.com/p/{shortcode}/" if shortcode else "",
                source_id=f"ig_{shortcode}" if shortcode else f"ig_{hash(title)}",
                image_url=image_url,
                price_info=self._extract_price(caption),
                organizer_name=post.get('owner', {}).get('username') or account_username,
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        if not text or len(text) < 30:
            return False
        text_lower = text.lower()
        locations = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit', 'silom', 'siam', 'rca']
        event_words = ['party', 'event', 'tonight', 'tomorrow', 'dj', 'live', 'tickets', 'rave', 'show']
        import re
        date_patterns = [r'\d{1,2}[\/\-]\d{1,2}', r'tonight|tomorrow|this saturday|this friday']
        has_location = any(loc in text_lower for loc in locations)
        has_event = any(word in text_lower for word in event_words)
        has_date = any(re.search(p, text_lower) for p in date_patterns)
        return (has_location or has_event) and has_date

    def _extract_title(self, text: str) -> Optional[str]:
        import re
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines[:5]:
            clean = re.sub(r'[#@]\w+', '', line).strip()
            if 10 < len(clean) < 150:
                return clean
        return None

    def _extract_datetime(self, text: str, post_date: datetime) -> Optional[datetime]:
        import re
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

        if post_date and (now - post_date).days < 3:
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour > 12:
                days_until_saturday = 7
            return (now + timedelta(days=days_until_saturday)).replace(hour=21, minute=0, second=0, microsecond=0)

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
        import re
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
        import re
        tags = re.findall(r'#([A-Za-z0-9_]+)', text)
        return [t.lower() for t in tags if 2 < len(t) < 25][:10]

    def _extract_price(self, text: str) -> Optional[str]:
        import re
        if 'free' in text.lower():
            return 'Free'
        m = re.search(r'(\d+)\s*(THB|baht)', text, re.I)
        return f'{m.group(1)} THB' if m else None


def run_browser_session_scraper() -> List[ScrapedEvent]:
    """Run the browser session scraper"""
    logger.info("=" * 60)
    logger.info("BROWSER SESSION INSTAGRAM SCRAPER")
    logger.info("=" * 60)

    # Try to get cookies from browser
    cookies = get_instagram_cookies_from_browser()

    if not cookies or 'sessionid' not in cookies:
        logger.error("No Instagram session found!")
        logger.info("")
        logger.info("To use this scraper:")
        logger.info("1. Install browser-cookie3: pip install browser-cookie3")
        logger.info("2. Log into Instagram in Chrome/Firefox/Edge")
        logger.info("3. Run this script again")
        return []

    scraper = BrowserSessionScraper(cookies)
    all_events = []
    seen_ids = set()

    logger.info(f"\nScraping {len(BANGKOK_ACCOUNTS)} Bangkok event accounts...")

    for account in BANGKOK_ACCOUNTS:
        try:
            events = scraper.scrape_profile(account, max_posts=5)
            for event in events:
                if event.source_id not in seen_ids:
                    seen_ids.add(event.source_id)
                    all_events.append(event)
        except Exception as e:
            logger.error(f"Failed @{account}: {e}")

    scraper.close()

    logger.info("=" * 60)
    logger.info(f"TOTAL: {len(all_events)} events found")

    return all_events


if __name__ == "__main__":
    events = run_browser_session_scraper()

    print(f"\n{'='*60}")
    print(f"FOUND {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:15]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    URL: {e.source_url}")
