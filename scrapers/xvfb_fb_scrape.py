"""
Facebook scraper for GitHub Actions with Xvfb virtual display.
Uses non-headless mode with stealth to avoid detection.
"""

import asyncio
import json
import re
import random
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright


async def human_delay(min_sec=1, max_sec=3):
    """Random delay to mimic human behavior"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def scrape_facebook():
    session_file = Path("facebook_session.json")
    if not session_file.exists():
        print("ERROR: No facebook_session.json found")
        return []

    session = json.loads(session_file.read_text())

    async with async_playwright() as p:
        # Non-headless mode - will use Xvfb virtual display
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-size=1920,1080',
                '--start-maximized',
            ]
        )

        context = await browser.new_context(
            storage_state=session,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='Asia/Bangkok',
        )

        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        all_events = []
        seen_ids = set()

        searches = [
            "bangkok party",
            "bangkok nightlife",
            "bangkok event",
            "bangkok music",
            "bangkok club"
        ]

        for query in searches:
            print(f"\nSearching: {query}")
            try:
                url = f"https://www.facebook.com/search/events/?q={query.replace(' ', '%20')}"
                await page.goto(url, timeout=30000, wait_until='networkidle')
                await human_delay(3, 5)

                # Scroll to load more events
                for i in range(5):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await human_delay(1, 2)

                content = await page.content()
                event_ids = list(set(re.findall(r"/events/(\d+)", content)))
                print(f"  Found {len(event_ids)} event links")

                for eid in event_ids[:8]:  # Limit per search
                    if eid in seen_ids:
                        continue
                    seen_ids.add(eid)

                    try:
                        await page.goto(f"https://www.facebook.com/events/{eid}/", timeout=20000)
                        await human_delay(2, 4)

                        # Get title
                        title = await page.title()
                        title = title.replace(" | Facebook", "").strip()
                        title = re.sub(r"^\(\d+\)\s*", "", title)  # Remove notification count

                        if not title or "Facebook" in title or len(title) < 3:
                            print(f"    {eid}: Skip (no title)")
                            continue

                        # Get description from meta
                        desc = ""
                        try:
                            desc_el = await page.query_selector('meta[name="description"]')
                            if desc_el:
                                desc = await desc_el.get_attribute("content") or ""
                        except:
                            pass

                        # Get image
                        img = None
                        try:
                            img_el = await page.query_selector('meta[property="og:image"]')
                            if img_el:
                                img = await img_el.get_attribute("content")
                        except:
                            pass

                        # Try to get date from page
                        event_date = None
                        html = await page.content()

                        # Try timestamp
                        ts_match = re.search(r'"start_timestamp":(\d+)', html)
                        if ts_match:
                            try:
                                event_date = datetime.fromtimestamp(int(ts_match.group(1)))
                            except:
                                pass

                        # Try ISO date
                        if not event_date:
                            iso_match = re.search(r'"startDate":"([^"]+)"', html)
                            if iso_match:
                                try:
                                    event_date = datetime.fromisoformat(
                                        iso_match.group(1).replace("Z", "+00:00")
                                    ).replace(tzinfo=None)
                                except:
                                    pass

                        # Default to upcoming weekend
                        if not event_date:
                            now = datetime.now()
                            days = (5 - now.weekday()) % 7
                            if days == 0:
                                days = 7
                            event_date = (now + timedelta(days=days)).replace(
                                hour=21, minute=0, second=0, microsecond=0
                            )

                        # Skip old events
                        if event_date < datetime.now() - timedelta(days=1):
                            print(f"    {eid}: Skip (past event)")
                            continue

                        # Detect district
                        text = f"{title} {desc}".lower()
                        district = "Central Bangkok"
                        for k, v in {
                            "thonglor": "Thonglor",
                            "ekkamai": "Ekkamai",
                            "sukhumvit": "Sukhumvit",
                            "silom": "Silom",
                            "siam": "Siam",
                            "rca": "RCA",
                            "khao san": "Khao San",
                            "asok": "Asok",
                        }.items():
                            if k in text:
                                district = v
                                break

                        # Detect category
                        category = "party"
                        if any(w in text for w in ["music", "concert", "live", "band", "dj"]):
                            category = "music"
                        elif any(w in text for w in ["art", "exhibition", "gallery"]):
                            category = "art"
                        elif any(w in text for w in ["food", "dinner", "brunch", "restaurant"]):
                            category = "food"
                        elif any(w in text for w in ["club", "party", "night", "rave"]):
                            category = "party"

                        # District coordinates
                        coords = {
                            "Thonglor": (13.7307, 100.5844),
                            "Ekkamai": (13.7234, 100.5874),
                            "Sukhumvit": (13.7400, 100.5600),
                            "Silom": (13.7260, 100.5230),
                            "Siam": (13.7453, 100.5318),
                            "RCA": (13.7567, 100.5623),
                            "Khao San": (13.7590, 100.4970),
                            "Asok": (13.7380, 100.5608),
                            "Central Bangkok": (13.7563, 100.5018),
                        }
                        lat, lng = coords.get(district, (13.7563, 100.5018))

                        event_data = {
                            "title": title[:255],
                            "description": desc[:2000] if desc else None,
                            "start_datetime": event_date.isoformat(),
                            "end_datetime": None,
                            "venue_name": None,
                            "address": None,
                            "latitude": lat,
                            "longitude": lng,
                            "district": district,
                            "category": category,
                            "tags": [],
                            "source": "facebook",
                            "source_url": f"https://www.facebook.com/events/{eid}/",
                            "source_id": f"fb_{eid}",
                            "image_url": img,
                            "price_info": None,
                            "organizer_name": None,
                        }

                        all_events.append(event_data)
                        print(f"    + {title[:50]}")

                    except Exception as e:
                        print(f"    {eid}: Error - {str(e)[:40]}")
                        continue

                await human_delay(2, 4)

            except Exception as e:
                print(f"  Search failed: {str(e)[:50]}")
                continue

        await browser.close()

        # Save results
        if all_events:
            # Deduplicate by source_id
            unique_events = {e['source_id']: e for e in all_events}
            all_events = list(unique_events.values())

            with open("scraped_events.json", "w", encoding="utf-8") as f:
                json.dump(all_events, f, indent=2, ensure_ascii=False)
            print(f"\n=== Saved {len(all_events)} events to scraped_events.json ===")
        else:
            print("\n=== No events scraped ===")

        return all_events


if __name__ == "__main__":
    print("=" * 60)
    print("FACEBOOK EVENT SCRAPER (Xvfb Mode)")
    print("=" * 60)
    events = asyncio.run(scrape_facebook())
    print(f"\nTotal events: {len(events)}")
