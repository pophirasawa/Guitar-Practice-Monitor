# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


a = Analysis(
    ['../src/desktop/practice_float.py'],
    pathex=['../src/backend'],
    binaries=collect_dynamic_libs('sounddevice'),
    datas=[
        ('../src/frontend/records.html', 'frontend'),
        ('../src/frontend/records.css', 'frontend'),
        ('../src/frontend/records.js', 'frontend'),
    ] + collect_data_files('sounddevice'),
    hiddenimports=['log_server'],
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
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name='guitar-practice-monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='../assets/app.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
