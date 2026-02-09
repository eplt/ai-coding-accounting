"""
Configuration for AI Coding Usage Tracker.
Override via environment variables; database path can also be set from the Settings UI.
"""
import json
import os
import sys
from datetime import datetime

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

# App config file (outside DB) - stores database_path so it can be changed from Settings and applied on next launch
# Use HOME explicitly so the path is the same when saving (in request) and when loading (at startup)
_HOME = os.environ.get("HOME") or os.path.expanduser("~")
APP_CONFIG_DIR = os.path.abspath(os.path.join(_HOME, "Library", "Application Support", "AI Coding Accounting"))


def get_app_config_path() -> str:
    """Path to app_config.json (database_path etc.). Same for frozen and dev."""
    try:
        os.makedirs(APP_CONFIG_DIR, exist_ok=True)
    except OSError:
        pass
    return os.path.join(APP_CONFIG_DIR, "app_config.json")


def _config_debug_log(message: str) -> None:
    """When AI_CODING_DEBUG_CONFIG=1, append to config_debug.log for troubleshooting DB path save/load."""
    if os.environ.get("AI_CODING_DEBUG_CONFIG", "").strip() != "1":
        return
    try:
        log_path = os.path.join(APP_CONFIG_DIR, "config_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {message}\n")
    except Exception:
        pass


def _db_dir_from_defaults() -> str:
    """Default DB directory when not overridden by config file or env."""
    if getattr(sys, "frozen", False):
        dirpath = os.path.abspath(os.path.expanduser("~/Library/Application Support/AI Coding Accounting/db"))
    else:
        dirpath = os.path.abspath(os.path.expanduser("~/Documents/db"))
    os.makedirs(dirpath, exist_ok=True)
    return dirpath


def _resolve_database_path() -> str:
    """Resolve DB path: env AI_CODING_DB_PATH, then app_config.json, then default. Env is set by launch from config file before app loads (reliable for standalone .app)."""
    if os.environ.get("AI_CODING_DB_PATH"):
        p = os.path.abspath(os.path.expanduser(os.environ["AI_CODING_DB_PATH"]).strip())
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
        except OSError:
            pass
        _config_debug_log(f"Resolved database_path (from env): {p}")
        return p
    config_path = get_app_config_path()
    _config_debug_log(f"Config file path: {config_path}")
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
            raw = (data.get("database_path") or "").strip()
            if raw:
                p = os.path.abspath(os.path.expanduser(raw))
                try:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                except OSError:
                    pass
                _config_debug_log(f"Resolved database_path (from config file): {p}")
                return p
        except Exception as e:
            _config_debug_log(f"Error reading config: {e}")
    default = os.path.join(_db_dir_from_defaults(), "ai_usage.db")
    _config_debug_log(f"Resolved database_path (default): {default}")
    return default


def write_app_config(updates: dict) -> None:
    """Write keys into app_config.json (e.g. database_path). Merged with existing content."""
    path = get_app_config_path()
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data.update(updates)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    if "database_path" in updates:
        _config_debug_log(f"Saved database_path to config file: {updates['database_path']}")


# Database path - resolved when first needed so config file is read at app init
DEFAULT_DB_DIR = _db_dir_from_defaults()


def get_database_path() -> str:
    """Return database path (from config file, env, or default). Call at app init so saved path is used after restart."""
    return _resolve_database_path()


# For code that already uses config.DATABASE_PATH (e.g. GET /api/settings)
DATABASE_PATH = get_database_path()

# Other settings
DEBUG = os.environ.get('AI_CODING_DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('AI_CODING_PORT', 5000))
