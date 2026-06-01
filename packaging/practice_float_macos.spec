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
    [],
    exclude_binaries=True,
    name='guitar-practice-monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    upx=False,
    name='guitar-practice-monitor',
)
app = BUNDLE(
    coll,
    name='Guitar Practice Monitor.app',
    icon='../assets/app.icns',
    bundle_identifier='dev.pophirasawa.guitar-practice-monitor',
    info_plist={
        'NSMicrophoneUsageDescription': 'Guitar Practice Monitor needs microphone access for input visualization and chord detection.',
    },
)
