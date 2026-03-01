# AI Coding Usage Tracker - Project Context

## Project Overview

**AI Coding Usage Tracker** is a web-based Flask application for tracking and analyzing AI coding tool usage costs (Cursor, GitHub Copilot, etc.) by project. It provides an intuitive dashboard for managing billing data, detecting coding sessions, and associating them with software projects.

### Core Features
- **CSV Upload & Import**: Upload billing CSVs or scan Downloads folder for recent usage files
- **Smart Session Detection**: Groups events into coding sessions (configurable time gap, default 2 hours)
- **Auto Project Detection**: Matches sessions to projects using file modification times in git repositories
- **Project Management**: Create/edit projects, organize into groups, assign sessions
- **Dashboard**: Cost, token usage, and session statistics by project and group
- **Standalone macOS App**: Double-clickable `.app` with menu bar and floating window

### Technology Stack
- **Backend**: Python 3.8+ with Flask 3.0.0
- **Database**: SQLite (Flask-SQLAlchemy 3.1.1)
- **Frontend**: Vanilla HTML/CSS/JavaScript with Chart.js
- **macOS App**: PyInstaller + rumps (menu bar app framework)

## Project Structure

```
ai-coding-accounting/
├── app.py                 # Main Flask application (1160 lines)
├── config.py              # Configuration management (DB paths, SCM paths, env vars)
├── launch.py              # Entry point for standalone macOS .app
├── project_detector.py    # Auto-detect projects from git repos via file mtimes
├── requirements.txt       # Python dependencies
├── ai-usage-tracker.spec  # PyInstaller build spec
├── templates/
│   └── index.html         # Single-page dashboard UI (1627 lines)
├── uploads/               # CSV upload staging directory
├── instance/              # SQLite database (dev mode default location)
├── build/ dist/           # PyInstaller build outputs
└── venv/                  # Python virtual environment
```

### Database Models (in `app.py`)
- **UsageEvent**: Individual AI usage events from CSV (tokens, cost, model, etc.)
- **CodingSession**: Grouped events within a time window
- **Project**: Software projects to associate with sessions
- **ProjectGroup**: Optional grouping of projects (e.g., "Work", "Product X")
- **AppSettings**: Application configuration
- **ImportBatch**: Track CSV import batches
- **EventArchive**: Raw CSV rows for audit/re-import
- **DatabaseMigration**: Tracks applied schema/data migrations

## Versioning and Migrations

The app uses a versioned migration system for backward-compatible database changes.

### App Version
- Current version: `1.1.0` (in `app.py` as `APP_VERSION`)
- Bump version when adding new migrations

### Migration Framework
- Migrations run automatically on startup (both `app.py` and `launch.py`)
- Each migration is versioned and recorded in `database_migration` table
- Migrations are idempotent - safe to run multiple times

### Adding a New Migration
1. Bump `APP_VERSION` in `app.py`
2. Add migration function: `def _migrate_X_Y_Z_description():`
3. Register in `MIGRATIONS` dict within `_run_database_migrations()`
4. Migration runs once per database on next startup

### Migration 1.1.0: Hash Recalculation
- Recalculates `unique_hash` for all existing `UsageEvent` records
- Old hash included `User` and `Model` fields (caused duplicates)
- New hash uses only timestamp + token counts
- Also removes any duplicate events found during migration

## Building and Running

### Quick Start (Development)
```bash
# One-time setup
chmod +x setup.sh
./setup.sh

# Run from source
source venv/bin/activate
python app.py

# Access UI at http://localhost:5000
```

### Development Mode Only
```bash
./setup.sh --dev  # Skip macOS .app build
```

### Standalone macOS App
```bash
# Build (requires macOS)
./build_standalone.sh

# Run the app
open "dist/AI Coding Usage Tracker.app"
```

### Manual Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Configuration via Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `AI_CODING_PORT` | `5000` | Flask server port |
| `AI_CODING_SCM_PATH` | `~/SCM` | Base path for project detection |
| `AI_CODING_DB_PATH` | See below | SQLite database path |
| `AI_CODING_DEBUG` | `False` | Enable debug logging |

### Database Locations
- **Development**: `~/Documents/db/ai_usage.db`
- **Standalone .app**: `~/Library/Application Support/AI Coding Accounting/db/ai_usage.db`
- **Custom**: Set via Settings UI or `AI_CODING_DB_PATH` environment variable

## Development Conventions

### Code Style
- Follow **PEP 8** for Python code
- Use meaningful variable and function names
- Keep functions focused and small
- Add comments for complex logic (especially session detection, project matching)

### Key Implementation Patterns
- **Database path resolution**: Handled in `config.py` with priority: env var → config file → default
- **Frozen detection**: `getattr(sys, 'frozen', False)` used throughout for PyInstaller bundle paths
- **Session grouping**: Time-gap based algorithm in `app.py` (default 2-hour gap)
- **Project detection**: File modification time matching in `project_detector.py`

### Testing Practices
- Test with sample CSV files before committing changes
- Verify UI works correctly after frontend changes
- Ensure app runs without errors in both dev and frozen modes

### CSV Format Expected
Columns: `Date` (ISO), `User` (optional), `Kind`, `Model`, `Max Mode`, `Input (w/ Cache Write)`, `Input (w/o Cache Write)`, `Cache Read`, `Output Tokens`, `Total Tokens`, `Cost`

## Important Files for Modifications

| File | Purpose | When to Modify |
|------|---------|----------------|
| `app.py` | Flask routes, DB models, CSV processing, session logic, migrations | Adding features, fixing bugs, schema changes |
| `config.py` | Configuration resolution, paths | Adding new config options |
| `project_detector.py` | Git repo scanning, project matching | Improving project detection |
| `templates/index.html` | Dashboard UI, forms, charts | UI/UX changes |
| `launch.py` | macOS app entry point, menu bar | Standalone app behavior |
| `requirements.txt` | Python dependencies | Adding new packages |
| `ai-usage-tracker.spec` | PyInstaller bundling | Build configuration |

## Common Tasks

### Add a New Feature
1. Add route/handler in `app.py`
2. Update `templates/index.html` if UI changes needed
3. Add DB model in `app.py` if data persistence required
4. Test in dev mode: `python app.py`
5. Verify standalone build works: `./build_standalone.sh`

### Change Configuration Defaults
1. Modify `config.py` default values
2. Update README.md documentation
3. Consider backward compatibility for existing users

### Modify Project Detection Logic
1. Edit `project_detector.py`
2. Test with various repo structures
3. Verify session-to-project matching accuracy

## Documentation Files
- `README.md` - User-facing documentation
- `CONTRIBUTING.md` - Contribution guidelines
- `STANDALONE_BUILD.md` - macOS .app build details
- `SERVICE_SETUP.md` - Running as macOS launchd service
- `MULTI_COMPUTER_SETUP.md` - Shared database setup

## Known Platform Notes
- **macOS 26 (Tahoe)**: Menu bar icon may not appear (Apple bug); floating window provided as workaround
- **Gatekeeper**: First launch may require "Open Anyway" in System Settings
- **Debug logs**: Written to `~/Desktop/ai-usage-tracker-launch.log` when frozen
