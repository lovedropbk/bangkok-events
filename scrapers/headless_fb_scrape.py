"""
Headless Facebook scraper for GitHub Actions.
"""

import asyncio
import json
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright


async def scrape_facebook():
    session_file = Path("facebook_session.json")
    if not session_file.exists():
        print("No facebook_session.json found")
        return []

    session = json.loads(session_file.read_text())

    async with async_playwright() as p:
        # Use headless mode for CI
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        context = await browser.new_context(
            storage_state=session,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        print("Searching Facebook events...")
        try:
            await page.goto(
                "https://www.facebook.com/search/events/?q=bangkok%20party", timeout=30000
            )
            await asyncio.sleep(5)

            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            content = await page.content()
            events = list(set(re.findall(r"/events/(\d+)", content)))
            print(f"Found {len(events)} events")

            scraped = []
            for eid in events[:15]:
                try:
                    await page.goto(
                        f"https://www.facebook.com/events/{eid}/", timeout=20000
                    )
                    await asyncio.sleep(3)

                    # Get title from page
                    title = await page.title()
                    title = title.replace(" | Facebook", "").strip()
                    title = re.sub(r"^\(\d+\)\s*", "", title)

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

                    if title and "Facebook" not in title:
                        print(f"  + {title[:50]}")

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
                        }.items():
                            if k in text:
                                district = v
                                break

                        # Detect category
                        category = "party"
                        if any(w in text for w in ["music", "concert", "live", "band"]):
                            category = "music"
                        elif any(w in text for w in ["art", "exhibition", "gallery"]):
                            category = "art"
                        elif any(w in text for w in ["food", "dinner", "brunch"]):
                            category = "food"

                        # Get coords
                        coords = {
                            "Thonglor": (13.7307, 100.5844),
                            "Ekkamai": (13.7234, 100.5874),
                            "Sukhumvit": (13.74, 100.56),
                            "Central Bangkok": (13.7563, 100.5018),
                        }
                        lat, lng = coords.get(district, (13.7563, 100.5018))

                        scraped.append(
                            {
                                "title": title[:255],
                                "description": desc[:2000] if desc else None,
                                "start_datetime": (
                                    datetime.now() + timedelta(days=3)
                                )
                                .replace(hour=21, minute=0, second=0, microsecond=0)
                                .isoformat(),
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
                        )
                    else:
                        print(f"  - {eid}: Skip")
                except Exception as e:
                    print(f"  - {eid}: Error - {str(e)[:40]}")

        except Exception as e:
            print(f"Search failed: {e}")
            await browser.close()
            return []

        await browser.close()

        if scraped:
            with open("scraped_events.json", "w", encoding="utf-8") as f:
                json.dump(scraped, f, indent=2, ensure_ascii=False)
            print(f"\nSaved {len(scraped)} events to scraped_events.json")

        return scraped


if __name__ == "__main__":
    asyncio.run(scrape_facebook())
