# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH)
block_cipher = None

a = Analysis(
    [str(ROOT / 'scripts' / 'runtime' / 'tray_v2.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'scripts' / 'runtime' / 'supervisor.py'), 'scripts/runtime'),
        (str(ROOT / 'scripts' / 'runtime' / 'serve_frontend.py'), 'scripts/runtime'),
        (str(ROOT / 'scripts' / 'runtime' / 'cmd_listener.py'), 'scripts/runtime'),
        (str(ROOT / 'frontend' / 'build'), 'frontend/build'),
        (str(ROOT / 'frontend'), 'frontend'),
        (str(ROOT / 'README.md'), '.'),
    ],
    hiddenimports=['pystray._win32','PIL._imaging','PIL.Image','PIL.ImageDraw','urllib.request','json','threading','subprocess','webbrowser'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch','tensorflow','cv2','numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GH05T3-Sovereign',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version_file=None,
    uac_admin=False,
)
