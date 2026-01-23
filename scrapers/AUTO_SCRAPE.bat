@echo off
echo ============================================
echo  BANGKOK EVENTS - AUTO SCRAPER
echo ============================================
echo.

cd /d "%~dp0"

echo [%date% %time%] Starting scrape...

:: Run the Facebook scraper
python quick_fb_scrape.py

:: Check if we got events
for /f %%i in ('python -c "import json; print(len(json.load(open('scraped_events.json'))))"') do set EVENT_COUNT=%%i

if %EVENT_COUNT% GTR 0 (
    echo [%date% %time%] Got %EVENT_COUNT% events, updating...

    :: Copy to frontend
    copy /Y scraped_events.json ..\frontend\public\events.json

    :: Git commit and push
    cd ..
    git add frontend/public/events.json
    git diff --staged --quiet
    if errorlevel 1 (
        git commit -m "Update events data [automated] - %EVENT_COUNT% events"
        git push
        echo [%date% %time%] Pushed to GitHub

        :: Also deploy directly to Vercel
        cd frontend
        call npx vercel --prod --yes
        echo [%date% %time%] Deployed to Vercel
    ) else (
        echo [%date% %time%] No changes to commit
    )

    echo [%date% %time%] Done!
) else (
    echo [%date% %time%] ERROR: No events scraped
    echo Check your Facebook session - run REFRESH_FB_LOGIN.bat
)

echo.
