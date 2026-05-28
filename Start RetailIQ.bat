@echo off
title RetailIQ
cd /d "%~dp0backend"

:: Prevent Windows from sleeping or turning off the screen while RetailIQ runs
powercfg /change standby-timeout-ac 0    >nul 2>&1
powercfg /change monitor-timeout-ac 0    >nul 2>&1
powercfg /change hibernate-timeout-ac 0  >nul 2>&1

:: Install / update Python dependencies silently
pip install -r requirements.txt --quiet --no-warn-script-location >nul 2>&1

:: Launch the watchdog in a minimised window.
:: The watchdog starts the backend and restarts it automatically if it ever crashes.
start "RetailIQ Watchdog (do not close)" /min "%~dp0RetailIQ Watchdog.bat"

:: Wait for backend to be ready, then open the dashboard
timeout /t 4 /nobreak >nul
start "" http://localhost:5050

exit
