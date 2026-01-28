# Pre-Commit Checklist

## ✅ Files to Commit

### Modified Files
- `app.py` - Added model info to sessions, project editing/deletion, improved error handling
- `templates/index.html` - Added model column, project edit/delete UI, improved browse folder, empty project filtering

### New Files (if any)
- `CHANGELOG.md` - Change log documenting all updates

## ✅ Security Check

- [x] No API keys or secrets in code
- [x] No hardcoded passwords
- [x] No personal information (emails, etc.) in code
- [x] Database files are in .gitignore
- [x] Uploaded CSV files are in .gitignore

## ✅ Ignored Files (Should NOT be committed)

- [x] `venv/` - Virtual environment (ignored)
- [x] `instance/` - Database files (ignored)
- [x] `uploads/` - Uploaded CSV files (ignored)
- [x] `__pycache__/` - Python cache (ignored)
- [x] `*.db` - Database files (ignored)

## ✅ Code Quality

- [x] No syntax errors
- [x] No TODO/FIXME comments left in code
- [x] Code follows consistent style
- [x] All features tested locally

## 📝 Commit Message Suggestion

```
feat: Add model info, project editing, and improved UI

- Add model information display in sessions table
- Add project editing and deletion functionality
- Improve browse folder path selection
- Filter empty projects from charts
- Add SCM path selector UI
- Improve timezone handling and error messages
- Update database path to ~/Documents/db for iCloud sync
```

## 🚀 Push Commands

```bash
# Stage changes
git add app.py templates/index.html CHANGELOG.md

# Commit with descriptive message
git commit -m "feat: Add model info, project editing, and improved UI

- Add model information display in sessions table
- Add project editing and deletion functionality  
- Improve browse folder path selection
- Filter empty projects from charts
- Add SCM path selector UI
- Improve timezone handling and error messages
- Update database path to ~/Documents/db for iCloud sync"

# Push to GitHub
git push origin master
```
