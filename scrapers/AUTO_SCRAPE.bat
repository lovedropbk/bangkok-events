@echo off
echo ============================================
echo  BANGKOK EVENTS - AUTO SCRAPER
echo ============================================
echo.

cd /d "%~dp0"

echo [%date% %time%] Starting scrape...

:: Run the Facebook scraper
python quick_fb_scrape.py

:: Check if scraping was successful
if exist scraped_events.json (
    echo [%date% %time%] Scraping complete, updating frontend...

    :: Copy to frontend
    copy /Y scraped_events.json ..\frontend\public\events.json

    :: Git commit and push
    cd ..
    git add frontend/public/events.json
    git diff --staged --quiet || (
        git commit -m "Update events data [automated]"
        git push
        echo [%date% %time%] Pushed to GitHub - Vercel will auto-deploy
    )

    echo [%date% %time%] Done!
) else (
    echo [%date% %time%] ERROR: No events scraped
)

echo.
