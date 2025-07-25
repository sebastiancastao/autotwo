@echo off
REM Gmail OAuth Automation - Windows Launcher
REM This script provides easy ways to run the OAuth automation tool

echo.
echo ========================================
echo    Gmail OAuth Automation Launcher
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Check if required files exist
if not exist "oauth_automation.py" (
    echo ERROR: oauth_automation.py not found
    echo Please make sure you're running this from the correct directory
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import selenium, requests" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo Select an option:
echo.
echo 1. Run OAuth automation (visible browser)
echo 2. Run OAuth automation (headless mode)
echo 3. Run OAuth automation with password
echo 4. Start trigger server
echo 5. Run in debug mode
echo 6. Install/Update dependencies
echo 7. Show help
echo 8. Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" (
    echo Running OAuth automation with visible browser...
    python oauth_automation.py
) else if "%choice%"=="2" (
    echo Running OAuth automation in headless mode...
    python oauth_automation.py --headless
) else if "%choice%"=="3" (
    set /p password="Enter password (or leave empty): "
    if not "%password%"=="" (
        echo Running OAuth automation with password...
        python oauth_automation.py --password "%password%"
    ) else (
        echo Running OAuth automation without password...
        python oauth_automation.py
    )
) else if "%choice%"=="4" (
    echo Starting trigger server on port 9999...
    echo You can trigger OAuth by sending POST requests to http://localhost:9999/trigger-oauth
    python oauth_automation.py --server --trigger-port 9999
) else if "%choice%"=="5" (
    echo Running OAuth automation in debug mode...
    python oauth_automation.py --debug
) else if "%choice%"=="6" (
    echo Installing/Updating dependencies...
    pip install -r requirements.txt --upgrade
) else if "%choice%"=="7" (
    python oauth_automation.py --help
) else if "%choice%"=="8" (
    echo Goodbye!
    exit /b 0
) else (
    echo Invalid choice. Please try again.
    pause
    goto :eof
)

echo.
echo Script completed.
pause 