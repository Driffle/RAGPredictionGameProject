"""Collapse duplicate calendar rows so event listings show one window each.

The live calendar mixes horizon templates, historical registry rows, ODS
planning stubs, and entertainment titles copied into both events and
adaptations. Listings should keep distinct editions (Steam Next Fest in
February vs June) but not "Gamescom" beside "Gamescom 2026" for the same
dates, or a film listed once as an event and again as an adaptation.
"""

from __future__ import annotations

import re

from src.date_range import event_window
from src.dates import confirmation_kind

YEAR_SUFFIX = re.compile(r"\s+20\d{2}\s*$")
# Bare fiscal quarters are merchandising timeframes, not named events.
# Matches Q3, Q3/Q4, 2026 Q4, Q1 2026 window, Q3 release window, etc.
QUARTER_TIMEFRAME_RE = re.compile(
    r"""
    ^
    (?:(?:fy|cy)\s*)?
    (?:20\d{2}\s+)?
    q\s*[1-4]
    (?:\s*[/,&+|–—-]\s*q\s*[1-4])?
    (?:\s+20\d{2})?
    (?:\s+(?:planning\s+|release\s+)?window)?
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)
NEAR_DAYS = 21
PRECISION_SCORE = {"day": 3, "month": 2, "quarter": 1, "year": 0}
CONFIRM_SCORE = {"confirmed": 3, "tentative": 1, "cancelled": 0}
ENTERTAINMENT_HINTS = (
    "film",
    "movie",
    "series",
    "ott",
    "anime",
    "theatrical",
    "streaming",
    "adaptation",
    "animated",
)

FILL_KEYS = (
    "wikipedia_url",
    "official_source",
    "summary",
    "location",
    "organizer",
    "related_game",
    "correlated_announced",
    "country",
    "country_code",
    "language",
    "locale",
    "attendance_mode",
    "scope",
)


def calendar_name(row: dict) -> str:
    return (row.get("event") or row.get("ip_adaptation") or row.get("name") or "").strip()


def is_product_release_window(row: dict | str | None) -> bool:
    """True for merchandising pads around a SKU launch, not a named event."""
    if not isinstance(row, dict):
        name = str(row or "").lower()
        return "release window" in name
    source = (row.get("source") or "").lower()
    event_type = (row.get("event_type") or row.get("type") or row.get("medium") or "").lower()
    category = (row.get("category") or "").lower()
    name = calendar_name(row).lower()
    if source == "announced_product_window":
        return True
    if event_type == "product release":
        return True
    if "release window" in name:
        return True
    if "announced product" in category:
        return True
    return False


def is_quarter_timeframe(value: dict | str | None) -> bool:
    """True when a listing is a Q1–Q4 window, not a named event."""
    name = calendar_name(value) if isinstance(value, dict) else (value or "")
    return bool(QUARTER_TIMEFRAME_RE.match(" ".join(name.split())))


def canonical_event_name(row: dict | str) -> str:
    name = calendar_name(row) if isinstance(row, dict) else (row or "")
    name = YEAR_SUFFIX.sub("", name)
    return " ".join(name.lower().split())


def listing_key(row: dict) -> tuple[str, str]:
    start = (row.get("start_date") or row.get("runtime_start") or row.get("start") or "")[:10]
    return canonical_event_name(row), start


def _quality(row: dict) -> tuple:
    name = calendar_name(row)
    precision = (row.get("date_precision") or "").lower()
    kind = (row.get("kind") or "event").lower()
    return (
        1 if row.get("official_source") else 0,
        CONFIRM_SCORE.get(confirmation_kind(row), 1),
        PRECISION_SCORE.get(precision, 0),
        1 if row.get("wikipedia_url") else 0,
        1 if YEAR_SUFFIX.search(name) else 0,
        1 if kind == "adaptation" else 0,
        name.lower(),
    )


def _is_entertainment(row: dict) -> bool:
    if (row.get("kind") or "").lower() == "adaptation":
        return True
    blob = f"{row.get('event_type') or ''} {row.get('medium') or ''} {row.get('format') or ''} {row.get('category') or ''}".lower()
    return any(token in blob for token in ENTERTAINMENT_HINTS)


SPORTS_ONLY_TYPES = {
    "golf",
    "tennis",
    "basketball",
    "ice hockey",
    "baseball",
    "american football",
    "motorsport",
    "cycling",
    "football",
    "soccer",
}


def is_gaming_world_event(row: dict) -> bool:
    """Industry, expo, showcase, esports, and fan events — not sports or films."""
    if is_quarter_timeframe(row):
        return False
    if (row.get("kind") or "event").lower() == "adaptation":
        return False
    source = (row.get("source") or "").lower()
    if source in {"announced_product_window"}:
        return False
    event_type = (row.get("event_type") or row.get("medium") or "").strip().lower()
    category = (row.get("category") or "").strip().lower()
    name = calendar_name(row).lower()
    if event_type == "product release" or "announced product" in category or "release window" in name:
        return False
    if _is_entertainment(row) and "gaming" not in category and "esport" not in category:
        return False
    blob = f"{category} {event_type} {name}"
    if any(token in blob for token in ("gaming", "esport", "game show", "gamescom", "game awards", "game developers")):
        return True
    if "sport" in category and "esport" not in category and "gaming" not in category:
        return False
    if event_type in SPORTS_ONLY_TYPES:
        return False
    return any(
        token in event_type
        for token in (
            "expo",
            "showcase",
            "conference",
            "festival",
            "convention",
            "awards",
            "esports",
            "fighting",
            "direct",
            "publisher",
            "hardware",
        )
    )


def _near_or_overlap(left: dict, right: dict, *, near_days: int = NEAR_DAYS) -> bool:
    a_start, a_end = event_window(left)
    b_start, b_end = event_window(right)
    if not a_start or not b_start:
        return listing_key(left) == listing_key(right) and listing_key(left)[1] != ""
    a_end = a_end or a_start
    b_end = b_end or b_start
    if a_start <= b_end and b_start <= a_end:
        return True
    gap = (b_start - a_end).days if a_end < b_start else (a_start - b_end).days
    if 0 <= gap <= near_days:
        return True
    if a_start.year == b_start.year and (_is_entertainment(left) or _is_entertainment(right)):
        return True
    return False


def _merge_row(winner: dict, loser: dict) -> dict:
    out = dict(winner)
    for key in FILL_KEYS:
        if not (out.get(key) or "").strip() and (loser.get(key) or "").strip():
            out[key] = loser[key]
    return out


def unique_event_listings(rows: list[dict]) -> list[dict]:
    """Keep the first row for each canonical name + start date."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for row in rows:
        if is_quarter_timeframe(row):
            continue
        key = listing_key(row)
        if not key[0]:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def dedupe_calendar_rows(rows: list[dict], *, near_days: int = NEAR_DAYS) -> list[dict]:
    """One row per overlapping (or nearly overlapping) window of the same event."""
    groups: dict[str, list[dict]] = {}
    leftover: list[dict] = []
    for row in rows:
        if is_quarter_timeframe(row):
            continue
        key = canonical_event_name(row)
        if not key:
            leftover.append(row)
            continue
        groups.setdefault(key, []).append(row)

    kept: list[dict] = []
    for bucket in groups.values():
        ordered = sorted(bucket, key=_quality, reverse=True)
        winners: list[dict] = []
        for row in ordered:
            match_at = next((i for i, existing in enumerate(winners) if _near_or_overlap(existing, row, near_days=near_days)), None)
            if match_at is None:
                winners.append(dict(row))
            else:
                winners[match_at] = _merge_row(winners[match_at], row)
        kept.extend(winners)

    kept.extend(leftover)
    kept.sort(key=lambda row: (row.get("start_date") or "9999", calendar_name(row).lower()))
    return kept


def split_deduped_calendar(events: list[dict], adaptations: list[dict]) -> tuple[list[dict], list[dict]]:
    combined = dedupe_calendar_rows(list(events) + list(adaptations))
    out_events: list[dict] = []
    out_adaptations: list[dict] = []
    for row in combined:
        if (row.get("kind") or "event").lower() == "adaptation":
            out_adaptations.append(row)
        else:
            out_events.append(row)
    return out_events, out_adaptations
