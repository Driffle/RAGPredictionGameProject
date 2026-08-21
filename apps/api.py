"""Floor Brief HTTP API and static website."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.artwork import ARTWORK_DIR
from src.paths import DATA_PROCESSED, PROJECT_ROOT
from src.store import get_store

WEB_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "apps" / "web"
if not WEB_DIR.exists():
    WEB_DIR = PROJECT_ROOT / "apps" / "web"

MEDIA_ARTWORK = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "data" / "processed" / "live" / "artwork"
if not MEDIA_ARTWORK.exists():
    MEDIA_ARTWORK = ARTWORK_DIR

app = FastAPI(title="Floor Brief", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    get_store()


@app.get("/api/health")
def health() -> dict:
    store = get_store()
    return {
        "ok": True,
        "loaded": store.loaded,
        "titles": len(store.titles),
        "events": len(store.events),
        "last_checked": (store.meta or {}).get("last_checked"),
        "artwork": (store.meta or {}).get("artwork"),
    }


@app.get("/api/products")
def products(q: str = Query(default=""), limit: int = Query(default=30, ge=1, le=80)) -> dict:
    return {"results": get_store().search_products(q, limit=limit)}


@app.get("/api/brief")
def brief(
    q: str = Query(..., min_length=1),
    start_year: int | None = Query(default=None, ge=2020, le=2035),
    start_month: int | None = Query(default=None, ge=1, le=12),
    end_year: int | None = Query(default=None, ge=2020, le=2035),
    end_month: int | None = Query(default=None, ge=1, le=12),
) -> dict:
    payload = get_store().product_brief(
        q,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail="No matching product in the catalog")
    return payload


@app.get("/api/events")
def events(
    q: str = Query(default=""),
    limit: int = Query(default=40, ge=1, le=80),
    year: int | None = Query(default=None, ge=2026, le=2030),
    kind: str = Query(default=""),
    mode: str = Query(default=""),
) -> dict:
    return {
        "results": get_store().search_events(
            q,
            limit=limit,
            year=year,
            kind=kind,
            mode=mode,
        )
    }


@app.get("/api/event")
def event_brief(
    q: str = Query(..., min_length=1),
    start_year: int | None = Query(default=None, ge=2020, le=2035),
    start_month: int | None = Query(default=None, ge=1, le=12),
    end_year: int | None = Query(default=None, ge=2020, le=2035),
    end_month: int | None = Query(default=None, ge=1, le=12),
) -> dict:
    payload = get_store().event_brief(
        q,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail="No matching event on the calendar")
    return payload


@app.get("/api/cross-sell")
def cross_sell(q: str = Query(..., min_length=1)) -> dict:
    """Event name → games and products to cross-sell in that timeframe."""
    payload = get_store().cross_sell_brief(q)
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail="No cross-sell products mapped for that event")
    return payload


@app.get("/api/cross-sell/events")
def cross_sell_events(limit: int = Query(default=40, ge=1, le=80)) -> dict:
    return {"results": [{"name": name} for name in get_store().featured_cross_sell_events(limit=limit)]}


@app.get("/api/calendar-range")
def calendar_range(
    start_year: int = Query(..., ge=2020, le=2035),
    start_month: int = Query(..., ge=1, le=12),
    end_year: int = Query(..., ge=2020, le=2035),
    end_month: int = Query(..., ge=1, le=12),
    kind: str = Query(default=""),
    precision: str = Query(default="", pattern="^(|all|dated|exact)$"),
    limit: int = Query(default=60, ge=1, le=120),
) -> dict:
    """Month/year range → overlapping events plus promote and cross-sell products."""
    return get_store().calendar_range_brief(
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        kind=kind,
        precision=precision,
        limit=limit,
    )


@app.get("/api/archive")
def archive(year: str = Query(default="", pattern="^(|2022|2023|2024|2025|2026)$")) -> dict:
    """Worldwide gaming events with runtimes from 2022 through 2026."""
    return get_store().archive_events(year=year)


@app.get("/api/changes")
def changes() -> dict:
    """Daily audit of delays, cancellations, confirmation flips, and date moves."""
    from src.audit_changes import load_changes
    from src.documents import load_rag_meta

    rows = load_changes()
    return {
        "as_of": rows[0]["as_of"] if rows else None,
        "count": len(rows),
        "changes": rows,
        "rag": load_rag_meta(),
    }


@app.get("/api/dashboard")
def dashboard() -> dict:
    return get_store().dashboard()


@app.get("/api/trends/analysis")
def trends_analysis() -> dict:
    return get_store().trends_analysis()


@app.post("/api/trends/refresh")
def refresh_trends() -> dict:
    store = get_store()
    store.refresh_trends()
    return {"ok": True, "priorities": len(store.priorities)}


@app.post("/api/database/refresh")
def refresh_database() -> dict:
    return {"ok": True, **get_store().refresh_database()}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
if MEDIA_ARTWORK.exists():
    app.mount("/media/artwork", StaticFiles(directory=str(MEDIA_ARTWORK)), name="artwork")


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    serve(host="0.0.0.0")
