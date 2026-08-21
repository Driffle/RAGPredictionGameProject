"""Build and overwrite the live product/event database (2026–2030)."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.announced import (
    correlate_events_with_announced,
    curated_announced_games,
    release_window_events,
)
from src.artwork import refresh_artwork_dataset
from src.audit_changes import run_audits
from src.dates import annotate_event, annotate_product
from src.documents import retrain_rag_index
from src.official_dates import apply_event_overrides, apply_product_overrides
from src.coverage import cross_media_releases
from src.historical_calendar import historical_adaptations, historical_events
from src.horizon import projected_events
from src.live_fetch import (
    HORIZON_END,
    HORIZON_START,
    fetch_wikidata_adaptations,
    fetch_wikidata_games,
    fetch_wikipedia_adaptations,
    fetch_wikipedia_events,
    fetch_wikipedia_games,
)
from src.load_data import load_calendar, load_catalog, parse_date
from src.paths import DATA_PROCESSED
from src.promote import build_plans, write_promotion_csv
from src.provenance import preserve_entry_date, stamp_provenance
from src.sheets import export_dataset_sheets

LIVE_DIR = DATA_PROCESSED / "live"
META_PATH = LIVE_DIR / "meta.json"
EVENTS_JSON = LIVE_DIR / "events.json"
ADAPTATIONS_JSON = LIVE_DIR / "adaptations.json"
ANNOUNCED_JSON = LIVE_DIR / "announced_games.json"
OVERLAY_JSON = LIVE_DIR / "catalog_overlay.json"


def _hydrate(row: dict) -> dict:
    out = dict(row)
    start = parse_date(out.get("start_date"))
    end = parse_date(out.get("end_date")) or start
    out["start_date_parsed"] = start
    out["end_date_parsed"] = end
    if start and not out.get("start_date"):
        out["start_date"] = start.isoformat()
    if end and not out.get("end_date"):
        out["end_date"] = end.isoformat()
    return out


def _event_key(row: dict) -> str:
    name = (row.get("event") or row.get("ip_adaptation") or "").strip().lower()
    if row.get("source") == "announced_product_window":
        # One merchandising window per announced title, whatever month it moves to.
        return f"{name}|release-window"
    start = (row.get("start_date") or "")[:7]
    return f"{name}|{start}"


def _prefer(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    rank = {"horizon_template": 1, "wikidata": 2, "wikipedia": 3, "ods": 5}

    def source_rank(row: dict) -> int:
        status = f"{row.get('status', '')} {row.get('confirmation', '')} {row.get('date_status', '')}".lower()
        if "confirm" in status or "known cycle" in status:
            return 6
        src = row.get("source") or "ods"
        if src == "historical_registry":
            return 6
        if src == "announced_registry":
            return 5
        if src.startswith("wikipedia"):
            return rank["wikipedia"]
        return rank.get(src, 3)

    if source_rank(incoming) >= source_rank(existing):
        for key, value in incoming.items():
            if value not in (None, "", [], {}):
                merged[key] = value
    else:
        for key, value in incoming.items():
            if key not in merged or merged.get(key) in (None, "", [], {}):
                merged[key] = value
    for field in (
        "wikipedia_url",
        "wikidata_id",
        "summary",
        "genre",
        "developer",
        "publisher",
        "platforms",
        "confirmation",
        "source",
        "last_checked",
        "official_source",
        "format",
        "scope",
        "release_channel",
        "attendance_mode",
        "location",
        "organizer",
        "cadence",
    ):
        if incoming.get(field) and not merged.get(field):
            merged[field] = incoming[field]
    merged["last_checked"] = date.today().isoformat()
    return preserve_entry_date(existing, incoming, merged)


def _merge_rows(base: list[dict], extra: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for row in base + extra:
        hydrated = _hydrate(row)
        key = _event_key(hydrated)
        if key in by_key:
            by_key[key] = _prefer(by_key[key], hydrated)
        else:
            by_key[key] = hydrated
    rows = list(by_key.values())
    rows.sort(key=lambda row: row.get("start_date") or "9999")
    return rows


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            payload = {key: row.get(key, "") for key in fields}
            writer.writerow(payload)


def _dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(payload, default=lambda value: value.isoformat() if isinstance(value, date) else str(value)))
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def refresh_live_database(*, fetch: bool = True) -> dict:
    """Overwrite processed calendar/product files with live metadata + horizon rows."""
    today = date.today().isoformat()
    calendar = load_calendar()
    ods_events = [{**row, "source": row.get("source") or "ods"} for row in calendar["events"]]
    ods_adaptations = [{**row, "source": row.get("source") or "ods"} for row in calendar["adaptations"]]
    wiki_events: list[dict] = []
    wiki_adaptations: list[dict] = []
    wiki_games: list[dict] = []
    wikidata_games: list[dict] = []
    wikidata_adaptations: list[dict] = []
    if fetch:
        wiki_events = fetch_wikipedia_events()
        wiki_adaptations = fetch_wikipedia_adaptations()
        wiki_games = fetch_wikipedia_games()
        wikidata_games = fetch_wikidata_games()
        wikidata_adaptations = fetch_wikidata_adaptations()
        events = _merge_rows(ods_events, projected_events() + wiki_events + historical_events())
        adaptations = _merge_rows(
            ods_adaptations,
            cross_media_releases() + wiki_adaptations + wikidata_adaptations + historical_adaptations(),
        )
    else:
        # Rebuild announced/event correlations from cached live rows.
        existing_events = load_json(EVENTS_JSON) or []
        existing_adaptations = load_json(ADAPTATIONS_JSON) or []
        wiki_games = load_json(ANNOUNCED_JSON, []) or []
        wikidata_games = []
        events = _merge_rows(
            ods_events,
            projected_events()
            + historical_events()
            + [
                row
                for row in existing_events
                if (row.get("source") or "").startswith("wikipedia")
                or row.get("source") == "announced_product_window"
                or row.get("source") == "historical_registry"
            ],
        )
        adaptations = _merge_rows(
            ods_adaptations,
            cross_media_releases()
            + historical_adaptations()
            + [
                row
                for row in existing_adaptations
                if (row.get("source") or "").startswith("wikipedia")
                or (row.get("source") or "").startswith("wikidata")
                or row.get("source") == "cross_media_registry"
                or row.get("source") == "historical_registry"
            ],
        )

    catalog = load_catalog(games_only=True, drop_placeholder_dates=True, include_live=False)
    overlay: dict[str, dict] = {}
    announced: list[dict] = []
    catalog_index = {row["canonical_title"].lower(): row for row in catalog if row.get("canonical_title")}
    for game in curated_announced_games(today=today) + wiki_games + wikidata_games:
        title = (game.get("canonical_title") or "").strip()
        if not title:
            continue
        meta = {
            "wikipedia_url": game.get("wikipedia_url") or "",
            "wikidata_id": game.get("wikidata_id") or "",
            "genre": game.get("genre") or "",
            "developer": game.get("developer") or "",
            "publisher": game.get("publisher") or "",
            "platforms": game.get("platforms") or game.get("platform") or "",
            "announced_release": game.get("release_date") or "",
            "confirmation": game.get("confirmation") or "",
            "source": game.get("source") or "",
            "franchise": game.get("franchise") or "",
            "last_checked": today,
        }
        overlay[title.lower()] = {**overlay.get(title.lower(), {}), **{k: v for k, v in meta.items() if v}}
        hit = catalog_index.get(title.lower())
        if hit:
            hit.update({key: value for key, value in meta.items() if value})
            # Keep storefront SKUs but flag that a live announcement also exists.
            if not hit.get("confirmation"):
                hit["confirmation"] = meta.get("confirmation") or "announced"
        else:
            announced.append(
                {
                    "product_id": game.get("product_id")
                    or f"live:{(game.get('wikidata_id') or title)[:40]}",
                    "product_sku": "",
                    "canonical_title": title,
                    "product_title": game.get("product_title") or title,
                    "product_type": "announced",
                    "platform": game.get("platform") or "Multi",
                    "status": game.get("confirmation") or "announced",
                    "release_date": game.get("release_date") or "",
                    "slug": title.lower().replace(" ", "-"),
                    **meta,
                }
            )

    # Prefer curated / richer metadata when the same title appears twice.
    by_title: dict[str, dict] = {}
    for row in announced:
        key = (row.get("canonical_title") or "").lower()
        if key not in by_title:
            by_title[key] = row
            continue
        by_title[key] = _prefer(by_title[key], row)
    announced = list(by_title.values())
    announced.sort(key=lambda row: (row.get("release_date") or "9999", row.get("canonical_title") or ""))

    # Release windows and correlations must include curated titles even when the
    # storefront already has a pre-order / early SKU under product_type=game.
    correlation_pool: dict[str, dict] = {
        (row.get("canonical_title") or "").lower(): row for row in announced if row.get("canonical_title")
    }
    for row in curated_announced_games(today=today):
        key = (row.get("canonical_title") or "").lower()
        if not key:
            continue
        if key in correlation_pool:
            correlation_pool[key] = _prefer(correlation_pool[key], row)
        else:
            correlation_pool[key] = row
    for row in catalog:
        release = row.get("release_date") or ""
        if release < today:
            continue
        confirmation = f"{row.get('confirmation') or ''} {row.get('status') or ''}".lower()
        if not (
            row.get("product_type") == "announced"
            or "announc" in confirmation
            or row.get("announced_release")
            or row.get("source") == "announced_registry"
        ):
            continue
        key = (row.get("canonical_title") or "").lower()
        if not key:
            continue
        payload = {
            **row,
            "product_type": "announced" if row.get("product_type") != "announced" else row.get("product_type"),
            "confirmation": row.get("confirmation") or "announced",
        }
        if key in correlation_pool:
            correlation_pool[key] = _prefer(correlation_pool[key], payload)
        else:
            correlation_pool[key] = payload
    correlation_rows = list(correlation_pool.values())

    # Publisher / organizer confirmed dates beat Wikipedia scrapes and TBA stubs.
    announced = apply_product_overrides(announced)
    correlation_rows = apply_product_overrides(correlation_rows)
    catalog = apply_product_overrides(catalog)

    # Release windows are regenerated from the current announced dates every run,
    # so drop cached copies first; otherwise a revised date leaves the old window
    # behind under a different month key.
    events = [row for row in events if row.get("source") != "announced_product_window"]
    events = _merge_rows(events, release_window_events(correlation_rows))
    events = apply_event_overrides(events)
    events = correlate_events_with_announced(events, correlation_rows)
    adaptations = correlate_events_with_announced(adaptations, correlation_rows)

    # Record how precise every stored date is so month/quarter/year announcements
    # stop reading as 31 December releases in range searches and in the UI.
    events = [stamp_provenance(annotate_event(row), default_source="calendar") for row in events]
    adaptations = [
        stamp_provenance(annotate_event(row), default_source="calendar") for row in adaptations
    ]
    announced = [stamp_provenance(annotate_product(row), default_source="announced_registry") for row in announced]
    correlation_rows = [
        stamp_provenance(annotate_product(row), default_source="catalog") for row in correlation_rows
    ]
    catalog = [stamp_provenance(row, default_source="catalog") for row in catalog]

    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    _dump_json(EVENTS_JSON, events)
    _dump_json(ADAPTATIONS_JSON, adaptations)
    _dump_json(ANNOUNCED_JSON, announced)
    _dump_json(OVERLAY_JSON, overlay)

    event_fields = [
        "start_date",
        "end_date",
        "runtime_start",
        "runtime_end",
        "date_precision",
        "date_label",
        "event",
        "category",
        "related_game",
        "event_type",
        "status",
        "wikipedia_url",
        "source",
        "confirmation",
        "official_source",
        "summary",
        "entry_date",
        "last_checked",
        "attendance_mode",
        "scope",
        "location",
        "organizer",
        "cadence",
        "correlated_announced",
    ]
    adaptation_fields = [
        "start_date",
        "end_date",
        "runtime_start",
        "runtime_end",
        "date_precision",
        "date_label",
        "ip_adaptation",
        "medium",
        "distributor",
        "related_game",
        "date_status",
        "wikipedia_url",
        "source",
        "confirmation",
        "entry_date",
        "last_checked",
        "format",
        "scope",
        "release_channel",
        "wikidata_id",
        "correlated_announced",
    ]
    announced_fields = [
        "product_id",
        "canonical_title",
        "product_title",
        "product_type",
        "platform",
        "status",
        "release_date",
        "release_start",
        "release_end",
        "date_precision",
        "release_label",
        "genre",
        "developer",
        "publisher",
        "wikipedia_url",
        "source",
        "confirmation",
        "official_source",
        "franchise",
        "platforms",
        "entry_date",
        "last_checked",
    ]
    _write_csv(DATA_PROCESSED / "events.csv", events, event_fields)
    _write_csv(DATA_PROCESSED / "adaptations.csv", adaptations, adaptation_fields)
    _write_csv(DATA_PROCESSED / "announced_games.csv", announced, announced_fields)
    upcoming = [
        row
        for row in catalog
        if (row.get("release_date") or "") >= HORIZON_START.isoformat()
        and (row.get("release_date") or "") <= HORIZON_END.isoformat()
    ]
    upcoming_fields = [
        "product_id",
        "canonical_title",
        "product_title",
        "product_sku",
        "product_type",
        "platform",
        "status",
        "release_date",
        "wikipedia_url",
        "genre",
        "developer",
        "publisher",
        "confirmation",
        "source",
        "entry_date",
        "last_checked",
    ]
    _write_csv(DATA_PROCESSED / "upcoming_games.csv", upcoming, upcoming_fields)

    sheet_paths = export_dataset_sheets(
        products=upcoming,
        announced=announced,
        events=events,
        adaptations=adaptations,
    )

    merged_catalog = catalog + announced
    plans = build_plans(events, adaptations, merged_catalog)
    write_promotion_csv(plans)

    # Audit delays / cancellations / confirmation flips against yesterday's snapshot.
    audit_products = announced + [
        row
        for row in catalog
        if (row.get("product_type") == "announced")
        or "announc" in (row.get("confirmation") or "").lower()
        or (row.get("release_date") or "") >= today
    ]
    # Deduplicate by title for a stable snapshot.
    audit_by_title: dict[str, dict] = {}
    for row in audit_products:
        key = (row.get("canonical_title") or row.get("product_title") or "").lower()
        if key and key not in audit_by_title:
            audit_by_title[key] = row
    audit_summary = run_audits(
        products=list(audit_by_title.values()),
        events=events + adaptations,
    )

    rag_meta = retrain_rag_index(events, adaptations, merged_catalog, plans)

    # Artwork for announced/upcoming products and calendar rows (remote URLs + placeholders).
    # Everything a promotion plan can surface needs a cover, otherwise cross-sell
    # and calendar tiles fall back to placeholders.
    art_products = sorted(
        correlation_rows + announced,
        key=lambda row: row.get("release_date") or "9999",
    )
    catalog_art = {(row.get("canonical_title") or "").lower(): row for row in merged_catalog}
    for plan in plans:
        title = plan.get("canonical_title") or ""
        if title and not any((row.get("canonical_title") or "").lower() == title.lower() for row in art_products):
            source = catalog_art.get(title.lower()) or {}
            art_products.append(
                {
                    "canonical_title": title,
                    "wikipedia_url": source.get("wikipedia_url") or "",
                }
            )
    art_events = list(events) + list(adaptations)
    artwork_meta = refresh_artwork_dataset(
        products=art_products,
        events=art_events,
        adaptations=[],
        limit_products=600,
        limit_events=600,
        fetch=fetch,
    )
    artwork_fields = ["key", "name", "kind", "image_url", "page_url", "source", "placeholder"]
    _write_csv(DATA_PROCESSED / "artwork.csv", artwork_meta.get("items") or [], artwork_fields)

    meta = {
        "last_checked": today,
        "horizon_start": HORIZON_START.isoformat(),
        "horizon_end": HORIZON_END.isoformat(),
        "events": len(events),
        "adaptations": len(adaptations),
        "announced_games": len(announced),
        "catalog_overlay": len(overlay),
        "promotion_plans": len(plans),
        "physical_events": sum(row.get("attendance_mode") == "physical" for row in events),
        "digital_events": sum(row.get("attendance_mode") == "digital" for row in events),
        "hybrid_events": sum(row.get("attendance_mode") == "hybrid" for row in events),
        "entertainment_formats": len(
            {
                row.get("format") or row.get("medium")
                for row in adaptations
                if row.get("format") or row.get("medium")
            }
        ),
        "correlated_events": sum(1 for row in events if row.get("correlated_announced")),
        "announced_tba": sum(
            1
            for row in list(announced) + list(correlation_rows)
            if "tba" in (row.get("confirmation") or "").lower()
        ),
        "announced_release_windows": sum(
            1 for row in events if row.get("source") == "announced_product_window"
        ),
        "artwork": artwork_meta.get("count") or 0,
        "artwork_remote": artwork_meta.get("remote") or 0,
        "artwork_products": (artwork_meta.get("counts") or {}).get("products")
        or sum(1 for row in (artwork_meta.get("items") or []) if row.get("kind") == "product"),
        "artwork_events": (artwork_meta.get("counts") or {}).get("events")
        or sum(1 for row in (artwork_meta.get("items") or []) if row.get("kind") == "event"),
        "fetched": fetch,
        "sheet_paths": sheet_paths,
        "audit": {
            "change_count": audit_summary.get("change_count") or 0,
            "by_type": audit_summary.get("by_type") or {},
            "product_official_mismatches": len(audit_summary.get("product_official_mismatches") or []),
            "event_official_mismatches": len(audit_summary.get("event_official_mismatches") or []),
        },
        "rag": rag_meta,
    }
    _dump_json(META_PATH, meta)
    return meta


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def live_events() -> list[dict] | None:
    rows = load_json(EVENTS_JSON)
    return [_hydrate(row) for row in rows] if rows else None


def live_adaptations() -> list[dict] | None:
    rows = load_json(ADAPTATIONS_JSON)
    return [_hydrate(row) for row in rows] if rows else None


def live_announced() -> list[dict]:
    return load_json(ANNOUNCED_JSON, []) or []


def live_overlay() -> dict:
    return load_json(OVERLAY_JSON, {}) or {}


def live_meta() -> dict:
    return load_json(META_PATH, {}) or {}


def main() -> None:
    meta = refresh_live_database(fetch=True)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
