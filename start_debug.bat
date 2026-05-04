@echo off
title Discord Bot Launcher - DEBUG MODE

:: This runs the bot in DEBUG MODE with detailed logging
:: All output will be saved to bot_debug.log and launcher_debug.log

echo ============================================
echo    DISCORD BOT - DEBUG MODE
echo ============================================
echo.
echo Debug mode enabled! All details will be logged.
echo Log files: bot_debug.log, launcher_debug.log
echo.
pause

:: Try 'py' first (Windows Python launcher), fallback to 'python'
py "%~dp0start.py" --debug 2>nul || python "%~dp0start.py" --debug

:: Pause at the end
echo.
if errorlevel 1 (
    echo Launcher exited with error.
    echo Check bot_debug.log for details.
)
pause
