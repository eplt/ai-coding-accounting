# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- **Privacy & Genericization**: Removed all personal information (usernames, specific paths) from codebase
  - All hardcoded paths replaced with generic examples (`~/SCM`, `~/code`, etc.)
  - Documentation updated to be user-agnostic
  - Added note about original use case (personal macOS + Cursor) while keeping it generic

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
