#!/bin/bash
# Build the standalone macOS .app for AI Coding Usage Tracker.
# Requires: Python venv with requirements.txt + pyinstaller installed.
# Usage: ./build_standalone.sh
# Output: dist/AI Coding Usage Tracker.app

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use project venv so pyinstaller and dependencies are available
if [[ -d "venv" ]]; then
  source venv/bin/activate
elif [[ -d ".venv" ]]; then
  source .venv/bin/activate
else
  echo "Error: No virtual environment found. Create one first:"
  echo "  python3 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -r requirements.txt"
  echo "  pip install pyinstaller"
  exit 1
fi

if ! command -v pyinstaller &>/dev/null; then
  echo "Error: pyinstaller not found. Install it with:"
  echo "  pip install pyinstaller"
  exit 1
fi

APP_NAME="AI Coding Usage Tracker"
DIST_DIR="dist"
COLLECT_DIR="$DIST_DIR/$APP_NAME"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "Building with PyInstaller..."
pyinstaller --noconfirm ai-usage-tracker.spec

if [[ ! -d "$COLLECT_DIR" ]]; then
  echo "Error: PyInstaller did not create $COLLECT_DIR"
  exit 1
fi

echo "Creating .app bundle..."
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS" "$RESOURCES"

# PyInstaller binary must run from the folder that contains _internal (it looks for Python there).
# Put the one-folder output in Resources; launcher in MacOS exec's it so the app runs.
cp -R "$COLLECT_DIR" "$RESOURCES/"

# Launcher: run the binary from its bundle dir so it finds _internal
cat > "$MACOS/launcher" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE="$DIR/../Resources/AI Coding Usage Tracker"
cd "$BUNDLE" || exit 1
exec "./ai-usage-tracker"
LAUNCHER
chmod +x "$MACOS/launcher"

# Info.plist
cat > "$CONTENTS/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleName</key>
  <string>AI Coding Usage Tracker</string>
  <key>CFBundleIdentifier</key>
  <string>com.ai-coding-accounting.tracker</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
</dict>
</plist>
PLIST

echo "Done. App bundle: $APP_BUNDLE"
echo "You can move it to /Applications or run it from here."
