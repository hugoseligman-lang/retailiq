@echo off
title RetailIQ - Stopping
taskkill /F /IM pythonw.exe /T >nul 2>&1
echo RetailIQ has been stopped.
timeout /t 2 /nobreak >nul
exit
