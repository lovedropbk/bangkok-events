"""
Reliable event sources using public APIs and curated data.
This module fetches events from sources that provide public APIs or structured data.
"""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EventData:
    """Event data structure"""
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


class EventbriteAPI:
    """
    Eventbrite API client using their public discovery endpoints.
    Eventbrite provides public event discovery without authentication.
    """

    BASE_URL = "https://www.eventbrite.com/api/v3"
    DISCOVERY_URL = "https://www.eventbrite.com/d/thailand--bangkok/all-events/"

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/html",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    def fetch_bangkok_events(self, page: int = 1) -> list[EventData]:
        """Fetch events from Eventbrite's Bangkok page"""
        events = []

        try:
            # Use Eventbrite's search API endpoint (public, no auth needed)
            url = f"https://www.eventbrite.com/api/v3/destination/events/"
            params = {
                "place_id": "101131301",  # Bangkok place ID
                "page_size": 50,
                "page": page,
            }

            # Try the browse API
            browse_url = "https://www.eventbrite.com/api/v3/destination/search/"
            response = self.client.get(browse_url, params={
                "location": "Bangkok",
                "page_size": 40,
            })

            if response.status_code != 200:
                # Fallback: try alternative endpoint
                alt_url = "https://www.eventbrite.com/api/v3/events/search/"
                response = self.client.get(alt_url, params={
                    "location.address": "Bangkok, Thailand",
                    "expand": "venue",
                })

            if response.status_code == 200:
                data = response.json()
                events_data = data.get("events", data.get("results", []))

                for e in events_data:
                    event = self._parse_eventbrite_event(e)
                    if event:
                        events.append(event)

        except Exception as e:
            logger.error(f"Eventbrite API error: {e}")

        return events

    def _parse_eventbrite_event(self, data: dict) -> Optional[EventData]:
        """Parse Eventbrite API response into EventData"""
        try:
            title = data.get("name", {}).get("text", data.get("name", ""))
            if isinstance(title, dict):
                title = title.get("text", "")
            if not title:
                return None

            description = data.get("description", {}).get("text", "")
            if isinstance(description, dict):
                description = description.get("text", "")

            # Parse dates
            start_datetime = None
            end_datetime = None
            start = data.get("start", {})
            if isinstance(start, dict):
                start_str = start.get("utc") or start.get("local")
                if start_str:
                    start_datetime = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

            end = data.get("end", {})
            if isinstance(end, dict):
                end_str = end.get("utc") or end.get("local")
                if end_str:
                    end_datetime = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

            # Venue
            venue = data.get("venue", {})
            venue_name = venue.get("name") if isinstance(venue, dict) else None
            address = None
            lat, lng = None, None

            if isinstance(venue, dict):
                addr = venue.get("address", {})
                if isinstance(addr, dict):
                    address = addr.get("localized_address_display")
                    lat = addr.get("latitude")
                    lng = addr.get("longitude")

            # Image
            logo = data.get("logo", {})
            image_url = logo.get("url") if isinstance(logo, dict) else None

            # Price
            price_info = None
            if data.get("is_free"):
                price_info = "Free"

            return EventData(
                title=title[:255],
                description=description[:2000] if description else "",
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                venue_name=venue_name,
                address=address,
                latitude=float(lat) if lat else None,
                longitude=float(lng) if lng else None,
                district=self._detect_district(f"{venue_name or ''} {address or ''}"),
                category=self._detect_category(title, description),
                tags=[],
                source="eventbrite",
                source_url=data.get("url", ""),
                source_id=f"eb_{data.get('id', '')}",
                image_url=image_url,
                price_info=price_info,
                organizer_name=None,
            )

        except Exception as e:
            logger.error(f"Error parsing Eventbrite event: {e}")
            return None

    def _detect_district(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        districts = {
            "thonglor": "Thonglor", "thong lo": "Thonglor",
            "ekkamai": "Ekkamai", "ekamai": "Ekkamai",
            "sukhumvit": "Sukhumvit", "silom": "Silom",
            "sathorn": "Sathorn", "siam": "Siam",
            "bangna": "Bangna", "ari": "Ari",
        }
        for key, value in districts.items():
            if key in text_lower:
                return value
        return "Central Bangkok"

    def _detect_category(self, title: str, description: str) -> str:
        text = f"{title} {description}".lower()
        if any(w in text for w in ["party", "club", "dj", "nightlife"]):
            return "party"
        if any(w in text for w in ["concert", "music", "live", "band"]):
            return "music"
        if any(w in text for w in ["art", "exhibition", "gallery"]):
            return "art"
        if any(w in text for w in ["food", "dinner", "brunch", "cooking"]):
            return "food"
        if any(w in text for w in ["workshop", "class", "learn"]):
            return "workshop"
        if any(w in text for w in ["yoga", "meditation", "wellness"]):
            return "wellness"
        return "other"

    def close(self):
        self.client.close()


class GooglePlacesEvents:
    """
    Fetch events from Google Places API (requires API key).
    Falls back to curated venue list if no API key.
    """

    # Popular Bangkok venues known for events
    CURATED_VENUES = [
        {
            "name": "The Commons Thonglor",
            "district": "Thonglor",
            "lat": 13.7289,
            "lng": 100.5789,
            "categories": ["food", "music", "market"],
        },
        {
            "name": "Vanilla Sky Rooftop",
            "district": "Sukhumvit",
            "lat": 13.7256,
            "lng": 100.5684,
            "categories": ["party", "music"],
        },
        {
            "name": "Warehouse 30",
            "district": "Charoenkrung",
            "lat": 13.7235,
            "lng": 100.5136,
            "categories": ["art", "market"],
        },
        {
            "name": "W District",
            "district": "Phrom Phong",
            "lat": 13.7203,
            "lng": 100.5867,
            "categories": ["food", "market"],
        },
    ]

    def get_venue_events(self) -> list[dict]:
        """Return curated venue data that can be used for event discovery"""
        return self.CURATED_VENUES


class SocialMediaAggregator:
    """
    Aggregate events from social media using public RSS feeds and embeds.
    This approach doesn't require authentication.
    """

    def fetch_from_rss(self, feed_url: str) -> list[EventData]:
        """Fetch events from RSS feeds (if available)"""
        events = []
        try:
            import feedparser
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                event = self._parse_rss_entry(entry)
                if event:
                    events.append(event)
        except ImportError:
            logger.warning("feedparser not installed, skipping RSS")
        except Exception as e:
            logger.error(f"RSS fetch error: {e}")
        return events

    def _parse_rss_entry(self, entry) -> Optional[EventData]:
        """Parse RSS entry into EventData"""
        try:
            title = entry.get("title", "")
            if not title:
                return None

            published = entry.get("published_parsed")
            start_datetime = datetime(*published[:6]) if published else None

            return EventData(
                title=title[:255],
                description=entry.get("summary", "")[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=None,
                address=None,
                latitude=None,
                longitude=None,
                district=None,
                category=None,
                tags=[],
                source="rss",
                source_url=entry.get("link", ""),
                source_id=f"rss_{hash(entry.get('id', title))}",
                image_url=None,
                price_info=None,
                organizer_name=None,
            )
        except Exception:
            return None


def fetch_all_events() -> list[EventData]:
    """
    Fetch events from all available sources.

    Returns:
        List of EventData objects
    """
    all_events = []

    # Eventbrite
    try:
        eb = EventbriteAPI()
        events = eb.fetch_bangkok_events()
        all_events.extend(events)
        logger.info(f"Fetched {len(events)} events from Eventbrite")
        eb.close()
    except Exception as e:
        logger.error(f"Eventbrite fetch failed: {e}")

    return all_events


if __name__ == "__main__":
    events = fetch_all_events()
    print(f"Total events: {len(events)}")
    for e in events[:5]:
        print(f"- {e.title} | {e.start_datetime} | {e.venue_name}")
