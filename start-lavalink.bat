@echo off
REM ========================================
REM Download & Start Lavalink (requires Java 17+)
REM ========================================

set LAVALINK_VERSION=4.0.8
set LAVALINK_JAR=Lavalink.jar
set LAVALINK_CONFIG=lavalink\application.yml

echo [1/2] Checking Java...
java -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Java not found! Install Java 17+
    echo Download: https://adoptium.net/
    pause
    exit /b 1
)

echo [2/2] Starting Lavalink...
if not exist "%LAVALINK_JAR%" (
    echo Downloading Lavalink %LAVALINK_VERSION%...
    curl -L -o %LAVALINK_JAR% https://github.com/lavalink-devs/Lavalink/releases/download/%LAVALINK_VERSION%/Lavalink.jar
)

echo.
echo ========================================
echo   Lavalink starting on port 2333
echo   Press Ctrl+C to stop
echo ========================================
echo.

java -jar %LAVALINK_JAR% --spring.config.location=%LAVALINK_CONFIG%
