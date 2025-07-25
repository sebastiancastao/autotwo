#!/bin/bash
# Gmail OAuth Automation - Unix/Linux Launcher
# This script provides easy ways to run the OAuth automation tool

echo ""
echo "========================================"
echo "   Gmail OAuth Automation Launcher"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python is not installed or not in PATH"
        echo "Please install Python 3.7+ and try again"
        exit 1
    else
        PYTHON=python
    fi
else
    PYTHON=python3
fi

echo "Using Python: $($PYTHON --version)"

# Check if required files exist
if [ ! -f "oauth_automation.py" ]; then
    echo "ERROR: oauth_automation.py not found"
    echo "Please make sure you're running this from the correct directory"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found"
    exit 1
fi

# Check if dependencies are installed
$PYTHON -c "import selenium, requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt || pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo "Select an option:"
echo ""
echo "1. Run OAuth automation (visible browser)"
echo "2. Run OAuth automation (headless mode)"
echo "3. Run OAuth automation with password"
echo "4. Start trigger server"
echo "5. Run in debug mode"
echo "6. Install/Update dependencies"
echo "7. Show help"
echo "8. Exit"
echo ""

read -p "Enter your choice (1-8): " choice

case $choice in
    1)
        echo "Running OAuth automation with visible browser..."
        $PYTHON oauth_automation.py
        ;;
    2)
        echo "Running OAuth automation in headless mode..."
        $PYTHON oauth_automation.py --headless
        ;;
    3)
        read -p "Enter password (or leave empty): " -s password
        echo ""
        if [ -n "$password" ]; then
            echo "Running OAuth automation with password..."
            $PYTHON oauth_automation.py --password "$password"
        else
            echo "Running OAuth automation without password..."
            $PYTHON oauth_automation.py
        fi
        ;;
    4)
        echo "Starting trigger server on port 9999..."
        echo "You can trigger OAuth by sending POST requests to http://localhost:9999/trigger-oauth"
        $PYTHON oauth_automation.py --server --trigger-port 9999
        ;;
    5)
        echo "Running OAuth automation in debug mode..."
        $PYTHON oauth_automation.py --debug
        ;;
    6)
        echo "Installing/Updating dependencies..."
        pip3 install -r requirements.txt --upgrade || pip install -r requirements.txt --upgrade
        ;;
    7)
        $PYTHON oauth_automation.py --help
        ;;
    8)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice. Please try again."
        exit 1
        ;;
esac

echo ""
echo "Script completed." 