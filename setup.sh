#!/usr/bin/env bash
#
# One-time setup for AI Coding Usage Tracker.
# Run after git clone or downloading the repo as zip.
#
# Usage:
#   ./setup.sh          # Create venv, install deps, and build the macOS .app
#   ./setup.sh --dev    # Create venv and install deps only (no .app build)
#
# Then run the app:
#   From source:  source venv/bin/activate && python app.py
#   Standalone:   open "dist/AI Coding Usage Tracker.app"
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_APP=true
if [[ "${1:-}" == "--dev" ]]; then
  BUILD_APP=false
fi

echo "=== AI Coding Usage Tracker – Setup ==="
echo ""

# 1. Find Python 3
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null && python -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
  PYTHON=python
else
  echo "Error: Python 3.8+ is required. Install it from python.org or your package manager."
  exit 1
fi
echo "Using: $PYTHON ($($PYTHON --version 2>&1))"

# 2. Create virtual environment if missing
if [[ -d "venv" ]]; then
  echo "Virtual environment already exists (venv/)."
elif [[ -d ".venv" ]]; then
  echo "Virtual environment already exists (.venv/)."
  echo "Note: build_standalone.sh looks for venv/ or .venv/. Continuing."
else
  echo "Creating virtual environment..."
  "$PYTHON" -m venv venv
  echo "Created venv/."
fi

# 3. Activate and install dependencies
if [[ -d "venv" ]]; then
  source venv/bin/activate
elif [[ -d ".venv" ]]; then
  source .venv/bin/activate
else
  echo "Error: No venv/ or .venv/ found."
  exit 1
fi

echo "Installing dependencies from requirements.txt..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "Dependencies installed."

# 4. Optionally build the standalone .app (macOS)
if [[ "$BUILD_APP" == true ]]; then
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Skipping .app build (macOS only). Run ./build_standalone.sh on macOS to build the app."
  else
    echo ""
    echo "Building standalone macOS app (this may take a minute)..."
    pip install -q pyinstaller
    chmod +x build_standalone.sh
    ./build_standalone.sh
    echo ""
    echo "Done! App bundle: dist/AI Coding Usage Tracker.app"
    echo "Run it: open \"dist/AI Coding Usage Tracker.app\""
  fi
else
  echo ""
  echo "Dev setup only (--dev). To build the .app later on macOS:"
  echo "  source venv/bin/activate"
  echo "  pip install pyinstaller"
  echo "  ./build_standalone.sh"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Run from source:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo "Then open: http://localhost:5000"
echo ""
