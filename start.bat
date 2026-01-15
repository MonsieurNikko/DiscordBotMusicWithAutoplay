@echo off
REM ========================================
REM Discord Music Bot - Windows Starter
REM ========================================

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Install Python 3.11+
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
pip install -r requirements.txt -q

echo [3/3] Starting bot...
echo.
echo ========================================
echo   IMPORTANT: Lavalink must be running!
echo   Default: localhost:2333
echo ========================================
echo.

python -m bot.main

pause
