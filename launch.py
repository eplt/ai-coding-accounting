"""
Entry point for the standalone macOS .app.
Starts the Flask server, sets the database path from config file before loading the app,
then runs a menu bar + floating window (Open in Browser, Settings, Quit).
"""
import json
import logging
import os
import sys
import threading
import time
import webbrowser

# Bootstrap log when frozen: write to Desktop so you can always find it (even if we crash later)
_DEBUG_LOG_PATH = None
if getattr(sys, "frozen", False):
    for _path in (
        os.path.expanduser("~/Desktop/ai-usage-tracker-launch.log"),
        os.path.expanduser("~/Library/Logs/AI Coding Accounting/launch.log"),
    ):
        try:
            if _path.startswith(os.path.expanduser("~/Library")):
                os.makedirs(os.path.dirname(_path), exist_ok=True)
            with open(_path, "a", encoding="utf-8") as _f:
                _f.write(f"[start] frozen app launched\n")
            _DEBUG_LOG_PATH = _path
            break
        except Exception:
            continue

def _debug_log(msg: str) -> None:
    """Append one line to the bootstrap log when frozen."""
    if _DEBUG_LOG_PATH:
        try:
            with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

if _DEBUG_LOG_PATH:
    _debug_log(f"[start] debug log path: {_DEBUG_LOG_PATH}")

import rumps

if _DEBUG_LOG_PATH:
    _debug_log("[start] rumps imported")

import config

# Set DB path from config file into env before app loads (ensures saved path is used after restart)
try:
    _cfg_path = config.get_app_config_path()
    if os.path.exists(_cfg_path):
        with open(_cfg_path, encoding="utf-8") as _f:
            _cfg = json.load(_f)
        _db_path = (_cfg.get("database_path") or "").strip()
        if _db_path:
            os.environ["AI_CODING_DB_PATH"] = _db_path
            if _DEBUG_LOG_PATH:
                _debug_log(f"[start] set AI_CODING_DB_PATH from config: {_db_path}")
except Exception as _e:
    if _DEBUG_LOG_PATH:
        _debug_log(f"[start] config read failed: {_e}")

from app import app, db

if _DEBUG_LOG_PATH:
    _debug_log("[start] config and app imported")

# Keep references to helper window and handler so they are not GC'd
_helper_window_refs = []

# Button handler class for the helper window - defined once at module level so we don't
# override the Objective-C class when the timer fires repeatedly
def _get_helper_button_handler_class():
    if hasattr(_get_helper_button_handler_class, "_klass"):
        return _get_helper_button_handler_class._klass
    import AppKit
    import objc
    class _HelperButtonHandler(AppKit.NSObject):
        def init(self):
            self = objc.super(_HelperButtonHandler, self).init()
            if self is not None:
                self._url = None
            return self
        def openInBrowser_(self, sender):
            if getattr(self, "_url", None):
                webbrowser.open(self._url)
        def openSettings_(self, sender):
            if getattr(self, "_url", None):
                webbrowser.open(self._url + "#settings")
        def quitApp_(self, sender):
            rumps.quit_application()
    _get_helper_button_handler_class._klass = _HelperButtonHandler
    return _HelperButtonHandler


def _setup_frozen_logging() -> None:
    """When running as a frozen .app, also use logging to the same file."""
    if not getattr(sys, "frozen", False):
        return
    if not _DEBUG_LOG_PATH:
        return
    try:
        handler = logging.FileHandler(_DEBUG_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log = logging.getLogger("launch")
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)
        log.info("Frozen app starting")
    except Exception:
        pass


def wait_for_server(url: str, timeout: float = 10.0, interval: float = 0.2) -> bool:
    """Poll until the server at url responds, or timeout."""
    try:
        import urllib.request
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                urllib.request.urlopen(url, timeout=1)
                return True
            except OSError:
                time.sleep(interval)
        return False
    except Exception:
        return False


def _set_app_activation_for_dock_and_menubar() -> None:
    """Ensure the app is a regular GUI app so it appears in the Dock and menu bar."""
    try:
        import AppKit
        nsapp = AppKit.NSApplication.sharedApplication()
        # NSApplicationActivationPolicyRegular = 1: show in Dock and allow menu bar
        nsapp.setActivationPolicy_(1)
        nsapp.activateIgnoringOtherApps_(True)
    except Exception as e:
        _debug_log(f"[main] setActivationPolicy failed: {e}")
        log = logging.getLogger("launch")
        log.warning("Could not set activation policy: %s", e, exc_info=True)


def _create_helper_window(url: str):
    """
    Create a small floating window with Open in Browser and Quit.
    On macOS 26 the menu bar icon often does not show (Apple bug); this window
    is always visible so you can open the dashboard and quit the app.
    """
    try:
        import AppKit

        # Use NSWindow so it behaves like a normal window; style: titled, closable, miniaturizable
        style = 1 | 2 | 4
        frame = AppKit.NSMakeRect(150, 300, 300, 158)
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, AppKit.NSBackingStoreBuffered, False
        )
        window.setTitle_("AI Usage Tracker")
        window.setLevel_(getattr(AppKit, "NSFloatingWindowLevel", 3))
        content = window.contentView()

        open_btn = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(30, 108, 240, 32))
        open_btn.setTitle_("Open in Browser")
        open_btn.setButtonType_(AppKit.NSMomentaryPushInButton)
        open_btn.setBezelStyle_(AppKit.NSRoundedBezelStyle)
        content.addSubview_(open_btn)

        settings_btn = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(30, 68, 240, 32))
        settings_btn.setTitle_("Settings")
        settings_btn.setButtonType_(AppKit.NSMomentaryPushInButton)
        settings_btn.setBezelStyle_(AppKit.NSRoundedBezelStyle)
        content.addSubview_(settings_btn)

        quit_btn = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(30, 18, 240, 32))
        quit_btn.setTitle_("Quit")
        quit_btn.setButtonType_(AppKit.NSMomentaryPushInButton)
        quit_btn.setBezelStyle_(AppKit.NSRoundedBezelStyle)
        content.addSubview_(quit_btn)

        HandlerClass = _get_helper_button_handler_class()
        handler = HandlerClass.alloc().init()
        handler._url = url
        open_btn.setTarget_(handler)
        open_btn.setAction_("openInBrowser:")
        settings_btn.setTarget_(handler)
        settings_btn.setAction_("openSettings:")
        quit_btn.setTarget_(handler)
        quit_btn.setAction_("quitApp:")

        # Keep refs so window and handler are not GC'd; don't set attributes on NSWindow (PyObjC proxy)
        _helper_window_refs.append((window, handler))
        window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        return window
    except Exception as e:
        _debug_log(f"[main] helper window failed: {e}")
        return None


def main() -> None:
    _setup_frozen_logging()
    log = logging.getLogger("launch")
    _debug_log("[main] entered")

    # Mark as regular GUI app early so Dock and menu bar show (must be before rumps.run())
    _set_app_activation_for_dock_and_menubar()
    _debug_log("[main] activation policy set")

    try:
        with app.app_context():
            db.create_all()
            # Schema migration: add project.group_id if missing (e.g. DB created before project groups)
            try:
                from sqlalchemy import text
                db.session.execute(text("ALTER TABLE project ADD COLUMN group_id INTEGER"))
                db.session.commit()
                _debug_log("[main] added project.group_id column")
            except Exception as _e:
                db.session.rollback()
                if "duplicate column name" not in str(_e).lower():
                    _debug_log(f"[main] project group_id column: {_e}")
            # Confirm which DB we're actually using and that we can read data
            try:
                from sqlalchemy import text
                _uri = str(db.engine.url)
                _debug_log(f"[main] engine URL: {_uri}")
                _tables = [r[0] for r in db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).fetchall()]
                _debug_log(f"[main] tables in DB: {_tables}")
                _n = db.session.execute(text("SELECT COUNT(*) FROM usage_event")).scalar()
                _debug_log(f"[main] usage_event row count: {_n}")
            except Exception as _e:
                _debug_log(f"[main] DB check failed: {_e}")
    except Exception as e:
        _debug_log(f"[main] database init failed: {e}")
        log.exception("Database init failed: %s", e)
        raise
    _debug_log("[main] database ready")

    port = config.PORT
    url = f"http://127.0.0.1:{port}"

    def run_server() -> None:
        try:
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        except Exception as e:
            log.exception("Flask server error: %s", e)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    if wait_for_server(url):
        webbrowser.open(url)
    else:
        log.warning("Server did not become ready in time; port %s may be in use", port)

    # Menu bar app: stays in the menu bar so you can reopen browser or quit
    class TrackerMenuBar(rumps.App):
        def __init__(self, dashboard_url: str, **kwargs):
            super().__init__(
                "AI Usage Tracker",
                "AI Usage",
                menu=["Open in Browser", None],
                quit_button="Quit",
                **kwargs,
            )
            self._url = dashboard_url
            self._helper_window = None

        @rumps.clicked("Open in Browser")
        def open_browser(self, _):
            webbrowser.open(self._url)

        @rumps.timer(0.5)  # fire once after 0.5s when run loop is active
        def show_helper_window(self, _):
            if self._helper_window is not None:
                return
            self._helper_window = _create_helper_window(self._url)
            if self._helper_window:
                _debug_log("[main] helper window shown (from timer)")

    menu_app = TrackerMenuBar(url)
    _debug_log("[main] TrackerMenuBar created")

    _debug_log("[main] calling menu_app.run()")
    try:
        log.info("Starting menu bar app")
        menu_app.run()
    except Exception as e:
        _debug_log(f"[main] menu bar app failed: {e}")
        log.exception("Menu bar app failed: %s", e)
        # Keep server running so user can still use the browser
        thread.join()


if __name__ == "__main__":
    main()
