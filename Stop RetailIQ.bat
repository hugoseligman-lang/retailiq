@echo off
title RetailIQ - Stopping

:: Kill the watchdog first so it doesn't restart the backend
taskkill /FI "WINDOWTITLE eq RetailIQ Watchdog*" /F /T >nul 2>&1

:: Kill the Python backend processes
taskkill /F /IM python.exe   /T >nul 2>&1
taskkill /F /IM pythonw.exe  /T >nul 2>&1

:: Restore normal Windows sleep settings
powercfg /change standby-timeout-ac 20  >nul 2>&1
powercfg /change monitor-timeout-ac 10  >nul 2>&1

echo RetailIQ has been stopped.
timeout /t 2 /nobreak >nul
exit
