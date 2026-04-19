# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# 时区查找需要带上 timezonefinder 的二进制时区多边形数据
# 以及 Windows 下 zoneinfo 需要 tzdata 包
tzf_datas, tzf_binaries, tzf_hiddenimports = collect_all('timezonefinder')
tzd_datas, tzd_binaries, tzd_hiddenimports = collect_all('tzdata')

a = Analysis(
    ['gso.py'],
    pathex=[],
    binaries=tzf_binaries + tzd_binaries,
    datas=[('storage/sqlite_schema.sql', 'storage')] + tzf_datas + tzd_datas,
    hiddenimports=[
        'scripts.init_aviation_db',
        'scripts.fetch_airport_codes',
        'scripts.poll_aviation_weather',
        'scripts.fetch_aviation_weather',
        'scripts.show_latest',
        'scripts.weather_by_city',
    ] + tzf_hiddenimports + tzd_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pandas', 'PIL'],
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
