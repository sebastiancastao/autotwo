@echo off
echo ==============================================
echo Gmail OAuth + ETERNAL 20-Minute Processing
echo ==============================================
echo This will:
echo 1. Complete Gmail OAuth authentication
echo 2. Run Gmail processing every 20 minutes
echo 3. Continue FOREVER until you manually stop it
echo 4. Automatically retry on any errors
echo ==============================================
echo.
echo WARNING: This will run CONTINUOUSLY!
echo Press Ctrl+C to stop (but it will keep trying to restart)
echo Close this window completely to stop the automation.
echo.
set /p password=Enter your Gmail password: 
echo.
echo Starting ETERNAL automation...
echo This will run forever - close the window to stop.
echo.

:RESTART
echo [%date% %time%] Starting/Restarting automation...
python python_oauth_automation.py --password "%password%" --workflow
echo [%date% %time%] Automation stopped unexpectedly - restarting in 10 seconds...
timeout /t 10 /nobreak
goto RESTART 