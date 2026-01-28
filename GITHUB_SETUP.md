# GitHub Repository Setup

This document lists what files should be committed to GitHub.

## Files to Commit

### Core Application Files
- `app.py` - Main Flask application
- `config.py` - Configuration file
- `project_detector.py` - Project detection module
- `migrate_timezones.py` - Timezone migration script (optional utility)

### Frontend
- `templates/index.html` - Web UI

### Configuration & Documentation
- `requirements.txt` - Python dependencies
- `README.md` - Main documentation
- `LICENSE` - MIT License
- `CONTRIBUTING.md` - Contribution guidelines
- `MULTI_COMPUTER_SETUP.md` - Multi-computer setup guide
- `.gitignore` - Git ignore rules
- `.gitattributes` - Git attributes for line endings

### GitHub Actions (Optional)
- `.github/workflows/python-check.yml` - Basic Python linting workflow

## Files NOT to Commit (Already in .gitignore)

- `venv/` - Virtual environment
- `__pycache__/` - Python cache files
- `*.db` - Database files
- `instance/` - Flask instance folder (may contain database)
- `uploads/` - Uploaded CSV files
- `.DS_Store` - macOS system files
- `*.csv` - CSV files

## Initial Git Setup

```bash
# Initialize git repository
git init

# Add all files (respecting .gitignore)
git add .

# Create initial commit
git commit -m "Initial commit: AI Coding Usage Tracker"

# Add remote (replace with your GitHub repo URL)
git remote add origin https://github.com/yourusername/ai-coding-accounting.git

# Push to GitHub
git push -u origin main
```

## Before Pushing

1. **Check for sensitive data:**
   - No API keys or secrets
   - No personal information in code
   - Database files are ignored

2. **Verify .gitignore is working:**
   ```bash
   git status
   # Should NOT show venv/, *.db, uploads/, etc.
   ```

3. **Test the application:**
   - Make sure it runs: `python app.py`
   - Test CSV upload
   - Test project detection

## Repository Structure

```
ai-coding-accounting/
├── .github/
│   └── workflows/
│       └── python-check.yml
├── templates/
│   └── index.html
├── .gitignore
├── .gitattributes
├── app.py
├── config.py
├── project_detector.py
├── migrate_timezones.py
├── requirements.txt
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── MULTI_COMPUTER_SETUP.md
└── GITHUB_SETUP.md (this file)
```

## Notes

- The default database path is `~/Documents/db/ai_usage.db` (for iCloud sync)
- Users should configure their own SCM path via environment variable or UI
- All hardcoded user-specific paths have been removed or made configurable
