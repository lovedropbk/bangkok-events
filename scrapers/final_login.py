"""
FINAL INSTAGRAM LOGIN SETUP

Run this script and log in. The script automatically detects when you're logged in.

Usage:
    python final_login.py
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    print("=" * 60)
    print("INSTAGRAM LOGIN")
    print("=" * 60)
    print()
    print("A browser will open at Instagram.")
    print("Please LOG IN with your account.")
    print()
    print("The script will automatically detect when you're logged in")
    print("and save your session.")
    print()
    print("Starting browser...")
    print()

    profile_dir = Path(__file__).parent / "ig_profile"
    profile_dir.mkdir(exist_ok=True)

    async with async_playwright() as p:
        # Use persistent context so login is remembered
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Hide automation
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Go to Instagram login
        await page.goto("https://www.instagram.com/accounts/login/")

        print("Browser opened at Instagram login.")
        print("Please log in...")
        print()
        print("Checking for login (will detect automatically)...")

        # Poll for sessionid cookie
        logged_in = False
        for i in range(300):  # 10 minutes max
            await asyncio.sleep(2)

            cookies = await context.cookies()
            cookie_names = [c["name"] for c in cookies]

            if "sessionid" in cookie_names:
                logged_in = True
                print()
                print("*" * 40)
                print("LOGIN DETECTED!")
                print("*" * 40)
                break

            # Show status every 30 seconds
            if i % 15 == 0 and i > 0:
                print(f"  Still waiting... (cookies: {len(cookie_names)})")

        if logged_in:
            # Save session
            state = await context.storage_state()
            Path("instagram_session.json").write_text(json.dumps(state, indent=2))
            print()
            print("Session saved to instagram_session.json!")

            # Test scraping
            print()
            print("-" * 40)
            print("TESTING SCRAPING")
            print("-" * 40)

            await page.goto("https://www.instagram.com/bangkokinvader/", timeout=30000)
            await asyncio.sleep(5)

            title = await page.title()
            print(f"Profile title: {title}")

            # Scroll
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)

            # Check for posts
            import re
            content = await page.content()
            posts = re.findall(r'/p/([A-Za-z0-9_-]+)', content)
            posts = list(set(posts))

            print(f"Posts found: {len(posts)}")

            if posts:
                print()
                print("=" * 40)
                print("SUCCESS! Instagram scraping works!")
                print("=" * 40)
            else:
                print()
                print("Profile loaded but no posts found.")
                print("Instagram may need more time to load posts.")

        else:
            print()
            print("Login timeout. Please run the script again.")

        print()
        input("Press Enter to close the browser...")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
