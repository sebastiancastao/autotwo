#!/bin/bash

# Start Xvfb (X Virtual Framebuffer) for GUI applications
echo "Starting Xvfb virtual display server..."
Xvfb :99 -screen 0 1200x800x16 &
XVFB_PID=$!

# Wait a moment for Xvfb to initialize
sleep 3

# Set display environment variable
export DISPLAY=:99

echo "Xvfb started with PID: $XVFB_PID"
echo "Display set to: $DISPLAY"

# Function to cleanup Xvfb on exit
cleanup() {
    echo "Stopping Xvfb..."
    kill $XVFB_PID 2>/dev/null
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Start the main application
echo "Starting Gmail OAuth Automation Web Service..."
python3 web_service.py

# Keep the script running (this line should not be reached normally)
wait 