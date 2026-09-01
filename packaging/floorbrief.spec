# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parent

# The website never loads these artifacts. Leaving them out keeps the Mac
# bundle hundreds of megabytes smaller.
SKIP_PROCESSED = {
    "tfidf_index.joblib",
    "corpus.jsonl",
    "corpus.jsonl.gz",
    "promotion_calendar.csv",
    "promotion_calendar.csv.gz",
}


def collect_dir(src: Path, dest: str, *, skip_names=frozenset()) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if not src.exists():
        return items
    for path in src.rglob("*"):
        if not path.is_file() or path.name in skip_names:
            continue
        if path.name == "game_products.csv" and (path.parent / "game_products.csv.gz").exists():
            continue
        rel_parent = path.parent.relative_to(src)
        dest_dir = dest if rel_parent == Path(".") else str(Path(dest) / rel_parent)
        items.append((str(path), dest_dir))
    return items


datas = [
    *collect_dir(root / "apps" / "web", "apps/web"),
    *collect_dir(root / "data" / "raw", "data/raw"),
    *collect_dir(root / "data" / "processed", "data/processed", skip_names=SKIP_PROCESSED),
    *collect_dir(root / "src", "src"),
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
        "src.first_party",
        "src.historical_calendar",
        "openpyxl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "sklearn", "joblib", "scipy"],
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
