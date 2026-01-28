# AI Coding Usage Tracker

A web-based tool for tracking and analyzing AI coding tool usage costs (Cursor, GitHub Copilot, etc.) by project.

**Note:** This tool was originally built for personal use on macOS with Cursor, but is designed to work with any AI coding tool that provides CSV export functionality.

Track your AI coding expenses, automatically detect which projects you worked on, and analyze costs by project with an intuitive web interface.

## Features

- **CSV Upload**: Upload billing CSV files from Cursor or other AI coding tools
- **Automatic Deduplication**: Only new entries are added to the database
- **Smart Session Detection**: Automatically groups events into coding sessions based on time gaps (configurable, default 2 hours)
- **Auto Project Detection**: Automatically detects which project folder corresponds to each coding session by analyzing file modification times in your configured code directory
- **Project Management**: Create and assign projects to sessions for better organization
- **Dashboard**: View cost, token usage, and session statistics by project
- **Visual Analytics**: Charts showing cost distribution across projects

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure SCM path (optional):**
   
   The default SCM path is `~/SCM`. To use a different path:
   
   **Option A: Environment variable (recommended)**
   ```bash
   export AI_CODING_SCM_PATH="/path/to/your/code"
   python app.py
   ```
   
   **Option B: Edit config.py**
   Edit `config.py` and change `DEFAULT_SCM_PATH` to your local path.
   
   **Option C: Use the UI**
   After starting the app, use the path selector in the Projects section to choose your base folder.
   
   **Option D: Use a shared database with different paths**
   If you want to use the same database file across computers but detect projects on each computer's local files:
   ```bash
   export AI_CODING_DB_PATH="/path/to/shared/ai_usage.db"
   export AI_CODING_SCM_PATH="/path/to/local/code"  # Local path on each computer
   python app.py
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Access the web interface:**
   Open your browser and navigate to `http://localhost:5000`

## Multi-Computer Usage

If you work on multiple computers:

1. **Same CSV, different local files:**
   - Upload the same CSV file on each computer
   - Each computer will detect projects from its own local code directory
   - The database can be shared (via cloud sync) or kept separate per computer

2. **Shared database (optional):**
   - Place the database file in a cloud-synced folder (Dropbox, iCloud, etc.)
   - Set `AI_CODING_DB_PATH` to point to the shared database
   - Each computer will use the same database but detect from its local files

3. **Per-computer configuration:**
   - Each computer can have its own `config.py` or use environment variables
   - The SCM path will automatically use the local directory on each machine

## Usage

### Uploading CSV Files

1. Download your usage CSV file from Cursor (or other tool)
2. Click "Select CSV File" and choose your file
3. Adjust the "Session Gap" if needed (default: 2 hours)
   - Events within this time gap will be grouped into the same session
4. Click "Upload & Process"
5. The system will:
   - Deduplicate entries (based on date, user, model, tokens, and cost)
   - Create coding sessions automatically
   - Show you how many new events were added

### Managing Projects

1. Click "+ New Project" to create a project manually
2. **Auto-Detect Projects**: Click "🔍 Auto-Detect Projects" to automatically match sessions to projects
   - The system scans all git repositories in your configured base folder
   - Matches sessions to projects based on file modification times
   - Shows confidence scores and file modification counts
   - You can review suggestions before applying them
   - Use the path selector to change which folder to scan
3. Assign sessions to projects using the dropdown in the Sessions table
4. View project statistics in the Projects section

### Auto-Detection Algorithm

The auto-detection feature works by:
- Scanning all git repositories and directories in your configured base folder
- Checking file modification times (mtime) within each session's time window (with a 30-minute buffer)
- Calculating confidence scores based on:
  - Number of files modified during the session
  - Files modified very close to session start time (bonus points)
  - Files modified exactly during the session window
  - Git commits (if available) as secondary indicators
- Only suggesting matches with confidence score ≥ 5
- Creating projects automatically from folder names when applying suggestions
- Works even if files aren't committed to git

### Understanding Sessions

Sessions are automatically detected by grouping events that occur within a specified time gap (default 2 hours). For example:
- Event at 10:00 AM
- Event at 10:30 AM
- Event at 11:00 AM
- Event at 2:00 PM (3 hours later)

This would create 2 sessions:
- Session 1: 10:00 AM - 11:00 AM (3 events)
- Session 2: 2:00 PM (1 event)

## Database

The application uses SQLite which is created automatically on first run. By default, the database is stored at `~/Documents/db/ai_usage.db` (for iCloud sync on macOS). You can customize this with the `AI_CODING_DB_PATH` environment variable.

The database contains:

- **UsageEvent**: Individual usage events from CSV files
- **CodingSession**: Grouped sessions of related events
- **Project**: User-created projects for organizing sessions

## CSV Format

The tool expects CSV files with the following columns:
- Date (ISO format)
- User
- Kind
- Model
- Max Mode
- Input (w/ Cache Write)
- Input (w/o Cache Write)
- Cache Read
- Output Tokens
- Total Tokens
- Cost

## About

This tool was originally built for personal use on macOS with Cursor, but is designed to be generic and work with:
- **Cursor** (primary use case)
- **GitHub Copilot** (if CSV export is available)
- **Other AI coding tools** that provide CSV export functionality

The tool is designed to work on macOS (with iCloud sync support) but should work on Linux and Windows as well with appropriate path configuration.

## Future Enhancements

Potential improvements:
- Export reports (PDF, CSV)
- Time-based filtering and date range selection
- More detailed analytics (cost per hour, token efficiency)
- Support for multiple users/teams
- Integration with other AI coding tools (API-based, not just CSV)
- Automatic project detection based on file patterns or git repos
- Support for Windows and Linux path conventions

## License

MIT
