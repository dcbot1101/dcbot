@echo off
title Discord Bot Launcher

:: This just runs the Python launcher
:: All the logic is in start.py

:: Try 'py' first (Windows Python launcher), fallback to 'python'
py "%~dp0start.py" 2>nul || python "%~dp0start.py"

:: Pause at the end (Python script also has pause, but this ensures window stays open)
if errorlevel 1 (
    echo.
    echo Launcher exited with error.
    pause
)
