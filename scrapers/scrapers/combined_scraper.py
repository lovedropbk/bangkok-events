"""
Combined event scraper that uses all available methods.
This is the main entry point for populating the database with events.

Available Methods:
1. Eventbrite API - Works well for public events
2. Manual curation - Via the web app's submit form
3. Apify Integration - For Instagram/Facebook (requires free Apify account)
4. Google Calendar - For venue event calendars
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass, asdict
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
    "Central Bangkok": (13.7563, 100.5018),
}


class EventbriteScraper:
    """
    Eventbrite scraper using their public search.
    Eventbrite has relaxed scraping policies for public events.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html",
    }

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS, timeout=30.0, follow_redirects=True)

    def close(self):
        self.client.close()

    def scrape_bangkok_events(self, max_pages: int = 3) -> List[ScrapedEvent]:
        """Scrape Eventbrite for Bangkok events"""
        events = []

        # Categories to search
        searches = [
            ("bangkok nightlife", "party"),
            ("bangkok music", "music"),
            ("bangkok art exhibition", "art"),
            ("bangkok food popup", "food"),
            ("bangkok workshop", "workshop"),
        ]

        for query, default_category in searches:
            try:
                page_events = self._search_events(query, default_category)
                events.extend(page_events)
                logger.info(f"Eventbrite '{query}': {len(page_events)} events")
            except Exception as e:
                logger.error(f"Eventbrite search error: {e}")

        return events

    def _search_events(self, query: str, default_category: str) -> List[ScrapedEvent]:
        """Search Eventbrite for events"""
        events = []

        try:
            # Try the API endpoint
            url = "https://www.eventbrite.com/api/v3/destination/search/"
            resp = self.client.get(url, params={
                "q": query,
                "page_size": 20,
            })

            if resp.status_code == 200:
                data = resp.json()
                for event_data in data.get("events", []):
                    event = self._parse_event(event_data, default_category)
                    if event:
                        events.append(event)
        except Exception as e:
            logger.debug(f"API error, trying HTML: {e}")

            # Fallback: scrape HTML
            try:
                url = f"https://www.eventbrite.com/d/thailand--bangkok/{query.replace(' ', '-')}/"
                resp = self.client.get(url)
                if resp.status_code == 200:
                    events.extend(self._parse_html(resp.text, default_category))
            except Exception as e2:
                logger.error(f"HTML scrape error: {e2}")

        return events

    def _parse_event(self, data: dict, default_category: str) -> Optional[ScrapedEvent]:
        """Parse Eventbrite API event data"""
        try:
            name = data.get("name", {})
            title = name.get("text", name) if isinstance(name, dict) else str(name)
            if not title:
                return None

            desc = data.get("description", {})
            description = desc.get("text", "") if isinstance(desc, dict) else str(desc or "")

            # Dates
            start = data.get("start", {})
            start_datetime = None
            if isinstance(start, dict) and start.get("utc"):
                try:
                    start_datetime = datetime.fromisoformat(start["utc"].replace("Z", "+00:00"))
                except:
                    pass

            # Skip past events
            if start_datetime and start_datetime < datetime.now():
                return None

            # Location
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

            district = self._detect_district(f"{title} {venue_name or ''} {address or ''}")

            # Get coords from district if not available
            if not lat and district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            # Image
            logo = data.get("logo", {})
            image_url = logo.get("url") if isinstance(logo, dict) else None

            # Price
            price_info = "Free" if data.get("is_free") else None

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
                category=self._detect_category(f"{title} {description}") or default_category,
                tags=[],
                source="eventbrite",
                source_url=data.get("url", ""),
                source_id=f"eb_{data.get('id', '')}",
                image_url=image_url,
                price_info=price_info,
                organizer_name=None,
            )
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _parse_html(self, html: str, default_category: str) -> List[ScrapedEvent]:
        """Parse Eventbrite HTML for events"""
        events = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            # Find event cards
            cards = soup.select('[data-testid="event-card"]') or soup.select('.search-event-card')

            for card in cards[:20]:
                try:
                    # Title
                    title_el = card.select_one('h3') or card.select_one('[data-testid="event-card-title"]')
                    title = title_el.text.strip() if title_el else None
                    if not title:
                        continue

                    # Link
                    link_el = card.select_one('a[href*="eventbrite.com/e/"]')
                    url = link_el.get('href', '') if link_el else ''

                    # Image
                    img_el = card.select_one('img')
                    image_url = img_el.get('src') or img_el.get('data-src') if img_el else None

                    # Generate ID from URL
                    id_match = re.search(r'/e/([^?]+)', url)
                    source_id = f"eb_{id_match.group(1)}" if id_match else f"eb_{hash(url) % 10**10}"

                    events.append(ScrapedEvent(
                        title=title[:255],
                        description="",
                        start_datetime=None,  # Would need to fetch full page
                        end_datetime=None,
                        venue_name=None,
                        address=None,
                        latitude=None,
                        longitude=None,
                        district=self._detect_district(title),
                        category=default_category,
                        tags=[],
                        source="eventbrite",
                        source_url=url,
                        source_id=source_id,
                        image_url=image_url,
                        price_info=None,
                        organizer_name=None,
                    ))
                except Exception as e:
                    logger.debug(f"Card parse error: {e}")

        except Exception as e:
            logger.error(f"HTML parse error: {e}")

        return events

    def _detect_district(self, text: str) -> Optional[str]:
        if not text:
            return None
        text_lower = text.lower()
        districts = {
            'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai',
            'sukhumvit': 'Sukhumvit', 'silom': 'Silom',
            'sathorn': 'Sathorn', 'siam': 'Siam',
            'bangna': 'Bangna', 'ari': 'Ari',
            'rca': 'RCA', 'ratchada': 'RCA',
        }
        for k, v in districts.items():
            if k in text_lower:
                return v
        return "Central Bangkok"

    def _detect_category(self, text: str) -> Optional[str]:
        if not text:
            return None
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj', 'nightlife']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live', 'band']):
            return 'music'
        if any(w in text_lower for w in ['art', 'exhibition', 'gallery']):
            return 'art'
        if any(w in text_lower for w in ['food', 'dinner', 'brunch', 'popup']):
            return 'food'
        if any(w in text_lower for w in ['workshop', 'class', 'learn']):
            return 'workshop'
        return None


class ApifyIntegration:
    """
    Integration with Apify for Instagram and Facebook scraping.

    Apify offers a free tier with 5 actor runs per month.
    This is the most reliable way to scrape IG/FB.

    Setup:
    1. Create free account at https://apify.com
    2. Get your API token from Settings
    3. Set APIFY_TOKEN environment variable
    """

    APIFY_URL = "https://api.apify.com/v2"

    # Apify actor IDs for Instagram and Facebook
    INSTAGRAM_ACTOR = "apify/instagram-hashtag-scraper"
    FACEBOOK_ACTOR = "apify/facebook-events-scraper"

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("APIFY_TOKEN")
        if self.api_token:
            self.client = httpx.Client(
                headers={"Authorization": f"Bearer {self.api_token}"},
                timeout=120.0
            )
        else:
            self.client = None
            logger.warning("No APIFY_TOKEN - Apify integration disabled")

    def close(self):
        if self.client:
            self.client.close()

    def is_available(self) -> bool:
        return self.client is not None

    def scrape_instagram_hashtag(self, hashtag: str, max_posts: int = 30) -> List[ScrapedEvent]:
        """Scrape Instagram hashtag using Apify"""
        if not self.is_available():
            return []

        events = []
        logger.info(f"Apify: Scraping Instagram #{hashtag}...")

        try:
            # Run the actor
            run_url = f"{self.APIFY_URL}/acts/{self.INSTAGRAM_ACTOR}/runs"
            resp = self.client.post(run_url, json={
                "hashtags": [hashtag],
                "resultsLimit": max_posts,
            })

            if resp.status_code != 201:
                logger.error(f"Apify run failed: {resp.status_code}")
                return events

            run_id = resp.json().get("data", {}).get("id")
            if not run_id:
                return events

            # Wait for results
            import time
            for _ in range(60):  # Max 60 seconds
                status_url = f"{self.APIFY_URL}/actor-runs/{run_id}"
                status_resp = self.client.get(status_url)
                status = status_resp.json().get("data", {}).get("status")

                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED"]:
                    logger.error(f"Apify run {status}")
                    return events

                time.sleep(2)

            # Get results
            results_url = f"{self.APIFY_URL}/actor-runs/{run_id}/dataset/items"
            results_resp = self.client.get(results_url)
            results = results_resp.json()

            for item in results:
                event = self._parse_instagram_result(item)
                if event:
                    events.append(event)

        except Exception as e:
            logger.error(f"Apify Instagram error: {e}")

        return events

    def _parse_instagram_result(self, item: dict) -> Optional[ScrapedEvent]:
        """Parse Apify Instagram result"""
        try:
            caption = item.get("caption", "")
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

            # Datetime
            start_datetime = self._extract_datetime(caption)
            if not start_datetime:
                return None

            district = self._detect_district(caption)
            lat, lng = None, None
            if district and district in DISTRICT_COORDS:
                lat, lng = DISTRICT_COORDS[district]

            return ScrapedEvent(
                title=title or "Bangkok Event",
                description=caption[:2000],
                start_datetime=start_datetime,
                end_datetime=None,
                venue_name=self._extract_venue(caption),
                address=None,
                latitude=lat,
                longitude=lng,
                district=district,
                category=self._detect_category(caption),
                tags=re.findall(r'#(\w+)', caption)[:10],
                source="instagram",
                source_url=item.get("url", ""),
                source_id=f"ig_{item.get('id', item.get('shortCode', ''))}",
                image_url=item.get("displayUrl"),
                price_info=self._extract_price(caption),
                organizer_name=item.get("ownerUsername"),
            )
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _looks_like_event(self, text: str) -> bool:
        if not text or len(text) < 50:
            return False
        text_lower = text.lower()
        locations = ['bangkok', 'bkk', 'thonglor', 'ekkamai', 'sukhumvit']
        events = ['party', 'event', 'tonight', 'dj', 'live', 'tickets', 'rave']
        return any(l in text_lower for l in locations) and any(e in text_lower for e in events)

    def _extract_datetime(self, text: str) -> Optional[datetime]:
        text_lower = text.lower()
        now = datetime.now()
        if 'tonight' in text_lower:
            return now.replace(hour=21, minute=0)
        if 'tomorrow' in text_lower:
            return (now + timedelta(days=1)).replace(hour=21, minute=0)
        match = re.search(r'(\d{1,2})[\/\-](\d{1,2})', text_lower)
        if match:
            try:
                from dateutil.parser import parse
                return parse(match.group(0), dayfirst=True).replace(hour=21, minute=0)
            except:
                pass
        return None

    def _extract_venue(self, text: str) -> Optional[str]:
        m = re.search(r'(?:at|@|venue)\s*[:\s]+([A-Za-z0-9\s\-\']+?)(?:\n|,|\.|\#|$)', text, re.I)
        if m:
            v = m.group(1).strip()
            if 5 < len(v) < 60:
                return v
        return None

    def _detect_district(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for k, v in {'thonglor': 'Thonglor', 'ekkamai': 'Ekkamai', 'sukhumvit': 'Sukhumvit',
                     'silom': 'Silom', 'siam': 'Siam', 'rca': 'RCA'}.items():
            if k in text_lower:
                return v
        return None

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ['party', 'club', 'dj', 'rave']):
            return 'party'
        if any(w in text_lower for w in ['music', 'concert', 'live']):
            return 'music'
        return 'party'

    def _extract_price(self, text: str) -> Optional[str]:
        if 'free' in text.lower():
            return 'Free'
        m = re.search(r'(\d+)\s*(THB|baht)', text, re.I)
        return f"{m.group(1)} THB" if m else None


def run_all_scrapers() -> List[ScrapedEvent]:
    """
    Run all available scrapers and return combined events.
    """
    all_events = []
    seen_ids = set()

    # 1. Eventbrite (always available)
    logger.info("=" * 60)
    logger.info("EVENTBRITE SCRAPER")
    try:
        eb = EventbriteScraper()
        events = eb.scrape_bangkok_events()
        for e in events:
            if e.source_id not in seen_ids:
                seen_ids.add(e.source_id)
                all_events.append(e)
        logger.info(f"Eventbrite: {len(events)} events")
        eb.close()
    except Exception as e:
        logger.error(f"Eventbrite failed: {e}")

    # 2. Apify Instagram/Facebook (if token available)
    apify_token = os.getenv("APIFY_TOKEN")
    if apify_token:
        logger.info("=" * 60)
        logger.info("APIFY INSTAGRAM SCRAPER")
        try:
            apify = ApifyIntegration(apify_token)

            # Scrape key hashtags
            for hashtag in ["bangkokparty", "bangkokunderground", "thonglornightlife"]:
                events = apify.scrape_instagram_hashtag(hashtag, max_posts=20)
                for e in events:
                    if e.source_id not in seen_ids:
                        seen_ids.add(e.source_id)
                        all_events.append(e)

            apify.close()
        except Exception as e:
            logger.error(f"Apify failed: {e}")
    else:
        logger.info("=" * 60)
        logger.info("Apify disabled - set APIFY_TOKEN for Instagram/Facebook scraping")
        logger.info("Get free token at: https://apify.com")

    logger.info("=" * 60)
    logger.info(f"TOTAL: {len(all_events)} events")

    return all_events


if __name__ == "__main__":
    events = run_all_scrapers()

    print(f"\n{'='*60}")
    print(f"SCRAPED {len(events)} EVENTS")
    print('='*60)

    for i, e in enumerate(events[:15]):
        print(f"\n[{i+1}] {e.title}")
        print(f"    Date: {e.start_datetime}")
        print(f"    District: {e.district} | Category: {e.category}")
        print(f"    Source: {e.source}")
        print(f"    Image: {'Yes' if e.image_url else 'No'}")
