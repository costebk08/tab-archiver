# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).resolve().parent

datas = [(str(project_root / "static"), "static")]
binaries = []
hiddenimports = [
    "app",
    "app.autostart",
    "app.browser_detection",
    "app.browser_launcher",
    "app.config",
    "app.platform_config",
    "app.settings",
    "app.snss_parser",
    "app.storage",
    "app.updater",
    "lz4.block",
    "psutil",
    "sqlite3",
]

for package in ("uvicorn", "fastapi", "starlette", "anyio", "pydantic", "pydantic_core"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hidden)

block_cipher = None

a = Analysis(
    [str(project_root / "run_app.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="Tab Archiver",
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Tab Archiver",
)

app = BUNDLE(
    coll,
    name="Tab Archiver.app",
    icon=None,
    bundle_identifier="com.tabarchiver.app",
)
