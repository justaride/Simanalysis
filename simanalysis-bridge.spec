# -*- mode: python ; coding: utf-8 -*-
# Headless stdio bridge sidecar: a single `simanalysis-bridge` binary,
# no web server and no web/dist.
block_cipher = None

a = Analysis(
    ['run_bridge.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'simanalysis.analyzers.mod_analyzer',
        'simanalysis.analyzers.tray_analyzer',
        'simanalysis.analyzers.save_analyzer',
        'simanalysis.services.thumbnail_service',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['fastapi', 'uvicorn', 'starlette', 'textual', 'aiohttp', 'jinja2'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='simanalysis-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)
