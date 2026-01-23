"""
Facebook Login - Save session for scraping.
Run this when your Facebook session expires.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def login_facebook():
    print("=" * 60)
    print("FACEBOOK LOGIN")
    print("=" * 60)
    print()
    print("A browser window will open.")
    print("1. Log in to Facebook")
    print("2. Complete any verification (2FA, CAPTCHA)")
    print("3. Wait until you see your Facebook feed")
    print("4. The script will automatically save your session")
    print()
    input("Press Enter to continue...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        await page.goto("https://www.facebook.com/login")
        print("\nWaiting for login...")

        # Wait for successful login (user reaches feed)
        while True:
            await asyncio.sleep(2)
            url = page.url

            if "facebook.com" in url and "/login" not in url and "checkpoint" not in url:
                # Check if we can see content
                try:
                    await page.wait_for_selector('[role="feed"], [data-pagelet="Feed"]', timeout=5000)
                    print("\n✓ LOGIN DETECTED!")
                    break
                except:
                    pass

            # Also check for profile or home
            if any(x in url for x in ["/home", "/?sk=", "facebook.com/?ref"]):
                print("\n✓ LOGIN DETECTED!")
                break

        # Save session
        state = await context.storage_state()
        Path("facebook_session.json").write_text(json.dumps(state, indent=2))
        print("✓ Session saved to facebook_session.json")

        # Test scraping
        print("\nTesting event search...")
        await page.goto("https://www.facebook.com/search/events/?q=bangkok%20party", timeout=30000)
        await asyncio.sleep(5)

        content = await page.content()
        import re
        events = list(set(re.findall(r"/events/(\d+)", content)))
        print(f"✓ Found {len(events)} events in search")

        await browser.close()

        if events:
            print("\n" + "=" * 60)
            print("SUCCESS! Your Facebook session is ready.")
            print("Run: python quick_fb_scrape.py")
            print("=" * 60)
        else:
            print("\nWarning: No events found. Facebook may be blocking.")

        return len(events) > 0


if __name__ == "__main__":
    asyncio.run(login_facebook())
