"""
Connect to Chrome with your existing login and scrape Instagram.

Prerequisites:
1. Run START_CHROME_DEBUG.bat (or manually start Chrome with --remote-debugging-port=9222)
2. Make sure you're logged into Instagram in Chrome
3. Run this script

This connects to your existing Chrome session and uses your real login.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright


async def connect_and_scrape():
    print("=" * 60)
    print("CONNECTING TO CHROME")
    print("=" * 60)

    async with async_playwright() as p:
        try:
            # Connect to Chrome via CDP
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            print("Connected to Chrome!")

            # Get existing context
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()

            # Check Instagram login
            print("\nChecking Instagram login...")
            await page.goto("https://www.instagram.com/", timeout=30000)
            await asyncio.sleep(3)

            title = await page.title()
            print(f"Page title: {title}")

            if "login" in title.lower():
                print("NOT logged in! Please log in to Instagram in Chrome first.")
                await browser.close()
                return

            print("Logged in!")

            # Get cookies and save them
            cookies = await context.cookies()
            ig_cookies = [c for c in cookies if "instagram" in c.get("domain", "")]
            print(f"Instagram cookies: {len(ig_cookies)}")

            has_session = any(c["name"] == "sessionid" for c in ig_cookies)
            print(f"Has sessionid: {has_session}")

            if has_session:
                # Save session for future use
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
            print(f"Profile title: {title}")

            # Scroll
            print("Scrolling...")
            for i in range(5):
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)

            # Find posts
            content = await page.content()
            posts = re.findall(r'/p/([A-Za-z0-9_-]+)', content)
            posts = list(set(posts))

            print(f"Posts found: {len(posts)}")

            if posts:
                print("\n*** SUCCESS! Scraping works! ***")
                print(f"Sample posts: {posts[:3]}")

                # Test a post
                shortcode = posts[0]
                print(f"\nScraping post {shortcode}...")
                await page.goto(f"https://www.instagram.com/p/{shortcode}/")
                await asyncio.sleep(3)

                html = await page.content()
                desc = re.search(r'property="og:description" content="([^"]+)"', html)
                if desc:
                    caption = desc.group(1)[:200]
                    print(f"Caption: {caption}...")

            await browser.close()
            print("\nDone!")

        except Exception as e:
            print(f"Error: {e}")
            print("\nMake sure Chrome is running with --remote-debugging-port=9222")
            print("Run START_CHROME_DEBUG.bat first.")


if __name__ == "__main__":
    asyncio.run(connect_and_scrape())
