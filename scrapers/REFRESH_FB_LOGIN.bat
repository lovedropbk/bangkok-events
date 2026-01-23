@echo off
echo ============================================
echo  FACEBOOK LOGIN - Session Refresh
echo ============================================
echo.
echo Your Facebook session has expired.
echo A browser will open - please log in.
echo.

cd /d "%~dp0"
python fb_login.py

echo.
pause
