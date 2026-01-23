"""
Run this script to log in to Instagram and Facebook and save sessions.

Usage:
    python login_and_save.py

After running:
- Browser opens
- Log in to Instagram
- Open new tab, log in to Facebook
- Come back to terminal and press Enter
- Sessions are saved for future scraping
"""

import asyncio
import json
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Installing playwright...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"])
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright


async def main():
    print("=" * 60)
    print("INSTAGRAM & FACEBOOK SESSION SETUP")
    print("=" * 60)
    print()
    print("A browser window will open.")
    print("Please:")
    print("  1. Log in to INSTAGRAM")
    print("  2. Open a NEW TAB and log in to FACEBOOK")
    print("  3. Come back here and press Enter")
    print()

    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        # Start at Instagram
        print("Opening Instagram login page...")
        await page.goto("https://www.instagram.com/accounts/login/")

        print()
        print("Browser is open. Log in to Instagram first.")
        print("Then open a new tab (Ctrl+T) and go to facebook.com to log in.")
        print()
        print("-" * 60)

        # Wait for user with periodic status check
        while True:
            try:
                user_input = input("Press Enter when done with BOTH logins (or 'q' to quit)... ")
                if user_input.lower() == 'q':
                    print("Cancelled.")
                    await browser.close()
                    return
                break
            except EOFError:
                # Handle case where input isn't available
                import asyncio
                await asyncio.sleep(5)

        print("-" * 60)

        # Check what cookies we got
        cookies = await context.cookies()
        cookie_names = [c['name'] for c in cookies]

        has_ig = 'sessionid' in cookie_names
        has_fb = 'c_user' in cookie_names

        print()
        if has_ig:
            print("✓ Instagram session found!")
        else:
            print("✗ Instagram session NOT found - make sure you logged in")

        if has_fb:
            print("✓ Facebook session found!")
        else:
            print("✗ Facebook session NOT found - make sure you logged in")

        # Save the session state
        state = await context.storage_state()

        # Save to both files
        Path("instagram_session.json").write_text(json.dumps(state, indent=2))
        Path("facebook_session.json").write_text(json.dumps(state, indent=2))

        print()
        if has_ig or has_fb:
            print("Sessions saved!")
            print("  - instagram_session.json")
            print("  - facebook_session.json")
            print()
            print("You can now run the scraper:")
            print("  python -m scrapers.master_scraper")
        else:
            print("No sessions were saved. Please try again and make sure to log in.")
        print()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
