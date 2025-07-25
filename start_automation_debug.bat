@echo off
echo ==============================================
echo ETERNAL Gmail Workflow (DEBUG MODE)
echo ==============================================
echo This will:
echo 1. Complete Gmail OAuth authentication
echo 2. Run Gmail processing every 20 minutes
echo 3. Continue FOREVER with auto-restart
echo 4. Keep browser open for debugging
echo 5. Show detailed logs
echo ==============================================
echo.
echo WARNING: This will run CONTINUOUSLY!
echo Close this window completely to stop the automation.
echo.
set /p password=Enter your Gmail password: 
echo.
echo Starting ETERNAL automation in DEBUG mode...
echo Browser will stay open for troubleshooting.
echo This will run forever - close the window to stop.
echo.

:RESTART
echo [%date% %time%] Starting/Restarting DEBUG automation...
python python_oauth_automation.py --password "%password%" --workflow --debug --keep-open 30
echo [%date% %time%] DEBUG automation stopped - restarting in 10 seconds...
timeout /t 10 /nobreak
goto RESTART 