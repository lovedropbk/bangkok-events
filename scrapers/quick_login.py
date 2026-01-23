"""
Simple one-shot script to log into Instagram and test scraping.
Run this in a command prompt/PowerShell:

    cd C:\Users\Patrick\coding\event_party_app\scrapers
    python quick_login.py

After logging in, press Enter to test scraping.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    print("=" * 60)
    print("INSTAGRAM LOGIN & TEST")
    print("=" * 60)

    profile_dir = Path(__file__).parent / "scrapers" / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Check if already logged in
        print("\nChecking login status...")
        await page.goto("https://www.instagram.com/", timeout=30000)
        await asyncio.sleep(3)

        cookies = await context.cookies()
        has_session = any(c["name"] == "sessionid" for c in cookies)

        if has_session:
            print("Already logged in!")
        else:
            print("\nNot logged in. Please log in now.")
            print("Go to the browser window and log in to Instagram.")
            print()
            input("Press Enter AFTER you have logged in successfully... ")

            # Re-check
            cookies = await context.cookies()
            has_session = any(c["name"] == "sessionid" for c in cookies)

            if not has_session:
                print("Still not logged in. Please try again.")
                await context.close()
                return

        # Save session
        state = await context.storage_state()
        Path("instagram_session.json").write_text(json.dumps(state, indent=2))
        print("Session saved!")

        # Test scraping
        print("\n" + "-" * 40)
        print("TESTING SCRAPING")
        print("-" * 40)

        test_account = "bangkokinvader"
        print(f"\nLoading @{test_account}...")

        await page.goto(f"https://www.instagram.com/{test_account}/", timeout=30000)
        await asyncio.sleep(5)

        title = await page.title()
        print(f"Page title: {title}")

        # Scroll to load posts
        print("Scrolling to load posts...")
        for i in range(5):
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1)

        # Find posts
        content = await page.content()
        posts = re.findall(r'/p/([A-Za-z0-9_-]+)', content)
        posts = list(set(posts))

        print(f"Posts found: {len(posts)}")

        if posts:
            print("\nTesting first post...")
            shortcode = posts[0]
            await page.goto(f"https://www.instagram.com/p/{shortcode}/")
            await asyncio.sleep(3)

            html = await page.content()
            desc_match = re.search(r'property="og:description" content="([^"]+)"', html)

            if desc_match:
                caption = desc_match.group(1)[:200]
                print(f"Caption: {caption}...")
            else:
                print("Could not extract caption")

            print("\n" + "=" * 60)
            print("SUCCESS! Instagram scraping is working!")
            print("=" * 60)
        else:
            print("\nNo posts found. Instagram may be blocking the scraper.")
            print("Try manually scrolling in the browser and then run again.")

        input("\nPress Enter to close... ")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
