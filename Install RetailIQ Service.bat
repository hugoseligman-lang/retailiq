@echo off
title Install RetailIQ — Auto-start on Boot

set "LAUNCHER=%~dp0Start RetailIQ.bat"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo Installing RetailIQ to start automatically when Windows boots...

:: Method 1: Windows Startup folder (simplest, works for current user)
copy /Y "%LAUNCHER%" "%STARTUP%\Start RetailIQ.bat" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Added to Startup folder: %STARTUP%
) else (
    echo [WARN] Could not write to Startup folder.
)

:: Method 2: Task Scheduler (more robust, survives user profile moves)
schtasks /delete /tn "RetailIQ" /f >nul 2>&1
schtasks /create /tn "RetailIQ" /tr "\"%LAUNCHER%\"" /sc onlogon /rl highest /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Registered as Windows Scheduled Task "RetailIQ"
) else (
    echo [INFO] Scheduled Task requires admin — Startup folder method is active.
)

echo.
echo RetailIQ will now start automatically every time this computer boots.
echo To remove auto-start, delete "Start RetailIQ.bat" from:
echo   %STARTUP%
echo.

:: Start it right now
call "%LAUNCHER%"
