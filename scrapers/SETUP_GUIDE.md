# Bangkok Event Scraper Setup Guide

This guide explains how to set up the Instagram and Facebook scrapers.

## Prerequisites

1. Python 3.10+ installed
2. Playwright installed: `pip install playwright`
3. Playwright browsers: `python -m playwright install chromium`

## Quick Setup (Recommended)

### Step 1: Run the Login Script

Open a **Command Prompt** or **PowerShell** and run:

```bash
cd C:\Users\Patrick\coding\event_party_app\scrapers
python final_login.py
```

This will:
1. Open a browser window at Instagram login
2. Wait for you to log in
3. Automatically detect the login and save your session
4. Test that scraping works

### Step 2: Log In Manually

In the browser window:
1. Enter your Instagram username and password
2. Complete any verification (CAPTCHA, 2FA, etc.)
3. Wait until you see your Instagram feed

The script will automatically detect the login and save your session.

### Step 3: Verify It Worked

After the script detects your login, it will:
- Show "LOGIN DETECTED!"
- Test scraping a profile
- Show "SUCCESS!" if it works

## Troubleshooting

### "Login not detected" after logging in
- Instagram may have blocked the automated browser
- Try logging in again or use a different browser approach

### "Posts found: 0" after login
- Instagram is loading content dynamically
- The scraper may need adjustments

### Alternative: Manual Event Collection
If automated scraping doesn't work, you can manually collect events:

```bash
cd C:\Users\Patrick\coding\event_party_app\scrapers
python manual_ig_scraper.py
```

Then paste Instagram post URLs when prompted.

## Running the Scraper

Once logged in, run the scraper:

```bash
cd C:\Users\Patrick\coding\event_party_app\scrapers
python -m scrapers.persistent_scraper
```

This will:
1. Scrape Instagram accounts for Bangkok events
2. Search Facebook for Bangkok events
3. Save results to `scraped_events.json`

## Backend Integration

The backend can run scrapers automatically. Set:

```bash
export ENABLE_SCRAPER=true
cd C:\Users\Patrick\coding\event_party_app\backend
uvicorn app.main:app --reload
```

## Files Created

- `instagram_session.json` - Your saved Instagram login session
- `facebook_session.json` - Your saved Facebook login session
- `scraped_events.json` - Scraped events in JSON format
- `ig_profile/` - Persistent browser profile with login

## Important Notes

1. **Instagram blocks automated browsers** - This is why login is tricky
2. **Sessions expire** - You may need to re-login periodically
3. **Rate limiting** - Don't scrape too aggressively
4. **Terms of Service** - Use responsibly
