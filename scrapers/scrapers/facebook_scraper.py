"""
Facebook Event Scraper - Scrapes Bangkok events from Facebook.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from playwright.async_api import async_playwright


@dataclass
class ScrapedEvent:
    title: str
    description: str
    start_datetime: datetime
    end_datetime: datetime
    venue_name: str
    address: str
    latitude: float
    longitude: float
    district: str
    category: str
    tags: list
    source: str
    source_url: str
    source_id: str
    image_url: str
    price_info: str
    organizer_name: str


DISTRICT_COORDS = {
    "Thonglor": (13.7307, 100.5844),
    "Ekkamai": (13.7234, 100.5874),
    "Sukhumvit": (13.7400, 100.5600),
    "Silom": (13.7260, 100.5230),
    "Siam": (13.7453, 100.5318),
    "RCA": (13.7567, 100.5623),
    "Central Bangkok": (13.7563, 100.5018),
}


def detect_district(text):
    if not text:
        return "Central Bangkok"
    text_lower = text.lower()
    districts = {
        "thonglor": "Thonglor",
        "ekkamai": "Ekkamai",
        "sukhumvit": "Sukhumvit",
        "silom": "Silom",
        "siam": "Siam",
        "rca": "RCA",
    }
    for k, v in districts.items():
        if k in text_lower:
            return v
    return "Central Bangkok"


def detect_category(text):
    if not text:
        return "party"
    text_lower = text.lower()
    if any(w in text_lower for w in ["party", "club", "dj", "rave"]):
        return "party"
    if any(w in text_lower for w in ["music", "concert", "live"]):
        return "music"
    if any(w in text_lower for w in ["art", "exhibition"]):
        return "art"
    if any(w in text_lower for w in ["food", "dinner"]):
        return "food"
    return "party"


async def scrape_facebook_events():
    profile_dir = Path(__file__).parent / "fb_profile"

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=True,
            viewport={"width": 1280, "height": 900},
        )

        page = context.pages[0] if context.pages else await context.new_page()

        all_events = []
        seen_ids = set()
        searches = ["bangkok party", "bangkok nightlife", "bangkok event", "bangkok music"]

        for query in searches:
            print(f"Searching: {query}")
            url = f"https://www.facebook.com/search/events/?q={query.replace(' ', '%20')}"
            await page.goto(url, timeout=30000)
            await asyncio.sleep(3)

            # Scroll to load more
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            content = await page.content()
            event_ids = list(set(re.findall(r"/events/(\d+)", content)))
            print(f"  Found {len(event_ids)} event links")

            for eid in event_ids[:10]:
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)

                try:
                    await page.goto(f"https://www.facebook.com/events/{eid}/", timeout=20000)
                    await asyncio.sleep(2)

                    html = await page.content()

                    # Title
                    title = None
                    title_match = re.search(r'property="og:title" content="([^"]+)"', html)
                    if title_match:
                        title = title_match.group(1)

                    if not title:
                        t_match = re.search(r"<title>([^<]+)</title>", html)
                        if t_match:
                            title = t_match.group(1).split("|")[0].strip()

                    if not title:
                        print(f"    {eid}: No title")
                        continue

                    # Description
                    desc = ""
                    desc_match = re.search(r'property="og:description" content="([^"]+)"', html)
                    if desc_match:
                        desc = desc_match.group(1)
                        desc = desc.replace("&amp;", "&").replace("&#x27;", "'")

                    # Image
                    img = None
                    img_match = re.search(r'property="og:image" content="([^"]+)"', html)
                    if img_match:
                        img = img_match.group(1)

                    # DateTime
                    dt = None
                    ts_match = re.search(r'"start_timestamp":(\d+)', html)
                    if ts_match:
                        try:
                            dt = datetime.fromtimestamp(int(ts_match.group(1)))
                        except:
                            pass

                    if not dt:
                        iso_match = re.search(r'"startDate":"([^"]+)"', html)
                        if iso_match:
                            try:
                                dt = datetime.fromisoformat(
                                    iso_match.group(1).replace("Z", "+00:00")
                                ).replace(tzinfo=None)
                            except:
                                pass

                    if not dt:
                        # Default to upcoming weekend
                        now = datetime.now()
                        days = (5 - now.weekday()) % 7
                        if days == 0:
                            days = 7
                        dt = (now + timedelta(days=days)).replace(
                            hour=21, minute=0, second=0, microsecond=0
                        )

                    # Skip old events
                    if dt < datetime.now() - timedelta(days=7):
                        continue

                    district = detect_district(f"{title} {desc}")
                    lat, lng = DISTRICT_COORDS.get(district, (13.7563, 100.5018))

                    event = ScrapedEvent(
                        title=title[:255],
                        description=desc[:2000] if desc else None,
                        start_datetime=dt,
                        end_datetime=None,
                        venue_name=None,
                        address=None,
                        latitude=lat,
                        longitude=lng,
                        district=district,
                        category=detect_category(f"{title} {desc}"),
                        tags=[],
                        source="facebook",
                        source_url=f"https://www.facebook.com/events/{eid}/",
                        source_id=f"fb_{eid}",
                        image_url=img,
                        price_info=None,
                        organizer_name=None,
                    )
                    all_events.append(event)
                    print(f"    + {title[:50]}")

                except Exception as e:
                    print(f"    {eid}: Error - {str(e)[:40]}")

            await asyncio.sleep(1)

        await context.close()
        return all_events


def save_events(events, filename="scraped_events.json"):
    """Save events to JSON file"""
    data = []
    for e in events:
        d = asdict(e)
        if d["start_datetime"]:
            d["start_datetime"] = d["start_datetime"].isoformat()
        if d["end_datetime"]:
            d["end_datetime"] = d["end_datetime"].isoformat()
        data.append(d)

    Path(filename).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return len(data)


if __name__ == "__main__":
    print("=" * 60)
    print("FACEBOOK EVENT SCRAPER")
    print("=" * 60)

    events = asyncio.run(scrape_facebook_events())
    print(f"\nTotal events: {len(events)}")

    count = save_events(events)
    print(f"Saved {count} events to scraped_events.json")

    if events:
        print("\nSample events:")
        for e in events[:5]:
            print(f"  - {e.title[:50]}")
            print(f"    Date: {e.start_datetime}")
            print(f"    District: {e.district}")
