#!/bin/bash
# Quit AI Usage Tracker - stops ALL running instances

echo "Quitting ALL AI Usage Tracker instances..."

# Kill ALL Python processes running app.py (force)
pkill -9 -f "python.*app.py" 2>/dev/null

# Kill standalone tracker processes (force)
pkill -9 -f "ai-usage-tracker" 2>/dev/null

# Kill processes on our ports (5000 and 5001)
lsof -ti :5000 | xargs kill -9 2>/dev/null
lsof -ti :5001 | xargs kill -9 2>/dev/null

# Wait a moment
sleep 1

# Check if still running
if pgrep -f "app.py|ai-usage-tracker" > /dev/null; then
    echo "⚠️  Some processes may still be running."
    echo "   Try: pkill -9 -f 'app.py'"
else
    echo "✅ All AI Usage Tracker instances have been stopped."
fi
