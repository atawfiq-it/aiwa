# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/run/media/alpha/Work/ai_apps/aiwa/backend/app/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/run/media/alpha/Work/ai_apps/aiwa/backend/migrations', 'migrations')],
    hiddenimports=['sqlmodel', 'uvicorn', 'sqlite3', 'engineio.async_drivers.asgi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='aiwa-backend-app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='aiwa-backend-app',
)
