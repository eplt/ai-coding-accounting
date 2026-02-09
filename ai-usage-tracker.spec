# PyInstaller spec for AI Coding Usage Tracker (one-folder build for macOS .app wrapper)
# Build with: pyinstaller ai-usage-tracker.spec

import os

block_cipher = None

# Include templates so they appear under sys._MEIPASS/templates when frozen
spec_dir = os.path.dirname(os.path.abspath(SPEC))
templates_src = os.path.join(spec_dir, 'templates')

a = Analysis(
    ['launch.py'],
    pathex=[],
    binaries=[],
    datas=[(templates_src, 'templates')],
    hiddenimports=[
        'flask',
        'flask_sqlalchemy',
        'werkzeug',
        'werkzeug.security',
        'jinja2',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'rumps',
        'objc',
        'Foundation',
        'AppKit',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ai-usage-tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No terminal window when double-clicking .app on macOS
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI Coding Usage Tracker',
)
