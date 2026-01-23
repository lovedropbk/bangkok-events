"""
Instagram scraper for Bangkok events.
Scrapes public event pages and hashtags.

Usage:
    python -m scrapers.instagram --hashtags bangkokevents bangkoknightlife
    python -m scrapers.instagram --accounts venue1 venue2
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional
import instaloader
from dataclasses import dataclass

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
    tags: list[str]
    source: str = "instagram"
    source_url: str = ""
    source_id: str = ""
    image_url: Optional[str] = None
    price_info: Optional[str] = None
    organizer_name: Optional[str] = None


class InstagramScraper:
    """Scrapes Instagram for Bangkok events"""

    # Bangkok-related hashtags to monitor
    HASHTAGS = [
        "bangkokevents",
        "bangkoknightlife",
        "bangkokparty",
        "bangkokrooftop",
        "bangkokunderground",
        "thonglornightlife",
        "ekkamainightlife",
        "bangkokpopup",
        "bangkokfoodie",
        "bangkokart",
    ]

    # Patterns for extracting event details from captions
    DATE_PATTERNS = [
        r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",  # DD/MM/YY or DD-MM-YYYY
        r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{2,4})",  # 15 Jan 2025
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{2,4})",  # Jan 15, 2025
    ]

    TIME_PATTERNS = [
        r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)",  # 7:00 PM
        r"(\d{1,2}\s*(?:AM|PM|am|pm))",  # 7PM
        r"(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})",  # 7:00-11:00
    ]

    PRICE_PATTERNS = [
        r"(\d+(?:,\d{3})*\s*(?:THB|baht|฿))",  # 500 THB
        r"(฿\s*\d+(?:,\d{3})*)",  # ฿500
        r"(free\s*entry|free\s*admission|no\s*cover)",  # Free
    ]

    LOCATION_PATTERNS = [
        r"@\s*([A-Za-z0-9\s]+(?:rooftop|bar|club|venue|hotel|restaurant))",
        r"(?:at|venue|location):\s*([^\n]+)",
    ]

    # District keywords
    DISTRICT_KEYWORDS = {
        "thonglor": "Thonglor",
        "ekkamai": "Ekkamai",
        "sukhumvit": "Sukhumvit",
        "silom": "Silom",
        "sathorn": "Sathorn",
        "siam": "Siam",
        "ari": "Ari",
        "bangna": "Bangna",
        "rca": "Ratchada",
        "ratchada": "Ratchada",
        "phrom phong": "Phrom Phong",
        "asok": "Sukhumvit",
    }

    # Category keywords
    CATEGORY_KEYWORDS = {
        "party": ["party", "dj", "club", "rave", "dance"],
        "music": ["live music", "concert", "jazz", "band", "acoustic", "vinyl"],
        "art": ["art", "exhibition", "gallery", "artist"],
        "food": ["food", "popup", "pop-up", "dining", "dinner", "brunch"],
        "wellness": ["meditation", "yoga", "wellness", "mindfulness"],
        "workshop": ["workshop", "class", "learn", "course"],
    }

    def __init__(self, rate_limit_delay: float = 2.0):
        """
        Initialize the Instagram scraper.

        Args:
            rate_limit_delay: Seconds between requests to avoid rate limiting
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
        self.rate_limit_delay = rate_limit_delay

    def scrape_hashtag(self, hashtag: str, max_posts: int = 50) -> list[ScrapedEvent]:
        """
        Scrape posts from a hashtag.

        Args:
            hashtag: The hashtag to scrape (without #)
            max_posts: Maximum number of posts to process

        Returns:
            List of ScrapedEvent objects
        """
        events = []
        try:
            logger.info(f"Scraping hashtag: #{hashtag}")
            posts = instaloader.Hashtag.from_name(self.loader.context, hashtag).get_posts()

            count = 0
            for post in posts:
                if count >= max_posts:
                    break

                event = self._parse_post(post)
                if event and self._is_valid_event(event):
                    events.append(event)
                    logger.info(f"Found event: {event.title[:50]}...")

                count += 1

        except Exception as e:
            logger.error(f"Error scraping hashtag {hashtag}: {e}")

        return events

    def scrape_profile(self, username: str, max_posts: int = 20) -> list[ScrapedEvent]:
        """
        Scrape posts from a profile.

        Args:
            username: The Instagram username
            max_posts: Maximum number of posts to process

        Returns:
            List of ScrapedEvent objects
        """
        events = []
        try:
            logger.info(f"Scraping profile: @{username}")
            profile = instaloader.Profile.from_username(self.loader.context, username)
            posts = profile.get_posts()

            count = 0
            for post in posts:
                if count >= max_posts:
                    break

                event = self._parse_post(post, default_organizer=username)
                if event and self._is_valid_event(event):
                    events.append(event)
                    logger.info(f"Found event: {event.title[:50]}...")

                count += 1

        except Exception as e:
            logger.error(f"Error scraping profile {username}: {e}")

        return events

    def _parse_post(self, post, default_organizer: Optional[str] = None) -> Optional[ScrapedEvent]:
        """Parse an Instagram post into a ScrapedEvent"""
        try:
            caption = post.caption or ""

            # Skip if caption is too short
            if len(caption) < 50:
                return None

            # Extract event details
            title = self._extract_title(caption)
            start_datetime = self._extract_datetime(caption, post.date_utc)
            venue = self._extract_venue(caption)
            district = self._extract_district(caption)
            category = self._extract_category(caption)
            tags = self._extract_tags(caption)
            price = self._extract_price(caption)

            # Skip if no date found (likely not an event)
            if not start_datetime:
                return None

            return ScrapedEvent(
                title=title,
                description=caption[:2000],  # Limit description length
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=venue,
                address=None,
                district=district,
                category=category,
                tags=tags,
                source="instagram",
                source_url=f"https://instagram.com/p/{post.shortcode}",
                source_id=f"ig_{post.shortcode}",
                image_url=post.url if post.typename == "GraphImage" else None,
                price_info=price,
                organizer_name=default_organizer or post.owner_username,
            )
        except Exception as e:
            logger.error(f"Error parsing post: {e}")
            return None

    def _extract_title(self, caption: str) -> str:
        """Extract event title from caption"""
        # Try to get first line as title
        lines = caption.strip().split('\n')
        first_line = lines[0].strip()

        # Clean up hashtags and mentions from title
        title = re.sub(r'[#@]\w+', '', first_line).strip()

        # Limit title length
        if len(title) > 100:
            title = title[:97] + "..."

        return title or "Untitled Event"

    def _extract_datetime(self, caption: str, post_date: datetime) -> Optional[datetime]:
        """Extract event datetime from caption"""
        caption_lower = caption.lower()

        # Look for date patterns
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, caption, re.IGNORECASE)
            if match:
                try:
                    from dateutil.parser import parse
                    date_str = match.group(1)
                    parsed_date = parse(date_str, dayfirst=True)

                    # Look for time
                    for time_pattern in self.TIME_PATTERNS:
                        time_match = re.search(time_pattern, caption, re.IGNORECASE)
                        if time_match:
                            time_str = time_match.group(1)
                            parsed_time = parse(time_str)
                            parsed_date = parsed_date.replace(
                                hour=parsed_time.hour,
                                minute=parsed_time.minute
                            )
                            break

                    return parsed_date
                except Exception:
                    pass

        # Check for relative dates like "this Saturday", "tomorrow"
        if "tonight" in caption_lower or "today" in caption_lower:
            return post_date
        elif "tomorrow" in caption_lower:
            return post_date + timedelta(days=1)
        elif "this saturday" in caption_lower:
            days_until = (5 - post_date.weekday()) % 7
            return post_date + timedelta(days=days_until)
        elif "this friday" in caption_lower:
            days_until = (4 - post_date.weekday()) % 7
            return post_date + timedelta(days=days_until)

        return None

    def _extract_venue(self, caption: str) -> Optional[str]:
        """Extract venue name from caption"""
        for pattern in self.LOCATION_PATTERNS:
            match = re.search(pattern, caption, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        return None

    def _extract_district(self, caption: str) -> Optional[str]:
        """Extract district from caption"""
        caption_lower = caption.lower()
        for keyword, district in self.DISTRICT_KEYWORDS.items():
            if keyword in caption_lower:
                return district
        return None

    def _extract_category(self, caption: str) -> Optional[str]:
        """Extract category from caption"""
        caption_lower = caption.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in caption_lower:
                    return category
        return None

    def _extract_tags(self, caption: str) -> list[str]:
        """Extract hashtags as tags"""
        hashtags = re.findall(r'#(\w+)', caption)
        # Filter out generic/spam hashtags and limit count
        filtered = [
            tag.lower() for tag in hashtags
            if len(tag) > 2 and len(tag) < 30 and tag.lower() not in [
                "instagram", "instagood", "love", "follow", "like",
                "bangkok", "thailand", "thai"
            ]
        ]
        return filtered[:10]

    def _extract_price(self, caption: str) -> Optional[str]:
        """Extract price info from caption"""
        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, caption, re.IGNORECASE)
            if match:
                price = match.group(1).strip()
                if "free" in price.lower():
                    return "Free"
                return price
        return None

    def _is_valid_event(self, event: ScrapedEvent) -> bool:
        """Check if the scraped event is valid"""
        # Must have a title
        if not event.title or event.title == "Untitled Event":
            return False

        # Must have a date in the future
        if event.start_datetime:
            if event.start_datetime < datetime.now() - timedelta(days=1):
                return False

        return True


def main():
    """Main entry point for the scraper"""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Instagram for Bangkok events")
    parser.add_argument("--hashtags", nargs="+", help="Hashtags to scrape")
    parser.add_argument("--accounts", nargs="+", help="Accounts to scrape")
    parser.add_argument("--max-posts", type=int, default=50, help="Max posts per source")
    args = parser.parse_args()

    scraper = InstagramScraper()

    all_events = []

    if args.hashtags:
        for hashtag in args.hashtags:
            events = scraper.scrape_hashtag(hashtag, args.max_posts)
            all_events.extend(events)
    else:
        # Default hashtags
        for hashtag in InstagramScraper.HASHTAGS[:3]:  # Limit for demo
            events = scraper.scrape_hashtag(hashtag, args.max_posts)
            all_events.extend(events)

    if args.accounts:
        for account in args.accounts:
            events = scraper.scrape_profile(account, args.max_posts)
            all_events.extend(events)

    logger.info(f"Total events found: {len(all_events)}")

    for event in all_events:
        print(f"\n{'='*60}")
        print(f"Title: {event.title}")
        print(f"Date: {event.start_datetime}")
        print(f"Venue: {event.venue_name}")
        print(f"District: {event.district}")
        print(f"Category: {event.category}")
        print(f"Price: {event.price_info}")
        print(f"Tags: {', '.join(event.tags[:5])}")
        print(f"URL: {event.source_url}")


if __name__ == "__main__":
    main()
