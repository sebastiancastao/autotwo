@echo off
title ETERNAL Gmail Automation - NEVER STOPS
color 0A
echo ==============================================
echo    ETERNAL Gmail OAuth Automation
echo          RUNS FOREVER - NEVER STOPS
echo ==============================================
echo.
echo This automation will:
echo   ✅ Complete Gmail OAuth authentication
echo   🔄 Process Gmail every 20 minutes
echo   🛡️ Automatically retry on ANY error
echo   ♾️ Run FOREVER until you close this window
echo   🔄 Restart even if crashed or interrupted
echo.
echo ==============================================
echo   WARNING: THIS WILL RUN CONTINUOUSLY!
echo ==============================================
echo.
echo To stop this automation:
echo   1. Close this window completely, OR
echo   2. Press Ctrl+C multiple times, OR  
echo   3. Kill the process from Task Manager
echo.
set /p password=Enter your Gmail password: 
echo.
echo ===============================================
echo   🚀 STARTING ETERNAL AUTOMATION
echo   This will run FOREVER!
echo ===============================================
echo.

:ETERNAL_RESTART
echo [%date% %time%] 🔄 Starting ETERNAL automation...
python eternal_gmail_automation.py --password "%password%"
echo [%date% %time%] ⚠️ Automation stopped - auto-restarting in 5 seconds...
echo                     Close window now to prevent restart!
timeout /t 5 /nobreak >nul
goto ETERNAL_RESTART 