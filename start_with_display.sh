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

# Start Xvfb (X Virtual Framebuffer) for GUI applications
echo "🖥️ Starting Xvfb virtual display server..."
Xvfb :99 -screen 0 1200x800x24 -ac -nolisten tcp -dpi 96 &
XVFB_PID=$!

# Wait for Xvfb to initialize
echo "⏳ Waiting for Xvfb to initialize..."
sleep 5

# Set display environment variable
export DISPLAY=:99

echo "✅ Xvfb started with PID: $XVFB_PID"
echo "🖼️ Display set to: $DISPLAY"

# Verify Xvfb is running
if ps -p $XVFB_PID > /dev/null; then
    echo "✅ Xvfb is running successfully"
else
    echo "❌ Xvfb failed to start"
    exit 1
fi

# Test X11 connection
echo "🔍 Testing X11 connection..."
if command -v xdpyinfo &> /dev/null; then
    xdpyinfo -display :99 | head -5 || echo "⚠️ X11 test failed but continuing..."
else
    echo "ℹ️ xdpyinfo not available, skipping X11 test"
fi

# Function to cleanup Xvfb on exit
cleanup() {
    echo "🛑 Stopping Xvfb..."
    kill $XVFB_PID 2>/dev/null
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