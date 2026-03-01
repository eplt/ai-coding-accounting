# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.3.0] – 2026-03-01

### Added
- **Database migration framework**: Versioned migrations with `DatabaseMigration` table; migrations run automatically on app startup (both source and standalone .app)
- **Import batch deletion**: Delete button in Settings → Import history; removes all events and sessions from a batch, allowing re-import
- **Quit script**: `quit-ai-usage` terminal command to kill all running instances
- **Floating window improvements**: Shows server URL, larger buttons with icons, Cmd+Q keyboard shortcut

### Changed
- **Deduplication hash format**: Changed from `Date + User + Model + TotalTokens + Cost` to `Date + InputTokens + CacheRead + OutputTokens + TotalTokens`
  - Fixes duplicates when importing CSVs without User column
  - Hash now based purely on timestamp and token counts
- **Default port changed to 5001**: Avoids conflict with macOS Control Center (uses port 5000)
- **Delete function matches by data, not hash**: Uses date + token counts to find events, handles hash format changes between versions
- **Migration 1.1.0**: Automatically recalculates hashes for all existing UsageEvent records and removes duplicates

### Fixed
- **Duplicate events on re-import**: CSV imports without User column no longer create duplicates
- **Orphaned sessions**: Sessions with no events are automatically cleaned up after batch deletion or migration
- **Quit button now kills all instances**: Previously only quit the current instance, leaving others running
- **Hash mismatch on delete**: Delete function now matches events by data fields instead of hash, handling format changes

### Technical
- Added `APP_VERSION = "1.3.0"` and `DatabaseMigration` model in `app.py`
- Added `_run_database_migrations()` function with extensible MIGRATIONS dict
- Added `_calculate_hash_from_event()` for consistent hash calculation from DB records
- Updated `create_unique_hash()` to use token-based fields
- Updated `delete_import_batch()` endpoint to match by data fields and delete all duplicates
- Changed default `PORT` in `config.py` from 5000 to 5001
- Updated `launch.py` quit handler to use subprocess for killing all instances

## [1.2.0] – 2026-02-09

### Added
- **Settings UI**: Database path, session gap, SCM path, and Downloads lookback configurable from the app; persisted in `~/Library/Application Support/AI Coding Accounting/app_config.json` (DB path applied on restart).
- **Project groups**: Create groups, assign projects to groups, filter sessions by group; optional `project_group` table and `project.group_id` (auto-migrated for existing DBs).
- **Import from Downloads**: Button to scan `~/Downloads` for recent usage/team CSVs and import in one click.
- **Import history**: List of recent import batches in Settings.
- **Session detail**: Expand a session to see events, change project per event, or unlink from session; session totals update when events are unlinked.
- **Re-detect Sessions**: Button to re-run session detection with current gap setting.
- **Standalone app**: Floating window with Open in Browser, Settings, and Quit; DB path from config file applied on launch.
- **Optional User column**: CSV import supports files with or without a User column.
- **Debug**: `GET /api/debug-db` (only when `AI_CODING_DEBUG=true`) and optional config logging when `AI_CODING_DEBUG_CONFIG=1`.

### Changed
- **Privacy & genericization**: Plist and install script use placeholder `REPLACE_ME_PROJECT_DIR`; no usernames or personal paths in repo. SERVICE_SETUP and PRIVACY_CLEANUP docs updated.
- Database path can be set from Settings and is stored outside the DB so it applies on next start.
- Dashboard stats and project list include group info; projects section shows groups and ungrouped.
- Session filter by group in the sessions table.

### Fixed
- Standalone app now uses the database path saved in Settings after restart (launch sets `AI_CODING_DB_PATH` from config before loading app).
- Schema migration adds `project.group_id` for databases created before project groups (no manual migration needed).
- Dashboard 500 when `project` table lacked `group_id`; stats endpoint tolerant of missing column and returns error details on failure.

### Documentation
- README: iCloud/sync section, Settings, project groups, standalone app, generic paths only.
- README database section: default paths and config file location.

---

## [1.1.1]

### Changed
- **Privacy & genericization**: Removed all personal information (usernames, specific paths) from codebase; documentation user-agnostic.

### Added
- Model information display in sessions table - shows which AI models were used in each session
- Project editing functionality - edit project names and descriptions
- Project deletion functionality - delete projects with confirmation, automatically unassigns sessions
- SCM path selector UI - change the base folder for auto-detection without restarting
- Empty project filtering - charts and project lists only show projects with actual usage data
- Improved browse folder functionality - better path extraction and auto-update
- Database path configuration - defaults to `~/Documents/db/ai_usage.db` for iCloud sync
- Configuration API endpoint - view current SCM path and database settings
- Multi-computer setup guide - comprehensive guide for using across multiple machines

### Changed
- Default SCM path now uses `~/SCM` instead of hardcoded path
- Project detection now uses file modification times instead of git commits (works without commits)
- Timezone handling - all dates stored and displayed in local timezone
- Session detection improved - recursive scanning of subfolders
- Auto-detection now scans all directories, not just git repos

### Fixed
- Browse folder path extraction and auto-update
- Timezone conversion issues (CSV UTC times now properly converted to local)
- Empty projects appearing in charts
- Project deletion now properly unassigns sessions

### Technical
- Added project editing/deletion API endpoints
- Improved error handling and logging
- Better UI feedback with loading states
- Code refactoring for multi-computer support

## [Initial Release]

### Features
- CSV upload with automatic deduplication
- Smart session detection based on time gaps
- Automatic project detection from file modifications
- Project management and assignment
- Dashboard with cost analytics
- Visual charts showing cost distribution
