@echo off
title NOC Report System
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Checking dependencies...
pip install -r requirements.txt --quiet --break-system-packages 2>nul || pip install -r requirements.txt --quiet

REM Launch the app
echo Starting NOC Report System...
python noc_app.py

pause
