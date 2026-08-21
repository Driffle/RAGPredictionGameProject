# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parent
datas = [
    (str(root / "apps" / "web"), "apps/web"),
    (str(root / "data" / "raw"), "data/raw"),
    (str(root / "data" / "processed"), "data/processed"),
    (str(root / "src"), "src"),
]

a = Analysis(
    [str(root / "apps" / "desktop.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "fastapi",
        "starlette",
        "pydantic",
        "webview",
        "apps",
        "apps.api",
        "src.database",
        "src.horizon",
        "src.live_fetch",
        "src.announced",
        "src.artwork",
        "src.coverage",
        "src.cross_sell",
        "src.date_range",
        "src.dates",
        "src.official_dates",
        "src.provenance",
        "src.audit_changes",
        "src.calendar_dedupe",
        "src.content_marketing",
        "src.sheets",
        "src.geo_placement",
        "src.load_data",
        "src.promote",
        "src.priorities",
        "src.daily_brief",
        "src.trends",
        "src.match",
        "src.documents",
        "src.http",
        "src.paths",
        "src.store",
        "src.orders",
        "src.historical_calendar",
        "openpyxl",
        "joblib",
        "sklearn",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FloorBrief",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="FloorBrief",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FloorBrief.app",
        icon=None,
        bundle_identifier="com.ragprediction.floorbrief",
        info_plist={"NSHighResolutionCapable": True, "CFBundleName": "Floor Brief"},
    )
