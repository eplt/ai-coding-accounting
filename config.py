"""
Configuration file for AI Coding Usage Tracker
You can customize settings here or use environment variables.
"""
import os
from pathlib import Path

# Default SCM path - can be overridden by environment variable
# On each computer, set this to your local SCM directory
# Change this to match your setup, or use environment variable AI_CODING_SCM_PATH
DEFAULT_SCM_PATH = os.path.expanduser("~/SCM")

# Get SCM path from environment variable or use default
SCM_PATH = os.environ.get('AI_CODING_SCM_PATH', DEFAULT_SCM_PATH)

# Ensure the path exists, if not, try to find a common alternative
if not os.path.exists(SCM_PATH):
    # Try common alternatives
    alternatives = [
        os.path.expanduser("~/SCM"),
        os.path.expanduser("~/code"),
        os.path.expanduser("~/projects"),
    ]
    for alt_path in alternatives:
        if os.path.exists(alt_path):
            SCM_PATH = alt_path
            print(f"Warning: {DEFAULT_SCM_PATH} not found, using {SCM_PATH} instead")
            break
    else:
        print(f"Warning: SCM path {SCM_PATH} does not exist. Project detection may not work.")

# Database path - can be customized for shared databases
# Default to Documents/db for iCloud sync
DEFAULT_DB_DIR = os.path.expanduser('~/Documents/db')
os.makedirs(DEFAULT_DB_DIR, exist_ok=True)  # Ensure directory exists
DATABASE_PATH = os.environ.get('AI_CODING_DB_PATH', os.path.join(DEFAULT_DB_DIR, 'ai_usage.db'))

# Other settings
DEBUG = os.environ.get('AI_CODING_DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('AI_CODING_PORT', 5000))
