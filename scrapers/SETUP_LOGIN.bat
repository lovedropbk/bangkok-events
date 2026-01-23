@echo off
echo ===============================================
echo     INSTAGRAM AND FACEBOOK LOGIN SETUP
echo ===============================================
echo.
echo A browser will open. Please:
echo   1. Log in to Instagram
echo   2. Open a new tab and log in to Facebook
echo   3. After logging in to BOTH, close the browser
echo.
echo The script will automatically save your sessions.
echo.
pause
cd /d "%~dp0"
python login_and_save.py
pause
