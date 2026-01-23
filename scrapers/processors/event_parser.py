"""
Event parser and processor.
Parses raw scraped data and prepares events for database insertion.
"""

import re
import logging
import hashlib
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProcessedEvent:
    """A processed event ready for database insertion"""
    title: str
    description: Optional[str]
    start_datetime: datetime
    end_datetime: Optional[datetime]
    venue_name: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    district: Optional[str]
    category: Optional[str]
    tags: list[str]
    source: str
    source_url: str
    source_id: str
    image_url: Optional[str]
    price_info: Optional[str]
    organizer_name: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


class EventProcessor:
    """Processes and validates scraped events"""

    # Bangkok districts with approximate center coordinates
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
        "Ratchathewi": (13.7580, 100.5350),
        "Ari": (13.7850, 100.5450),
    }

    def __init__(self):
        self.processed_ids = set()

    def process(self, raw_event: dict) -> Optional[ProcessedEvent]:
        """
        Process a raw scraped event.

        Args:
            raw_event: Raw event data from scraper

        Returns:
            ProcessedEvent or None if invalid
        """
        try:
            # Validate required fields
            title = self._clean_text(raw_event.get("title", ""))
            if not title or len(title) < 3:
                logger.debug(f"Skipping event with invalid title: {title}")
                return None

            start_datetime = raw_event.get("start_datetime")
            if not start_datetime:
                logger.debug(f"Skipping event without date: {title}")
                return None

            # Ensure datetime is a datetime object
            if isinstance(start_datetime, str):
                try:
                    from dateutil.parser import parse
                    start_datetime = parse(start_datetime)
                except Exception:
                    logger.debug(f"Skipping event with invalid date: {title}")
                    return None

            # Skip past events
            if start_datetime < datetime.now():
                logger.debug(f"Skipping past event: {title}")
                return None

            # Generate source ID for deduplication
            source = raw_event.get("source", "unknown")
            source_id = raw_event.get("source_id")
            if not source_id:
                # Generate from URL or title
                source_url = raw_event.get("source_url", "")
                source_id = self._generate_source_id(source, source_url, title)

            # Check for duplicates
            if source_id in self.processed_ids:
                logger.debug(f"Skipping duplicate: {title}")
                return None
            self.processed_ids.add(source_id)

            # Process description
            description = self._clean_text(raw_event.get("description", ""))
            if len(description) > 2000:
                description = description[:1997] + "..."

            # Process end datetime
            end_datetime = raw_event.get("end_datetime")
            if isinstance(end_datetime, str):
                try:
                    from dateutil.parser import parse
                    end_datetime = parse(end_datetime)
                except Exception:
                    end_datetime = None

            # Get or estimate location
            latitude = raw_event.get("latitude")
            longitude = raw_event.get("longitude")
            district = raw_event.get("district")

            # If no coordinates but have district, use district center
            if (latitude is None or longitude is None) and district:
                if district in self.DISTRICT_COORDS:
                    latitude, longitude = self.DISTRICT_COORDS[district]

            # Try to detect district from venue/address if not set
            if not district:
                venue_name = raw_event.get("venue_name", "")
                address = raw_event.get("address", "")
                district = self._detect_district(f"{title} {venue_name} {address}")

                # Get coordinates for detected district
                if district and (latitude is None or longitude is None):
                    if district in self.DISTRICT_COORDS:
                        latitude, longitude = self.DISTRICT_COORDS[district]

            # Process tags
            tags = raw_event.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            tags = [t.lower().strip() for t in tags if t and len(t) > 1][:10]

            # Clean and validate other fields
            venue_name = self._clean_text(raw_event.get("venue_name", ""))[:255] if raw_event.get("venue_name") else None
            address = self._clean_text(raw_event.get("address", ""))[:500] if raw_event.get("address") else None
            category = raw_event.get("category", "")[:50] if raw_event.get("category") else None
            source_url = raw_event.get("source_url", "")[:2000] if raw_event.get("source_url") else ""
            image_url = raw_event.get("image_url", "")[:2000] if raw_event.get("image_url") else None
            price_info = raw_event.get("price_info", "")[:100] if raw_event.get("price_info") else None
            organizer_name = raw_event.get("organizer_name", "")[:255] if raw_event.get("organizer_name") else None

            return ProcessedEvent(
                title=title[:255],
                description=description,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                venue_name=venue_name,
                address=address,
                latitude=latitude,
                longitude=longitude,
                district=district,
                category=category,
                tags=tags,
                source=source[:50],
                source_url=source_url,
                source_id=source_id[:255],
                image_url=image_url,
                price_info=price_info,
                organizer_name=organizer_name,
            )

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        return text.strip()

    def _generate_source_id(self, source: str, url: str, title: str) -> str:
        """Generate a unique source ID for deduplication"""
        content = f"{source}:{url}:{title}"
        hash_val = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"{source}_{hash_val}"

    def _detect_district(self, text: str) -> Optional[str]:
        """Detect Bangkok district from text"""
        text_lower = text.lower()
        district_keywords = {
            "thonglor": "Thonglor",
            "thong lo": "Thonglor",
            "ekkamai": "Ekkamai",
            "ekamai": "Ekkamai",
            "sukhumvit": "Sukhumvit",
            "phrom phong": "Phrom Phong",
            "prompong": "Phrom Phong",
            "silom": "Silom",
            "sathorn": "Sathorn",
            "siam": "Siam",
            "bangna": "Bangna",
            "bang na": "Bangna",
            "ratchathewi": "Ratchathewi",
            "ari": "Ari",
            "asok": "Sukhumvit",
            "nana": "Sukhumvit",
        }
        for keyword, district in district_keywords.items():
            if keyword in text_lower:
                return district
        return None
