#!/bin/bash

echo "🚀 Starting Gmail OAuth Automation with Virtual Display Support"

# Check if we're in a Docker environment
if [ -f /.dockerenv ]; then
    echo "🐳 Running in Docker container"
else
    echo "💻 Running in local environment"
fi

# Kill any existing Xvfb processes
echo "🧹 Cleaning up any existing Xvfb processes..."
pkill -f Xvfb || true

# Wait for processes to fully terminate
sleep 2

# Remove any leftover lock files for display 99
echo "🧽 Removing any leftover X11 lock files..."
rm -f /tmp/.X99-lock || true
rm -f /tmp/.X11-unix/X99 || true

# Ensure display 99 is not in use
if ps aux | grep -v grep | grep "Xvfb :99" > /dev/null; then
    echo "⚠️ Display :99 still in use, trying to force cleanup..."
    pkill -9 -f "Xvfb :99" || true
    sleep 2
    rm -f /tmp/.X99-lock || true
    rm -f /tmp/.X11-unix/X99 || true
fi

# Start Xvfb (X Virtual Framebuffer) for GUI applications
echo "🖥️ Starting Xvfb virtual display server..."
Xvfb :99 -screen 0 1200x800x24 -ac -nolisten tcp -dpi 96 > /dev/null 2>&1 &
XVFB_PID=$!

# Wait for Xvfb to initialize
echo "⏳ Waiting for Xvfb to initialize..."
sleep 5

# Set display environment variable
export DISPLAY=:99

# Verify Xvfb actually started and is running
if ! ps -p $XVFB_PID > /dev/null; then
    echo "❌ Xvfb failed to start (process not running)"
    echo "🔍 Checking for errors..."
    # Try to start again with error output visible
    Xvfb :99 -screen 0 1200x800x24 -ac -nolisten tcp -dpi 96 &
    XVFB_PID=$!
    sleep 3
    if ! ps -p $XVFB_PID > /dev/null; then
        echo "❌ Xvfb still failed to start. Trying different display..."
        # Try display 98 as fallback
        Xvfb :98 -screen 0 1200x800x24 -ac -nolisten tcp -dpi 96 > /dev/null 2>&1 &
        XVFB_PID=$!
        export DISPLAY=:98
        sleep 3
        if ! ps -p $XVFB_PID > /dev/null; then
            echo "❌ Failed to start Xvfb on any display"
            exit 1
        else
            echo "✅ Xvfb started on display :98 with PID: $XVFB_PID"
        fi
    else
        echo "✅ Xvfb started on display :99 with PID: $XVFB_PID"
    fi
else
    echo "✅ Xvfb started with PID: $XVFB_PID"
fi

echo "🖼️ Display set to: $DISPLAY"

# Test X11 connection
echo "🔍 Testing X11 connection..."
if command -v xdpyinfo &> /dev/null; then
    if xdpyinfo -display $DISPLAY > /dev/null 2>&1; then
        echo "✅ X11 connection test passed"
        xdpyinfo -display $DISPLAY | head -5 || true
    else
        echo "⚠️ X11 test failed but continuing..."
    fi
else
    echo "ℹ️ xdpyinfo not available, skipping X11 test"
fi

# Function to cleanup Xvfb on exit
cleanup() {
    echo "🛑 Stopping Xvfb..."
    kill $XVFB_PID 2>/dev/null || true
    sleep 2
    # Force kill if still running
    kill -9 $XVFB_PID 2>/dev/null || true
    # Clean up lock files
    rm -f /tmp/.X99-lock 2>/dev/null || true
    rm -f /tmp/.X98-lock 2>/dev/null || true
    rm -f /tmp/.X11-unix/X99 2>/dev/null || true
    rm -f /tmp/.X11-unix/X98 2>/dev/null || true
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Show environment info
echo "🌐 Environment variables:"
echo "   DISPLAY=$DISPLAY"
echo "   ENVIRONMENT=${ENVIRONMENT:-'not set'}"
echo "   BROWSER_HEADLESS=${BROWSER_HEADLESS:-'not set'}"
echo "   PORT=${PORT:-'not set'}"

# Start the main application
echo "🚀 Starting Gmail OAuth Automation Web Service..."
python3 web_service.py

# Keep the script running (this line should not be reached normally)
wait 