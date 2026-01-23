@echo off
echo ====================================
echo INSTAGRAM SCRAPER SETUP
echo ====================================
echo.
echo This will:
echo 1. Close Chrome (if running)
echo 2. Reopen Chrome with debugging enabled
echo 3. Connect to your existing login session
echo.
echo IMPORTANT: Make sure you're logged into Instagram in Chrome!
echo.
pause

REM Kill existing Chrome
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 >nul

REM Start Chrome with remote debugging
echo Starting Chrome with remote debugging...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data"

echo.
echo Chrome opened. Wait a few seconds, then run:
echo   python connect_to_chrome.py
echo.
pause
