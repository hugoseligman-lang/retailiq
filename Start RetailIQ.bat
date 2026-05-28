@echo off
title RetailIQ
cd /d "%~dp0backend"

:: Install / update dependencies silently
pip install -r requirements.txt --quiet --no-warn-script-location 2>nul

:: Start the backend with no console window
start "" pythonw main.py

:: Wait for it to be ready, then open the dashboard
timeout /t 3 /nobreak >nul
start "" http://localhost:5050

:: Close this window
exit
