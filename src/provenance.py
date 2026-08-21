"""Source and first-seen (entry) date helpers for product/event rows."""

from __future__ import annotations

from datetime import date


def today_iso(on: date | None = None) -> str:
    return (on or date.today()).isoformat()


def display_source(row: dict) -> str:
    """Human-readable provenance for sheets and UI."""
    official = (row.get("official_source") or "").strip()
    if official:
        return official
    source = (row.get("source") or "").strip()
    if source:
        return source
    if row.get("wikipedia_url"):
        return "wikipedia"
    if row.get("wikidata_id"):
        return "wikidata"
    return "catalog"


def stamp_provenance(row: dict, *, default_source: str = "", on: date | None = None) -> dict:
    """Ensure every row has a source and a stable entry_date (first seen)."""
    out = dict(row)
    day = today_iso(on)
    if not (out.get("source") or "").strip():
        out["source"] = default_source or display_source(out)
    if not (out.get("entry_date") or "").strip():
        # Prefer an earlier known stamp over inventing "today" for historical rows.
        out["entry_date"] = (
            (out.get("last_checked") or "").strip()
            or (out.get("release_date") or out.get("start_date") or "")[:10]
            or day
        )
    if not (out.get("last_checked") or "").strip():
        out["last_checked"] = day
    return out


def preserve_entry_date(existing: dict, incoming: dict, merged: dict, *, on: date | None = None) -> dict:
    """Keep the earliest entry_date across merges; never let a refresh overwrite it."""
    candidates = [
        (existing.get("entry_date") or "").strip(),
        (incoming.get("entry_date") or "").strip(),
        (merged.get("entry_date") or "").strip(),
    ]
    dated = sorted(c for c in candidates if c)
    merged["entry_date"] = dated[0] if dated else today_iso(on)
    if not (merged.get("source") or "").strip():
        merged["source"] = display_source(incoming) if incoming.get("source") else display_source(existing)
    return merged
