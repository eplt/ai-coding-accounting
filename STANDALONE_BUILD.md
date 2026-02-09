# Building the standalone macOS app

You can build a double-clickable **AI Coding Usage Tracker.app** that bundles Python and all dependencies, so end users do not need to install Python or a virtual environment.

## Option A: One-command setup and build

From the repo root (after clone or download):

```bash
chmod +x setup.sh
./setup.sh
```

This creates the virtual environment, installs dependencies, and builds the `.app`. Output: `dist/AI Coding Usage Tracker.app`.

## Option B: Manual build steps

**Requirements:** macOS, Python 3, venv, and project dependencies.

1. **Create and activate a virtual environment** (if you have not already):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install runtime and build dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. **Run the build script:**
   ```bash
   chmod +x build_standalone.sh
   ./build_standalone.sh
   ```

4. **Output:** The app bundle is created at:
   ```text
   dist/AI Coding Usage Tracker.app
   ```
   You can move it to `/Applications` or run it from `dist/`.

## What the app does when you open it

- Starts the Flask server on `http://127.0.0.1:5000` (or the port set by `AI_CODING_PORT`).
- Opens your default browser to the tracker UI.
- Shows a **menu bar icon** (“AI Usage”) at the top of the screen. Click it for:
  - **Open in Browser** — open or reopen the tracker in your browser.
  - **Quit** — stop the server and exit the app.
- The app does not appear in the Dock; use the menu bar to quit.

## Config and data paths

When you run the **standalone app** (the .app bundle), it uses:

- **Database:** `~/Library/Application Support/AI Coding Accounting/db/ai_usage.db` (so it always has a writable path). To use your existing `~/Documents/db/ai_usage.db` instead, set the environment variable `AI_CODING_DB_PATH` before opening the app (e.g. in a wrapper script).
- **SCM path for project detection:** `~/SCM` (or `AI_CODING_SCM_PATH` if set). You can change this in the app’s Projects section.
- **Uploads:** `~/Library/Application Support/AI Coding Accounting/uploads`.

When you run from source (`python app.py`), the database stays `~/Documents/db/ai_usage.db` unless you set `AI_CODING_DB_PATH`.

## macOS 26 (Tahoe): menu bar icon may not appear

On **macOS 26**, the system menu bar icon (“AI Usage”) often **does not show** for apps built with PyInstaller or similar launchers. This is a known macOS bug (see [Apple Developer Forums](https://developer.apple.com/forums/thread/806691)); the status bar item works on macOS 15.x but can disappear on 26.x.

**Workaround:** The app now shows a **small floating window** with **“Open in Browser”** and **“Quit”** so you can always open the dashboard and quit the app even when the menu bar icon is missing. Use that window, or quit via **Activity Monitor** (search for “ai-usage-tracker”) or run `pkill -f ai-usage-tracker` in Terminal.

## Debugging: menu bar or Dock not showing

When you run the .app, it writes a debug log so we can see where startup stops. **Look for this file on your Desktop:**

- **`~/Desktop/ai-usage-tracker-launch.log`**

If that can’t be created, it falls back to:

- **`~/Library/Logs/AI Coding Accounting/launch.log`**

Open the log and check the last lines: they show how far the app got (e.g. “rumps imported”, “activation policy set”, “TrackerMenuBar created”, or an error). Share the last 20–30 lines if you need help debugging.

## First run and Gatekeeper

On first launch, macOS may block the app because it is not notarized. If you see a security message:

1. Open **System Settings → Privacy & Security**.
2. Find the message about “AI Coding Usage Tracker” and choose **Open** (or **Open Anyway**).

Alternatively, from the terminal:

```bash
xattr -cr "dist/AI Coding Usage Tracker.app"
```

This only removes quarantine attributes; it does not replace Apple notarization for distribution to others.

## Building from the spec only

If you prefer to run PyInstaller yourself without the wrapper script:

```bash
pyinstaller ai-usage-tracker.spec
```

This produces the one-folder bundle at `dist/AI Coding Usage Tracker/`. The `build_standalone.sh` script then turns that folder into `dist/AI Coding Usage Tracker.app` with the correct launcher and `Info.plist`.
