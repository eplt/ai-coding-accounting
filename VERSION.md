# Version Information

## Current Version: 1.3.0

### v1.3.0 (2026-03-01)
- **Hash-based deduplication fix**: Unique hash now based on timestamp + token counts (not User/Model), preventing duplicates when importing CSVs without User column
- **Database migration system**: Versioned migrations that run automatically on startup; migration 1.1.0 recalculates hashes for existing data
- **Import batch deletion**: Delete import batches from Settings → Import history; removes all associated events and sessions
- **Improved quit functionality**: Floating window Quit button kills ALL running instances; terminal command `quit-ai-usage` available
- **Port changed to 5001**: Avoids conflict with macOS Control Center (which uses port 5000)
- **Orphaned session cleanup**: Automatically removes sessions with no events after batch deletion

### v1.2.0 (2026-02-09)
- **Settings UI**: Database path, session gap, SCM path, Downloads lookback; persisted across restarts.
- **Project groups**: Create groups, assign projects; filter sessions by group.
- **Import from Downloads** and import history in Settings.
- **Session detail**: Per-event project edit and unlink; Re-detect Sessions button.
- **Standalone app**: DB path from config file; floating window (Open in Browser, Settings, Quit).
- **Generic repo**: No personal paths/usernames; plist uses `REPLACE_ME_PROJECT_DIR`.

### v1.1.1
- Privacy & genericization: all paths and docs generic for any user.

### v1.1.0
- Model info in sessions, project edit/delete, SCM path UI, empty project filtering, multi-computer and iCloud DB support, timezone handling, recursive scanning, file mtime detection.
