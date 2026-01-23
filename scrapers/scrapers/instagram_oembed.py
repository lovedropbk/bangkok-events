"""
Instagram scraper using oEmbed API and known venue accounts.
oEmbed doesn't require authentication and works for public posts.

This approach:
1. Uses a curated list of known Bangkok event organizers
2. Uses Instagram's public oEmbed API to get post details
3. Monitors RSS feeds and other sources for new event announcements
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


# Known Bangkok event organizers and venues on Instagram
# These are real accounts that regularly post events
BANGKOK_EVENT_ACCOUNTS = {
    # Underground/Techno scene
    "sataniebkk": {"district": "Thonglor", "category": "party"},
    "kolorbkk": {"district": "Thonglor", "category": "party"},
    "saferoombangkok": {"district": "RCA", "category": "party"},
    "duenobkk": {"district": "Thonglor", "category": "party"},
    "mustachebkk": {"district": "Thonglor", "category": "party"},

    # Venues
    "beamthonglor": {"district": "Thonglor", "category": "music"},
    "thecommonsbkk": {"district": "Thonglor", "category": "market"},
    "warehouse30bkk": {"district": "Charoenkrung", "category": "art"},
    "jamfactorybkk": {"district": "Thonburi", "category": "art"},

    # Event pages
    "bangkoknightlife": {"district": None, "category": "party"},
    "bangkokinvader": {"district": None, "category": "party"},
}

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
    "Thonburi": (13.7200, 100.4950),
}


class InstagramOEmbedScraper:
    """
    Scraper using Instagram's oEmbed API.
    Works without authentication for public posts.
    """

    OEMBED_URL = "https://api.instagram.com/oembed"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)

    def close(self):
        self.client.close()

    def get_post_details(self, post_url: str) -> Optional[dict]:
        """
        Get post details using Instagram oEmbed API.
        Returns HTML embed with caption, author, etc.
        """
        try:
            resp = self.client.get(
                self.OEMBED_URL,
                params={"url": post_url, "omitscript": "true"}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"oEmbed error: {e}")
        return None

    def parse_embed_to_event(self, embed_data: dict, post_url: str, account_info: dict) -> Optional[ScrapedEvent]:
        """Parse oEmbed response into event"""
        try:
            # Extract caption from HTML
            html = embed_data.get('html', '')
            caption_match = re.search(r'<p>(.+?)</p>', html, re.DOTALL)
            caption = caption_match.group(1) if caption_match else ''

            # Clean HTML entities
            caption = re.sub(r'<[^>]+>', '', caption)
            caption = caption.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

            if not self._looks_like_event(caption):
                return None

            # Extract title
            lines = [l.strip() for l in caption.split('\n') if l.strip()]
            title = ""
            for line in lines[:3]:
                clean = re.sub(r'[#@]\w+', '', line).strip()
                if len(clean) > 10:
                    title = clean[:150]
                    break
            if not title:
                title = embed_data.get('title', 'Bangkok Event')

            # Extract datetime
            start_datetime = self._extract_datetime(caption)
            if not start_datetime or start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Get venue/district from account info or caption
            district = account_info.get('district') or self._detect_district(caption)
            venue = self._extract_venue(caption)
            category = account_info.get('category') or self._detect_category(caption)

            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            # Extract shortcode for ID
            shortcode_match = re.search(r'/p/([A-Za-z0-9_-]+)', post_url)
            shortcode = shortcode_match.group(1) if shortcode_match else hashlib.md5(post_url.encode()).hexdigest()[:16]

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
                tags=self._extract_tags(caption),
                source="instagram",
                source_url=post_url,
                source_id=f"ig_{shortcode}",
                image_url=embed_data.get('thumbnail_url'),
                price_info=self._extract_price(caption),
                organizer_name=embed_data.get('author_name'),
            )

        except Exception as e:
            logger.error(f"Error parsing embed: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        if not text or len(text) < 30:
            return False
        text_lower = text.lower()

        locations = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit', 'silom', 'siam', 'rca']
        has_location = any(loc in text_lower for loc in locations)

        event_words = ['party', 'event', 'tonight', 'dj', 'live', 'tickets', 'doors', 'lineup', 'rave']
        has_event = any(word in text_lower for word in event_words)

        date_patterns = [r'\d{1,2}[\/\-]\d{1,2}', r'tonight|tomorrow|this saturday|this friday']
        has_date = any(re.search(p, text_lower) for p in date_patterns)

        return (has_location or has_event) and has_date

    def _extract_datetime(self, text: str) -> Optional[datetime]:
        text_lower = text.lower()
        now = datetime.now()

        if 'tonight' in text_lower:
            return now.replace(hour=21, minute=0, second=0)
        if 'tomorrow' in text_lower:
            return (now + timedelta(days=1)).replace(hour=21, minute=0, second=0)

        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if f'this {day}' in text_lower:
                days_ahead = i - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).replace(hour=21, minute=0, second=0)

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
            r'([A-Za-z0-9\s]+(?:rooftop|bar|club|warehouse))',
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
            'rca': 'RCA', 'ratchada': 'RCA',
        }
        for k, v in districts.items():
            if k in text_lower:
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


class ProfileScraper:
    """
    Scrapes known Bangkok event organizer profiles.
    Uses public profile pages to find recent posts.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "text/html,application/xhtml+xml",
    }

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)
        self.oembed = InstagramOEmbedScraper()

    def close(self):
        self.client.close()
        self.oembed.close()

    def scrape_profile(self, username: str, account_info: dict, max_posts: int = 10) -> List[ScrapedEvent]:
        """Scrape a profile for event posts"""
        events = []
        logger.info(f"Scraping @{username}...")

        try:
            # Try to get profile page
            url = f"https://www.instagram.com/{username}/"
            resp = self.client.get(url)

            if resp.status_code != 200:
                return events

            html = resp.text

            # Extract post shortcodes from HTML
            shortcodes = re.findall(r'/p/([A-Za-z0-9_-]+)/', html)
            shortcodes = list(set(shortcodes))[:max_posts]

            for shortcode in shortcodes:
                post_url = f"https://www.instagram.com/p/{shortcode}/"
                embed_data = self.oembed.get_post_details(post_url)

                if embed_data:
                    event = self.oembed.parse_embed_to_event(embed_data, post_url, account_info)
                    if event:
                        events.append(event)
                        logger.info(f"  Found event: {event.title[:40]}...")

        except Exception as e:
            logger.error(f"Error scraping @{username}: {e}")

        return events

    def scrape_all_accounts(self) -> List[ScrapedEvent]:
        """Scrape all known Bangkok event accounts"""
        all_events = []
        seen_ids = set()

        for username, info in BANGKOK_EVENT_ACCOUNTS.items():
            try:
                events = self.scrape_profile(username, info, max_posts=5)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)
            except Exception as e:
                logger.error(f"Failed @{username}: {e}")

        return all_events


def run_instagram_scraper() -> List[ScrapedEvent]:
    """Main entry point for Instagram scraping"""
    scraper = ProfileScraper()

    try:
        logger.info("=" * 60)
        logger.info("Scraping known Bangkok event accounts...")
        events = scraper.scrape_all_accounts()
        logger.info(f"Total: {len(events)} events found")
        return events
    finally:
        scraper.close()


if __name__ == "__main__":
    events = run_instagram_scraper()

    print(f"\n{'='*60}")
    print(f"FOUND {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:10]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    Price: {e.price_info}")
        print(f"    Image: {'Yes' if e.image_url else 'No'}")
        print(f"    URL: {e.source_url}")
