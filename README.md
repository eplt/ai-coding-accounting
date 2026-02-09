# AI Coding Usage Tracker

A web-based tool for tracking and analyzing AI coding tool usage costs (Cursor, GitHub Copilot, etc.) by project.

Track your AI coding expenses, automatically detect which projects you worked on, and analyze costs by project with an intuitive web interface.

## Features

- **CSV Upload**: Upload billing CSV files from Cursor or other AI coding tools
- **Import from Downloads**: Scan your Downloads folder for recent usage CSVs and import in one click
- **Automatic Deduplication**: Only new entries are added to the database
- **Smart Session Detection**: Groups events into coding sessions (configurable gap, default 2 hours)
- **Auto Project Detection**: Matches sessions to projects using file modification times in your code directory
- **Project Groups**: Organize projects into groups (e.g. Work, Product X)
- **Project Management**: Create, edit, and assign projects; session detail view with per-event project assignment
- **Settings**: Configure database path, session gap, SCM path, and import lookback from the UI (persisted across restarts)
- **Dashboard**: Cost, token usage, and session statistics by project and group
- **Re-detect Sessions**: Re-run session detection with current settings
- **Standalone macOS app**: Double-clickable `.app` with menu bar and floating window (Open in Browser, Settings, Quit)

## Setup

**Quick start (after clone or download):**

```bash
chmod +x setup.sh
./setup.sh
```

This creates a virtual environment, installs dependencies, and on macOS builds the standalone `.app`. To only set up the environment (no app build), run `./setup.sh --dev`.

**Then run the app:**

- **From source:** `source venv/bin/activate && python app.py`
- **Standalone (macOS):** `open "dist/AI Coding Usage Tracker.app"`

Open the UI at `http://localhost:5000` (or the port in Settings / `AI_CODING_PORT`).

**Manual setup (alternative):**

1. `python3 -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. Run: `python app.py` — or on macOS build the .app: `pip install pyinstaller && ./build_standalone.sh` (see [STANDALONE_BUILD.md](STANDALONE_BUILD.md)).

**Configure SCM path (optional):** Default is `~/SCM`. Override via environment variable `AI_CODING_SCM_PATH` or from the app’s Projects section / Settings.

### Database location

- **Default (dev):** `~/Documents/db/ai_usage.db`
- **Default (standalone .app):** `~/Library/Application Support/AI Coding Accounting/db/ai_usage.db`
- **Custom:** Set in **Settings → Database path** (e.g. `~/Documents/db/ai_usage.db`). Takes effect after restart. You can also use `AI_CODING_DB_PATH`.

## Syncing the database (e.g. iCloud)

To use the same database across machines or back it up with iCloud:

1. **Choose a synced folder**  
   Examples: `~/Documents/db` (often included in iCloud Documents), or a folder inside iCloud Drive.

2. **Point the app at it**  
   - **From source:** Set `AI_CODING_DB_PATH` to the DB path, e.g.  
     `export AI_CODING_DB_PATH="$HOME/Documents/db/ai_usage.db"`
   - **From Settings (UI):** Set **Database path** to e.g. `~/Documents/db/ai_usage.db` and click Save. Restart the app.

3. **Create the directory if needed**  
   e.g. `mkdir -p ~/Documents/db`

4. **Caveats**  
   - Avoid opening the same SQLite file from two machines at once; close the app on one before opening on another, or use the DB on a single machine at a time.
   - If you use iCloud, ensure the file is fully synced before opening the app on another device.

## Usage

### Uploading CSV

1. Download usage CSV from Cursor (or your tool).
2. Use **Upload & Process** or **Import from Downloads** (scans `~/Downloads` for recent usage CSVs).
3. Adjust **Session gap** in the form or in Settings if needed.

### Projects and groups

- **+ New Project** / **+ New Group**: Create projects and optional groups.
- **Edit project**: Assign a **Group** (or leave Ungrouped).
- **Auto-Detect Projects**: Match unassigned sessions to repos in your SCM path; apply suggestions as needed.
- **Sessions table**: Assign project per session; open **Details** to edit project per event or unlink from session.
- **Re-detect Sessions**: Re-run session grouping with the current gap setting.

### Settings

- **Session gap (hours)**: Time gap used to split events into sessions.
- **Import from Downloads: look back (hours)**: How far back to look for CSVs in `~/Downloads`.
- **SCM path**: Base folder for project detection.
- **Database path**: SQLite file path (persisted; effective after restart).

## Database

SQLite is created automatically. Default locations:

- Development: `~/Documents/db/ai_usage.db`
- Standalone .app: `~/Library/Application Support/AI Coding Accounting/db/ai_usage.db`

Override via Settings or `AI_CODING_DB_PATH`. Config is stored in `~/Library/Application Support/AI Coding Accounting/app_config.json` (database path and similar).

Main tables: **UsageEvent**, **CodingSession**, **Project**, **ProjectGroup**, **AppSettings**, **ImportBatch**, **EventArchive**.

## CSV format

Expected columns (and optional **User**): Date (ISO), User, Kind, Model, Max Mode, Input (w/ Cache Write), Input (w/o Cache Write), Cache Read, Output Tokens, Total Tokens, Cost.

## Multi-computer

- Use a **shared database** in a synced folder (see [Syncing the database](#syncing-the-database-eg-icloud)) and set the same path on each machine.
- Set **SCM path** per machine (each machine’s local code directory) so project detection uses local paths.

## Documentation

- [STANDALONE_BUILD.md](STANDALONE_BUILD.md) – Build the macOS `.app` (the binary is not in the repo; follow these steps to build your own)
- [SERVICE_SETUP.md](SERVICE_SETUP.md) – Run as a macOS launchd service
- [MULTI_COMPUTER_SETUP.md](MULTI_COMPUTER_SETUP.md) – Shared DB and per-machine config

## License

MIT
