# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gso.py'],
    pathex=[],
    binaries=[],
    datas=[('storage/sqlite_schema.sql', 'storage')],
    hiddenimports=['scripts.init_aviation_db', 'scripts.fetch_airport_codes', 'scripts.poll_aviation_weather', 'scripts.fetch_aviation_weather', 'scripts.show_latest', 'scripts.weather_by_city'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='gso',
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
    name='gso',
)
