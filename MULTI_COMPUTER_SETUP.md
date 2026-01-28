# Multi-Computer Setup Guide

This guide explains how to use the AI Coding Usage Tracker across multiple computers.

## Scenario

You have multiple computers, each with code in a local directory (e.g., `~/SCM`, `~/code`, or `/path/to/your/projects`), and you want to:
- Upload the same CSV file (from Cursor or other AI coding tools) on each computer
- Have each computer detect projects from its own local code directory
- Optionally share the database across computers

## Setup Options

### Option 1: Separate Database Per Computer (Simplest)

Each computer has its own database and detects from its local files.

**On each computer:**
1. Clone/copy the tool to the computer
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python app.py`
4. Upload your CSV file
5. Click "Auto-Detect Projects" - it will scan that computer's local code directory

**Pros:**
- Simple, no configuration needed
- Each computer's detection is independent
- No sync conflicts

**Cons:**
- Data is separate per computer
- Need to upload CSV on each computer

### Option 2: Shared Database, Local Detection (Recommended)

Use the same database file across computers (via cloud sync), but each computer detects from its own local files.

**Setup:**
1. Choose a cloud-synced folder (Dropbox, iCloud, Google Drive, etc.)
   - Example: `~/Dropbox/ai-coding-accounting/`

2. On Computer 1:
   ```bash
   export AI_CODING_DB_PATH="$HOME/Dropbox/ai-coding-accounting/ai_usage.db"
   export AI_CODING_SCM_PATH="~/SCM"  # or your code directory path
   python app.py
   ```

3. On Computer 2 (and others):
   ```bash
   export AI_CODING_DB_PATH="$HOME/Dropbox/ai-coding-accounting/ai_usage.db"
   export AI_CODING_SCM_PATH="~/SCM"  # or your code directory path
   python app.py
   ```

**Pros:**
- Single source of truth for all usage data
- Each computer detects from its own local files
- All projects and sessions are synced

**Cons:**
- Need to ensure database file syncs properly
- Only one computer should run the app at a time (to avoid database locks)

### Option 3: Custom SCM Path Per Computer

If your SCM directory is in a different location on some computers.

**On Computer 1:**
```bash
export AI_CODING_SCM_PATH="~/SCM"  # or your code directory
python app.py
```

**On Computer 2 (if path is different):**
```bash
export AI_CODING_SCM_PATH="~/code"  # or any other path
python app.py
```

## Configuration Methods

### Method 1: Environment Variables (Recommended)

Set before running:
```bash
export AI_CODING_SCM_PATH="/path/to/your/SCM"
export AI_CODING_DB_PATH="/path/to/database.db"
python app.py
```

Or create a startup script:
```bash
#!/bin/bash
# ~/bin/ai-accounting.sh
export AI_CODING_SCM_PATH="~/SCM"  # Change to your code directory
export AI_CODING_DB_PATH="$HOME/Dropbox/ai-coding-accounting/ai_usage.db"
cd /path/to/ai-coding-accounting
python app.py
```

### Method 2: Edit config.py

Edit `config.py` and change:
```python
DEFAULT_SCM_PATH = "~/SCM"  # Change to your path, e.g., "~/code" or "/path/to/projects"
```

### Method 3: Per-Computer Config Files

Create computer-specific config files:
- `config.macbook.py`
- `config.imac.py`
- `config.laptop.py`

Then import the appropriate one in `app.py` based on hostname.

## Workflow Recommendations

### Recommended Workflow

1. **Primary Computer Setup:**
   - Set up shared database in cloud folder
   - Upload CSV files here
   - Run auto-detection

2. **Secondary Computers:**
   - Point to same database
   - Upload same CSV (deduplication will skip duplicates)
   - Run auto-detection (will detect from local files)

3. **Daily Usage:**
   - Upload new CSV on any computer
   - Run auto-detection on that computer
   - Database syncs via cloud

### CSV Upload Strategy

Since the tool deduplicates entries, you can:
- Upload the same CSV on multiple computers safely
- Only new entries will be added
- Each computer will detect projects from its own local files

## Troubleshooting

### Database Locked Error

If you see "database is locked" errors:
- Only run the app on one computer at a time
- Wait for cloud sync to complete before switching computers
- Consider using Option 1 (separate databases) if this is a problem

### Wrong SCM Path

Check the path shown in the UI (below "Projects" heading). If wrong:
- Verify the path exists: `ls -la ~/SCM` (or your code directory)
- Set environment variable: `export AI_CODING_SCM_PATH="/correct/path"`
- Or use the UI path selector to update it
- Restart the app if needed

### Projects Not Detected

- Verify SCM path is correct (check UI)
- Ensure git repositories exist in that path
- Check browser console for errors
- Check Flask terminal for backend errors

## Example: Dropbox Setup

```bash
# Create shared folder
mkdir -p ~/Dropbox/ai-coding-accounting

# On each computer, create startup script
cat > ~/bin/ai-accounting.sh << 'EOF'
#!/bin/bash
export AI_CODING_DB_PATH="$HOME/Dropbox/ai-coding-accounting/ai_usage.db"
export AI_CODING_SCM_PATH="~/SCM"  # Change to your code directory
cd /path/to/ai-coding-accounting
source venv/bin/activate  # if using virtualenv
python app.py
EOF

chmod +x ~/bin/ai-accounting.sh
```

Then just run `ai-accounting.sh` on any computer!
