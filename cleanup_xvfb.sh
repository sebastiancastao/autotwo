#!/bin/bash

echo "🧹 Xvfb Cleanup Utility"
echo "========================"

# Kill all Xvfb processes
echo "🔍 Checking for running Xvfb processes..."
if ps aux | grep -v grep | grep Xvfb > /dev/null; then
    echo "📋 Found running Xvfb processes:"
    ps aux | grep -v grep | grep Xvfb
    echo ""
    echo "🛑 Killing all Xvfb processes..."
    pkill -f Xvfb || true
    sleep 2
    
    # Force kill if any are still running
    if ps aux | grep -v grep | grep Xvfb > /dev/null; then
        echo "⚡ Force killing stubborn Xvfb processes..."
        pkill -9 -f Xvfb || true
        sleep 2
    fi
else
    echo "✅ No running Xvfb processes found"
fi

# Clean up lock files
echo "🧽 Cleaning up X11 lock files..."
lock_files_removed=0

if [ -f "/tmp/.X99-lock" ]; then
    rm -f /tmp/.X99-lock && echo "   🗑️ Removed /tmp/.X99-lock" && lock_files_removed=$((lock_files_removed + 1))
fi

if [ -f "/tmp/.X98-lock" ]; then
    rm -f /tmp/.X98-lock && echo "   🗑️ Removed /tmp/.X98-lock" && lock_files_removed=$((lock_files_removed + 1))
fi

if [ -f "/tmp/.X11-unix/X99" ]; then
    rm -f /tmp/.X11-unix/X99 && echo "   🗑️ Removed /tmp/.X11-unix/X99" && lock_files_removed=$((lock_files_removed + 1))
fi

if [ -f "/tmp/.X11-unix/X98" ]; then
    rm -f /tmp/.X11-unix/X98 && echo "   🗑️ Removed /tmp/.X11-unix/X98" && lock_files_removed=$((lock_files_removed + 1))
fi

# Clean up any other X lock files (X0-X100)
for i in {0..100}; do
    if [ -f "/tmp/.X${i}-lock" ]; then
        rm -f "/tmp/.X${i}-lock" && echo "   🗑️ Removed /tmp/.X${i}-lock" && lock_files_removed=$((lock_files_removed + 1))
    fi
    if [ -f "/tmp/.X11-unix/X${i}" ]; then
        rm -f "/tmp/.X11-unix/X${i}" && echo "   🗑️ Removed /tmp/.X11-unix/X${i}" && lock_files_removed=$((lock_files_removed + 1))
    fi
done

if [ $lock_files_removed -eq 0 ]; then
    echo "✅ No lock files found to remove"
else
    echo "✅ Removed $lock_files_removed lock files"
fi

# Final verification
echo ""
echo "🔍 Final verification..."
if ps aux | grep -v grep | grep Xvfb > /dev/null; then
    echo "⚠️ Warning: Some Xvfb processes are still running:"
    ps aux | grep -v grep | grep Xvfb
else
    echo "✅ All Xvfb processes have been terminated"
fi

# Check for remaining lock files
remaining_locks=$(find /tmp -name ".X*-lock" 2>/dev/null | wc -l)
if [ $remaining_locks -gt 0 ]; then
    echo "⚠️ Warning: $remaining_locks X11 lock files still exist in /tmp"
    find /tmp -name ".X*-lock" 2>/dev/null
else
    echo "✅ All X11 lock files have been cleaned up"
fi

echo ""
echo "🎉 Cleanup completed! You can now restart your automation."
echo "💡 To run this cleanup anytime: chmod +x cleanup_xvfb.sh && ./cleanup_xvfb.sh" 