@echo off
echo =====================================
echo  BANGKOK EVENT SCRAPER - FINAL SETUP
echo =====================================
echo.
echo This will open a browser for Instagram login.
echo.
echo IMPORTANT:
echo - Log in with your Instagram credentials
echo - Complete any verification (CAPTCHA, 2FA)
echo - Wait for the script to detect your login
echo.
pause

cd /d "%~dp0"
python final_login.py

echo.
echo =====================================
echo If successful, you can now run:
echo   python -m scrapers.persistent_scraper
echo =====================================
pause
