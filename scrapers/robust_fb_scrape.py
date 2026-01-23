"""
Robust Facebook scraper - waits for dynamic content.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright


async def scrape_facebook():
    session_file = Path("facebook_session.json")
    if not session_file.exists():
        print("ERROR: Run fb_login.py first")
        return []

    session = json.loads(session_file.read_text())

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            storage_state=session,
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = await context.new_page()

        print("Navigating to Facebook events search...")

        # Try multiple search URLs
        searches = [
            "https://www.facebook.com/events/search?q=bangkok",
            "https://www.facebook.com/search/events/?q=bangkok%20party",
            "https://www.facebook.com/search/events?q=bangkok%20events",
        ]

        all_event_ids = set()

        for search_url in searches:
            print(f"\nTrying: {search_url}")
            try:
                await page.goto(search_url, timeout=30000, wait_until='domcontentloaded')

                # Wait longer for dynamic content
                print("  Waiting for content to load...")
                await asyncio.sleep(8)

                # Scroll multiple times to load more
                for i in range(5):
                    await page.evaluate("window.scrollBy(0, 1000)")
                    await asyncio.sleep(2)

                # Get page content
                content = await page.content()

                # Save debug HTML
                Path("debug_search.html").write_text(content, encoding='utf-8')

                # Find event IDs
                event_ids = set(re.findall(r"/events/(\d{10,})", content))
                print(f"  Found {len(event_ids)} event links")
                all_event_ids.update(event_ids)

                # Also try to find events in data attributes
                data_ids = set(re.findall(r'"event_id":"(\d+)"', content))
                print(f"  Found {len(data_ids)} in data attributes")
                all_event_ids.update(data_ids)

            except Exception as e:
                print(f"  Error: {e}")

        print(f"\nTotal unique event IDs: {len(all_event_ids)}")

        if not all_event_ids:
            # Try clicking on Events tab if we're on general search
            print("\nTrying to find events via general search...")
            try:
                await page.goto("https://www.facebook.com/search/top?q=bangkok%20party%20event", timeout=30000)
                await asyncio.sleep(5)

                # Look for Events filter/tab
                events_tab = await page.query_selector('text=Events')
                if events_tab:
                    await events_tab.click()
                    await asyncio.sleep(5)

                content = await page.content()
                event_ids = set(re.findall(r"/events/(\d{10,})", content))
                all_event_ids.update(event_ids)
                print(f"Found {len(event_ids)} via general search")
            except Exception as e:
                print(f"Error: {e}")

        scraped = []
        for eid in list(all_event_ids)[:20]:
            try:
                print(f"\nScraping event {eid}...")
                await page.goto(f"https://www.facebook.com/events/{eid}/", timeout=20000)
                await asyncio.sleep(3)

                title = await page.title()
                title = title.replace(" | Facebook", "").strip()
                title = re.sub(r"^\(\d+\)\s*", "", title)

                if not title or "Facebook" in title or len(title) < 5:
                    print(f"  Skip: invalid title")
                    continue

                # Get description
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

                print(f"  Title: {title[:50]}")

                # District detection
                text = f"{title} {desc}".lower()
                district = "Central Bangkok"
                for k, v in {
                    "thonglor": "Thonglor", "ekkamai": "Ekkamai",
                    "sukhumvit": "Sukhumvit", "silom": "Silom",
                    "siam": "Siam", "rca": "RCA",
                }.items():
                    if k in text:
                        district = v
                        break

                # Category detection
                category = "party"
                if any(w in text for w in ["music", "concert", "live", "band"]):
                    category = "music"
                elif any(w in text for w in ["art", "exhibition", "gallery"]):
                    category = "art"
                elif any(w in text for w in ["food", "dinner", "brunch"]):
                    category = "food"

                coords = {
                    "Thonglor": (13.7307, 100.5844),
                    "Ekkamai": (13.7234, 100.5874),
                    "Sukhumvit": (13.74, 100.56),
                    "Central Bangkok": (13.7563, 100.5018),
                }
                lat, lng = coords.get(district, (13.7563, 100.5018))

                scraped.append({
                    "title": title[:255],
                    "description": desc[:2000] if desc else None,
                    "start_datetime": (datetime.now() + timedelta(days=3)).replace(
                        hour=21, minute=0, second=0, microsecond=0
                    ).isoformat(),
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
                })

            except Exception as e:
                print(f"  Error: {str(e)[:50]}")

        await browser.close()

        if scraped:
            with open("scraped_events.json", "w", encoding="utf-8") as f:
                json.dump(scraped, f, indent=2, ensure_ascii=False)
            print(f"\n{'='*60}")
            print(f"Saved {len(scraped)} events to scraped_events.json")
            print(f"{'='*60}")
        else:
            print("\nNo events scraped.")
            print("Check debug_search.html to see what Facebook returned.")

        return scraped


if __name__ == "__main__":
    print("=" * 60)
    print("FACEBOOK EVENT SCRAPER")
    print("=" * 60)
    asyncio.run(scrape_facebook())
