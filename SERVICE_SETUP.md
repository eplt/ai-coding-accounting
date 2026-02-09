# Running as a macOS Service

This guide shows you how to run the AI Coding Usage Tracker as a background service on macOS.

## Quick Install (Recommended)

**Easiest way - just run:**
```bash
./install-service.sh
```

This will automatically:
- Set up the service
- Install it to LaunchAgents
- Start it for you

Then access the app at: http://localhost:5000

## Option 1: Launchd Service (Recommended)

This runs the app as a background service that can start automatically and restart if it crashes.

### Quick Setup

Run the install script:
```bash
./install-service.sh
```

### Manual Setup Steps

1. **Make the startup script executable:**
   ```bash
   chmod +x start.sh
   ```

2. **Create logs directory:**
   ```bash
   mkdir -p logs
   ```

3. **Install the plist** (the install script does this for you; for manual install):
   ```bash
   # The plist uses placeholder REPLACE_ME_PROJECT_DIR; substitute your project path:
   sed "s|REPLACE_ME_PROJECT_DIR|$(pwd)|g" com.ai-coding-accounting.plist > ~/Library/LaunchAgents/com.ai-coding-accounting.plist
   launchctl load ~/Library/LaunchAgents/com.ai-coding-accounting.plist
   ```

### Managing the Service

**Start the service:**
```bash
launchctl start com.ai-coding-accounting
```

**Stop the service:**
```bash
launchctl stop com.ai-coding-accounting
```

**Check if it's running:**
```bash
launchctl list | grep ai-coding-accounting
```

**View logs:**
```bash
tail -f logs/service.log
tail -f logs/service.error.log
```

**Unload the service (to stop it permanently):**
```bash
launchctl unload ~/Library/LaunchAgents/com.ai-coding-accounting.plist
```

**Enable auto-start on login:**
- Edit the installed plist: `~/Library/LaunchAgents/com.ai-coding-accounting.plist`
- Change `<false/>` to `<true/>` for `RunAtLoad`
- Reload: `launchctl unload ~/Library/LaunchAgents/com.ai-coding-accounting.plist && launchctl load ~/Library/LaunchAgents/com.ai-coding-accounting.plist`

## Option 2: Simple Shell Script (Quick Start)

For a simpler approach, create a desktop shortcut:

1. **Create a simple launcher script** (replace `/path/to/ai-coding-accounting` with your clone path):
   ```bash
   mkdir -p ~/bin
   cat > ~/bin/ai-accounting.sh << 'EOF'
   #!/bin/bash
   cd /path/to/ai-coding-accounting
   source venv/bin/activate
   python app.py
   EOF
   chmod +x ~/bin/ai-accounting.sh
   ```

2. **Create an Automator app:**
   - Open Automator
   - Choose "Application"
   - Add "Run Shell Script" action
   - Paste: `~/bin/ai-accounting.sh`
   - Save as "AI Accounting" in Applications
   - Now you can double-click to start

## Option 3: Terminal Alias (Simplest)

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
# Replace /path/to/ai-coding-accounting with your project directory
alias ai-accounting='cd /path/to/ai-coding-accounting && source venv/bin/activate && python app.py'
```

Then just type `ai-accounting` in terminal.

## Option 4: Background Process (No Service)

Run in background and detach:

```bash
cd /path/to/ai-coding-accounting
source venv/bin/activate
nohup python app.py > logs/app.log 2>&1 &
```

To stop it later:
```bash
pkill -f "python app.py"
```

## Recommended: Launchd Service

The launchd service (Option 1) is recommended because:
- ✅ Runs in background automatically
- ✅ Restarts if it crashes
- ✅ Can auto-start on login (optional)
- ✅ Proper logging
- ✅ Easy to manage

## Troubleshooting

**Service won't start:**
- Check logs: `tail -f logs/service.error.log`
- Verify paths in plist file are correct
- Make sure `start.sh` is executable: `chmod +x start.sh`
- Check virtual environment exists

**Port already in use:**
- Change port in `config.py` or set `AI_CODING_PORT` environment variable
- Or stop the existing process: `lsof -ti:5000 | xargs kill`

**Service keeps restarting:**
- Check error logs to see why it's crashing
- Verify all dependencies are installed in venv
