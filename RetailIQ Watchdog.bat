@echo off
title RetailIQ Watchdog (do not close)
cd /d "%~dp0backend"

:loop
echo [%date% %time%] Starting RetailIQ backend...
python main.py
echo [%date% %time%] Backend stopped (exit %ERRORLEVEL%). Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
