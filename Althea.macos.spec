# -*- mode: python ; coding: utf-8 -*-

# app building spec for PyInstaller, macOS target

# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

block_cipher = None


a = Analysis(
    ['Althea.py'],
    pathex=[],
    binaries=[],
    datas=[('commit_id', '.'), ('VERSION', '.'), ('License.txt', '.'), ('venv/lib/python*/site-packages/imgui_bundle/assets', './assets'), ('fonts', './fonts'), ('althea', './althea')],
    hiddenimports=['pandas', 'pandasql', 'sqlparse', 'numpy', 'numba'],
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
    name='Althea',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas, 
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Althea'
)
app = BUNDLE(
    coll,
    name='Althea.app',
    icon=None,
    bundle_identifier=None
)
