"""
Quick setup script to save Instagram and Facebook sessions.
Run this once to save your login sessions, then scrapers can use them.

Usage:
    python setup_sessions.py

This will:
1. Open a browser window
2. You log into Instagram and Facebook
3. Sessions are saved automatically
4. Future scraping uses saved sessions (no manual login needed)
"""

import asyncio
import json
import logging
from pathlib import Path
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INSTAGRAM_SESSION = "instagram_session.json"
FACEBOOK_SESSION = "facebook_session.json"


async def setup_instagram_session():
    """Set up Instagram session"""
    logger.info("=" * 60)
    logger.info("SETTING UP INSTAGRAM SESSION")
    logger.info("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.instagram.com/accounts/login/")

        logger.info("\nPlease log in to Instagram in the browser window.")
        logger.info("After logging in successfully, press Enter here to save the session.\n")

        input("Press Enter after you've logged in to Instagram...")

        # Save session
        state = await context.storage_state()
        Path(INSTAGRAM_SESSION).write_text(json.dumps(state))
        logger.info(f"Instagram session saved to {INSTAGRAM_SESSION}")

        await browser.close()


async def setup_facebook_session():
    """Set up Facebook session"""
    logger.info("=" * 60)
    logger.info("SETTING UP FACEBOOK SESSION")
    logger.info("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.facebook.com/login")

        logger.info("\nPlease log in to Facebook in the browser window.")
        logger.info("After logging in successfully, press Enter here to save the session.\n")

        input("Press Enter after you've logged in to Facebook...")

        # Save session
        state = await context.storage_state()
        Path(FACEBOOK_SESSION).write_text(json.dumps(state))
        logger.info(f"Facebook session saved to {FACEBOOK_SESSION}")

        await browser.close()


async def main():
    logger.info("This script will help you save your login sessions.")
    logger.info("Run this once, then scrapers will work automatically.\n")

    # Instagram
    if not Path(INSTAGRAM_SESSION).exists():
        await setup_instagram_session()
    else:
        logger.info(f"Instagram session already exists: {INSTAGRAM_SESSION}")
        response = input("Re-create Instagram session? (y/N): ")
        if response.lower() == 'y':
            await setup_instagram_session()

    # Facebook
    if not Path(FACEBOOK_SESSION).exists():
        await setup_facebook_session()
    else:
        logger.info(f"Facebook session already exists: {FACEBOOK_SESSION}")
        response = input("Re-create Facebook session? (y/N): ")
        if response.lower() == 'y':
            await setup_facebook_session()

    logger.info("\n" + "=" * 60)
    logger.info("SETUP COMPLETE!")
    logger.info("=" * 60)
    logger.info("\nYou can now run the scrapers:")
    logger.info("  python -m scrapers.master_scraper")


if __name__ == "__main__":
    asyncio.run(main())
