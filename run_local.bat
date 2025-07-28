@echo off
echo ====================================================
echo   Gmail OAuth Automation - LOCAL MODE
echo ====================================================
echo This will run the automation on your local computer
echo instead of the Render cloud deployment.
echo ====================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

echo ✅ Python found: 
python --version

REM Check for dependencies
echo 🔍 Checking dependencies...
python -c "import selenium, requests" >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    fi
)

echo ✅ Dependencies OK

REM Get local IP address
echo 🌐 Detecting your local IP address...
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=1" %%j in ("%%i") do (
        set LOCAL_IP=%%j
        goto :found_ip
    )
)

:found_ip
if not defined LOCAL_IP (
    set LOCAL_IP=localhost
    echo ⚠️ Could not detect IP, using localhost
) else (
    echo ✅ Local IP detected: %LOCAL_IP%
)

echo.
echo 🚀 Starting LOCAL Gmail automation...
echo 📍 Running on: http://%LOCAL_IP%:8080
echo 🌐 OAuth redirect will use: http://%LOCAL_IP%:8080/oauth-callback.html
echo.

REM Set local environment variables
set ENVIRONMENT=local
set BROWSER_HEADLESS=false
set PORT=8080
set APP_BASE_URL=http://%LOCAL_IP%:8080
set GOOGLE_REDIRECT_URI=http://%LOCAL_IP%:8080/oauth-callback.html

echo Select mode:
echo 1. 🌐 Run web service (recommended for local testing)
echo 2. 📧 Direct Gmail automation with password
echo 3. 🔄 Eternal automation (runs forever)
echo 4. 🧪 Test browser setup
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo 🌐 Starting local web service...
    echo 💡 Open your browser to: http://%LOCAL_IP%:8080
    echo 💡 Or use: http://localhost:8080
    python web_service.py
) else if "%choice%"=="2" (
    set /p password="Enter Gmail password: "
    echo 📧 Running direct Gmail automation...
    python python_oauth_automation.py --password "%password%" --base-url "http://%LOCAL_IP%:8080"
) else if "%choice%"=="3" (
    set /p password="Enter Gmail password: "
    echo 🔄 Starting eternal automation...
    python eternal_gmail_automation.py --password "%password%" --port 8080
) else if "%choice%"=="4" (
    echo 🧪 Testing browser setup...
    python test_browser_setup.py
) else (
    echo ❌ Invalid choice
    pause
    exit /b 1
)

pause 