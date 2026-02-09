#!/bin/bash
# Install script for AI Coding Usage Tracker macOS service

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_NAME="com.ai-coding-accounting.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Installing AI Coding Usage Tracker service..."

# Check if start.sh exists and is executable
if [ ! -f "$SCRIPT_DIR/start.sh" ]; then
    echo "Error: start.sh not found!"
    exit 1
fi

chmod +x "$SCRIPT_DIR/start.sh"

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Generate plist with actual project path and install to LaunchAgents (repo plist unchanged)
echo "Installing plist to ~/Library/LaunchAgents/..."
sed "s|REPLACE_ME_PROJECT_DIR|$SCRIPT_DIR|g" "$PLIST_SOURCE" > "$PLIST_DEST"

# Load the service
echo "Loading service..."
launchctl load "$PLIST_DEST" 2>/dev/null || launchctl load -w "$PLIST_DEST"

echo ""
echo "✅ Service installed successfully!"
echo ""
echo "To start the service:"
echo "  launchctl start com.ai-coding-accounting"
echo ""
echo "To stop the service:"
echo "  launchctl stop com.ai-coding-accounting"
echo ""
echo "To check if it's running:"
echo "  launchctl list | grep ai-coding-accounting"
echo ""
echo "To view logs:"
echo "  tail -f $SCRIPT_DIR/logs/service.log"
echo ""
echo "The service will automatically restart if it crashes."
echo "To enable auto-start on login, edit the plist and set RunAtLoad to true."
