"""
Instagram scraper using Instaloader library.
Instaloader is specifically designed for Instagram and handles authentication.

Two modes:
1. Anonymous (limited) - Can scrape public profiles but with rate limits
2. Session-based - Uses saved session from browser login for full access

Setup for session-based (recommended):
1. Log into Instagram in your browser
2. Export cookies using a browser extension (like "EditThisCookie")
3. Save session using: instaloader --login YOUR_USERNAME --sessionfile session.instaloader
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import instaloader
from instaloader import Profile, Hashtag, Post

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

# Known Bangkok event organizers and venues
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
    "glowinthedarkcollective",
    "darkside_bkk",
    "sugarclub_bangkok",
]

BANGKOK_HASHTAGS = [
    "bangkokparty",
    "bangkokunderground",
    "bangkoknightlife",
    "bangkokrave",
    "bangkokevents",
    "thonglornightlife",
    "bangkoktechno",
]


class InstaLoaderScraper:
    """
    Scraper using Instaloader library.
    """

    def __init__(self, session_file: Optional[str] = None, username: Optional[str] = None):
        """
        Initialize scraper.

        Args:
            session_file: Path to saved session file (from instaloader --login)
            username: Instagram username (required if using session)
        """
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )

        # Try to load session
        self.authenticated = False
        if session_file and username and os.path.exists(session_file):
            try:
                self.loader.load_session_from_file(username, session_file)
                self.authenticated = True
                logger.info(f"Loaded session for @{username}")
            except Exception as e:
                logger.warning(f"Failed to load session: {e}")

        # Also check environment variables
        ig_username = os.getenv("INSTAGRAM_USERNAME")
        ig_session = os.getenv("INSTAGRAM_SESSION_FILE")
        if not self.authenticated and ig_username and ig_session:
            try:
                self.loader.load_session_from_file(ig_username, ig_session)
                self.authenticated = True
                logger.info(f"Loaded session from env for @{ig_username}")
            except Exception as e:
                logger.warning(f"Failed to load session from env: {e}")

    def scrape_profile(self, username: str, max_posts: int = 10) -> List[ScrapedEvent]:
        """Scrape a profile for event posts"""
        events = []
        logger.info(f"Scraping @{username}...")

        try:
            profile = Profile.from_username(self.loader.context, username)

            posts_checked = 0
            for post in profile.get_posts():
                if posts_checked >= max_posts:
                    break

                event = self._parse_post(post, username)
                if event:
                    events.append(event)
                    logger.info(f"  Found event: {event.title[:40]}...")

                posts_checked += 1

        except instaloader.exceptions.ProfileNotExistsException:
            logger.error(f"Profile @{username} not found")
        except instaloader.exceptions.LoginRequiredException:
            logger.warning(f"Login required to scrape @{username}")
        except instaloader.exceptions.ConnectionException as e:
            logger.error(f"Connection error for @{username}: {e}")
        except Exception as e:
            logger.error(f"Error scraping @{username}: {e}")

        return events

    def scrape_hashtag(self, hashtag: str, max_posts: int = 20) -> List[ScrapedEvent]:
        """Scrape a hashtag for event posts"""
        events = []
        logger.info(f"Scraping #{hashtag}...")

        try:
            tag = Hashtag.from_name(self.loader.context, hashtag)

            posts_checked = 0
            for post in tag.get_posts():
                if posts_checked >= max_posts:
                    break

                event = self._parse_post(post)
                if event:
                    events.append(event)
                    logger.info(f"  Found event: {event.title[:40]}...")

                posts_checked += 1

        except instaloader.exceptions.LoginRequiredException:
            logger.warning(f"Login required to scrape #{hashtag}")
        except instaloader.exceptions.ConnectionException as e:
            logger.error(f"Connection error for #{hashtag}: {e}")
        except Exception as e:
            logger.error(f"Error scraping #{hashtag}: {e}")

        return events

    def _parse_post(self, post: Post, account_username: str = None) -> Optional[ScrapedEvent]:
        """Parse an Instagram post into an event"""
        try:
            caption = post.caption or ""

            # Check if it looks like an event
            if not self._looks_like_event(caption):
                return None

            # Extract title from first meaningful line
            title = self._extract_title(caption)
            if not title:
                return None

            # Extract datetime
            start_datetime = self._extract_datetime(caption, post.date_utc)
            if not start_datetime:
                return None

            # Skip past events
            if start_datetime < datetime.now() - timedelta(hours=6):
                return None

            # Extract location info
            district = self._detect_district(caption)
            venue = self._extract_venue(caption)

            # Get coords
            lat, lng = None, None
            if post.location:
                lat = post.location.lat
                lng = post.location.lng
            elif district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            # Category
            category = self._detect_category(caption)

            # Image URL
            image_url = post.url if hasattr(post, 'url') else None

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
                source_url=f"https://www.instagram.com/p/{post.shortcode}/",
                source_id=f"ig_{post.shortcode}",
                image_url=image_url,
                price_info=self._extract_price(caption),
                organizer_name=post.owner_username or account_username,
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        """Check if text looks like an event announcement"""
        if not text or len(text) < 30:
            return False

        text_lower = text.lower()

        # Must have location indicator
        locations = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit',
                     'silom', 'siam', 'rca', 'sathorn', 'ari']
        has_location = any(loc in text_lower for loc in locations)

        # Must have event indicator
        event_words = ['party', 'event', 'tonight', 'tomorrow', 'dj', 'live',
                       'tickets', 'doors', 'lineup', 'rave', 'show', 'festival',
                       'club', 'rooftop', 'underground']
        has_event = any(word in text_lower for word in event_words)

        # Date patterns
        date_patterns = [
            r'\d{1,2}[\/\-\.]\d{1,2}',  # 25/12, 25-12
            r'tonight|tomorrow|this saturday|this friday|this weekend',
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}',
        ]
        has_date = any(re.search(p, text_lower) for p in date_patterns)

        return (has_location or has_event) and has_date

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract event title from caption"""
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        for line in lines[:5]:
            # Remove hashtags and mentions
            clean = re.sub(r'[#@]\w+', '', line).strip()
            # Remove emojis (basic)
            clean = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', '', clean)
            clean = clean.strip()

            if 10 < len(clean) < 150:
                return clean

        return None

    def _extract_datetime(self, text: str, post_date: datetime) -> Optional[datetime]:
        """Extract event datetime from caption"""
        text_lower = text.lower()
        now = datetime.now()

        # Tonight
        if 'tonight' in text_lower:
            return now.replace(hour=21, minute=0, second=0, microsecond=0)

        # Tomorrow
        if 'tomorrow' in text_lower:
            return (now + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)

        # This weekend
        if 'this weekend' in text_lower:
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour > 12:
                days_until_saturday = 7
            return (now + timedelta(days=days_until_saturday)).replace(hour=21, minute=0, second=0, microsecond=0)

        # Day of week
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if f'this {day}' in text_lower or f'next {day}' in text_lower:
                days_ahead = (i - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return (now + timedelta(days=days_ahead)).replace(hour=21, minute=0, second=0, microsecond=0)

        # Date pattern: 25/12, 25-12, 25.12
        match = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})', text_lower)
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

        # Month name pattern: Jan 25, January 25
        match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})', text_lower)
        if match:
            try:
                from dateutil.parser import parse
                return parse(match.group(0)).replace(hour=21, minute=0)
            except:
                pass

        # If post is recent (within 3 days), assume it's about an upcoming event
        if post_date and (now - post_date).days < 3:
            # Use next weekend as default
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour > 12:
                days_until_saturday = 7
            return (now + timedelta(days=days_until_saturday)).replace(hour=21, minute=0, second=0, microsecond=0)

        return None

    def _detect_district(self, text: str) -> Optional[str]:
        """Detect Bangkok district from text"""
        if not text:
            return None

        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'thong lo': 'Thonglor',
            'ekkamai': 'Ekkamai', 'ekamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit',
            'silom': 'Silom',
            'sathorn': 'Sathorn',
            'siam': 'Siam',
            'bangna': 'Bangna', 'bang na': 'Bangna',
            'rca': 'RCA', 'ratchada': 'RCA',
            'ari': 'Ari',
            'charoenkrung': 'Charoenkrung', 'charoen krung': 'Charoenkrung',
        }

        for key, value in districts.items():
            if key in text_lower:
                return value

        return None

    def _extract_venue(self, text: str) -> Optional[str]:
        """Extract venue name from text"""
        patterns = [
            r'(?:at|@|venue|location)[:\s]+([A-Za-z0-9\s\-\']+?)(?:\n|,|\.|#|$)',
            r'([A-Za-z0-9\s]+(?:rooftop|bar|club|warehouse|studio|gallery))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                venue = match.group(1).strip()
                if 5 < len(venue) < 60:
                    return venue

        return None

    def _detect_category(self, text: str) -> str:
        """Detect event category from text"""
        text_lower = text.lower()

        if any(w in text_lower for w in ['party', 'club', 'dj', 'rave', 'techno', 'house']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live', 'band', 'gig']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition', 'gallery', 'show']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner', 'brunch', 'popup', 'pop-up']):
            return 'food'
        if any(w in text_lower for w in ['workshop', 'class', 'learn', 'course']):
            return 'workshop'
        if any(w in text_lower for w in ['market', 'bazaar', 'fair']):
            return 'market'

        return 'party'

    def _extract_tags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        tags = re.findall(r'#([A-Za-z0-9_]+)', text)
        return [t.lower() for t in tags if 2 < len(t) < 25][:10]

    def _extract_price(self, text: str) -> Optional[str]:
        """Extract price info from text"""
        text_lower = text.lower()

        if 'free entry' in text_lower or 'free admission' in text_lower or 'no cover' in text_lower:
            return 'Free'
        if 'free' in text_lower and 'before' in text_lower:
            match = re.search(r'free\s+(?:entry\s+)?before\s+(\d+(?::\d+)?)', text_lower)
            if match:
                return f'Free before {match.group(1)}'

        # Price patterns
        patterns = [
            r'(\d+)\s*(thb|baht|฿)',
            r'(thb|baht|฿)\s*(\d+)',
            r'entry[:\s]+(\d+)',
            r'cover[:\s]+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                # Get the number
                for g in match.groups():
                    if g and g.isdigit():
                        return f'{g} THB'

        return None


def run_instaloader_scraper(session_file: str = None, username: str = None) -> List[ScrapedEvent]:
    """
    Run the Instagram scraper using Instaloader.

    Args:
        session_file: Path to instaloader session file
        username: Instagram username for session

    Returns:
        List of scraped events
    """
    scraper = InstaLoaderScraper(session_file, username)
    all_events = []
    seen_ids = set()

    logger.info("=" * 60)
    logger.info("INSTALOADER INSTAGRAM SCRAPER")
    logger.info(f"Authenticated: {scraper.authenticated}")
    logger.info("=" * 60)

    # Scrape known accounts
    logger.info("\nScraping known Bangkok event accounts...")
    for account in BANGKOK_ACCOUNTS[:5]:  # Start with first 5
        try:
            events = scraper.scrape_profile(account, max_posts=5)
            for event in events:
                if event.source_id not in seen_ids:
                    seen_ids.add(event.source_id)
                    all_events.append(event)
        except Exception as e:
            logger.error(f"Failed @{account}: {e}")

    # Scrape hashtags (requires authentication usually)
    if scraper.authenticated:
        logger.info("\nScraping Bangkok event hashtags...")
        for hashtag in BANGKOK_HASHTAGS[:3]:  # Start with first 3
            try:
                events = scraper.scrape_hashtag(hashtag, max_posts=10)
                for event in events:
                    if event.source_id not in seen_ids:
                        seen_ids.add(event.source_id)
                        all_events.append(event)
            except Exception as e:
                logger.error(f"Failed #{hashtag}: {e}")
    else:
        logger.info("\nSkipping hashtags (requires authentication)")

    logger.info("=" * 60)
    logger.info(f"TOTAL: {len(all_events)} events found")

    return all_events


if __name__ == "__main__":
    # Check for session file
    session_file = os.getenv("INSTAGRAM_SESSION_FILE", "session.instaloader")
    username = os.getenv("INSTAGRAM_USERNAME")

    events = run_instaloader_scraper(session_file, username)

    print(f"\n{'='*60}")
    print(f"FOUND {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:15]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    Venue: {e.venue_name}")
        print(f"    Price: {e.price_info}")
        print(f"    URL: {e.source_url}")
