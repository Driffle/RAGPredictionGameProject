"""Date-range calendar: events in a month/year window + promote / cross-sell products.

Notebook 05 and the Floor Brief Calendar page share this module.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Iterable


def parse_month_year(year: int | str, month: int | str) -> tuple[int, int]:
    y = int(year)
    m = int(month)
    if y < 2020 or y > 2035:
        raise ValueError("Year must be between 2020 and 2035")
    if m < 1 or m > 12:
        raise ValueError("Month must be 1–12")
    return y, m


def month_span(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def range_span(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> tuple[date, date]:
    start, _ = month_span(start_year, start_month)
    _, end = month_span(end_year, end_month)
    if end < start:
        start, _ = month_span(end_year, end_month)
        _, end = month_span(start_year, start_month)
    return start, end


def _parse_iso(value: str | None) -> date | None:
    text = (value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def event_window(row: dict) -> tuple[date | None, date | None]:
    """True runtime for a row, falling back to the stored start/end dates.

    `runtime_start` / `runtime_end` carry the precision-aware window, so a
    "September 2026" release matches a September search even though the stored
    representative day is the first of the month.
    """
    start = _parse_iso(row.get("runtime_start")) or _parse_iso(row.get("start_date"))
    end = (
        _parse_iso(row.get("runtime_end"))
        or _parse_iso(row.get("end_date"))
        or start
    )
    if start and end and end < start:
        start, end = end, start
    return start, end


def overlaps(start: date | None, end: date | None, range_start: date, range_end: date) -> bool:
    if not start:
        return False
    finish = end or start
    return start <= range_end and finish >= range_start


def listing_span(row: dict) -> tuple[date | None, date | None]:
    """Runtime for a calendar row or promotion plan."""
    return event_window(
        {
            "runtime_start": row.get("runtime_start")
            or row.get("event_start")
            or row.get("start")
            or row.get("promo_start")
            or row.get("start_date"),
            "runtime_end": row.get("runtime_end")
            or row.get("event_end")
            or row.get("end")
            or row.get("promo_end")
            or row.get("end_date"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
        }
    )


def is_current_or_in_range(
    row: dict,
    *,
    today: date | None = None,
    range_start: date | None = None,
    range_end: date | None = None,
) -> bool:
    """Keep live/future windows, or past ones that still overlap a calendar range."""
    day = today or date.today()
    start, end = listing_span(row)
    finish = end or start
    if finish and finish >= day:
        return True
    if range_start and range_end and start:
        return overlaps(start, finish or start, range_start, range_end)
    return False


PRECISION_RANK = {"day": 0, "month": 1, "quarter": 2, "year": 3}

# What each filter keeps: exact days only, day+month, or everything.
PRECISION_FILTERS = {
    "exact": {"day"},
    "dated": {"day", "month"},
    "all": set(PRECISION_RANK),
}


def row_precision(row: dict) -> str:
    stated = (row.get("date_precision") or "").strip().lower()
    if stated in PRECISION_RANK:
        return stated
    start, end = event_window(row)
    if start and end and start == end:
        return "day"
    return "month"


def events_in_range(
    rows: Iterable[dict],
    range_start: date,
    range_end: date,
    *,
    kind: str = "",
    precision: str = "",
) -> list[dict]:
    """Return calendar/adaptation rows whose runtime overlaps the inclusive range.

    `precision` trims vaguer rows: "exact" keeps confirmed days, "dated" also
    keeps month windows, and anything else keeps quarter/year placeholders too.
    """
    kind_l = (kind or "").strip().lower()
    allowed = PRECISION_FILTERS.get((precision or "all").strip().lower(), PRECISION_FILTERS["all"])
    out: list[dict] = []
    for row in rows:
        if kind_l and (row.get("kind") or "event").lower() != kind_l:
            continue
        if row_precision(row) not in allowed:
            continue
        start, end = event_window(row)
        if overlaps(start, end, range_start, range_end):
            out.append(row)

    def sort_key(row: dict) -> tuple:
        start, _ = event_window(row)
        # Confirmed timing leads; year-wide placeholders sink to the bottom.
        return (
            PRECISION_RANK[row_precision(row)],
            start.isoformat() if start else "9999",
            row.get("event") or row.get("ip_adaptation") or "",
        )

    out.sort(key=sort_key)
    return out


LIVE_EVENT_FLOOR = date(2026, 1, 1)


def event_on_or_after_horizon(row: dict, floor: date = LIVE_EVENT_FLOOR) -> bool:
    """True when an event's runtime starts in the live desk (2026 onward)."""
    start, _ = event_window(row)
    if start:
        return start >= floor
    stamp = (row.get("start_date") or row.get("runtime_start") or row.get("start") or "")[:10]
    return bool(stamp) and stamp >= floor.isoformat()


def calendar_range_payload(
    *,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    events: list[dict],
    adaptations: list[dict],
    plans: list[dict],
    kind: str = "",
    precision: str = "",
    limit: int = 80,
    products_per_event: int = 10,
) -> dict:
    """List overlapping events with promote / cross-sell products for each."""
    from src.calendar_dedupe import dedupe_calendar_rows, unique_event_listings
    from src.cross_sell import cross_sell_payload

    start_year, start_month = parse_month_year(start_year, start_month)
    end_year, end_month = parse_month_year(end_year, end_month)
    range_start, range_end = range_span(start_year, start_month, end_year, end_month)

    pool = list(events) + list(adaptations)
    matched = unique_event_listings(
        dedupe_calendar_rows(events_in_range(pool, range_start, range_end, kind=kind, precision=precision))
    )
    matched = [row for row in matched if event_on_or_after_horizon(row)][: max(1, limit)]

    event_cards = []
    all_titles: dict[str, dict] = {}
    for row in matched:
        name = row.get("event") or row.get("ip_adaptation") or ""
        xs = cross_sell_payload(name, plans=plans, calendar_row=row)
        products = []
        for plan in (xs.get("products") or [])[:products_per_event]:
            title = plan.get("canonical_title") or ""
            item = {
                "canonical_title": title,
                "event": name,
                "role": plan.get("role") or "",
                "platform": plan.get("platform") or "",
                "offer": plan.get("offer") or "",
                "release_date": plan.get("release_date") or "",
                "product_type": plan.get("product_type") or "",
                "promo_family": plan.get("promo_family") or "",
                "promo_start": plan.get("promo_start") or xs.get("promo_start") or "",
                "promo_end": plan.get("promo_end") or xs.get("promo_end") or "",
                "runtime_start": plan.get("runtime_start") or xs.get("runtime_start") or row.get("start_date") or "",
                "runtime_end": plan.get("runtime_end") or xs.get("runtime_end") or row.get("end_date") or "",
                "phases": plan.get("phases") or [],
            }
            products.append(item)
            if title and title.lower() not in all_titles:
                all_titles[title.lower()] = item
        window_start, window_end = event_window(row)
        event_cards.append(
            {
                "name": name,
                "kind": row.get("kind") or "event",
                "start": (window_start.isoformat() if window_start else row.get("start_date") or ""),
                "end": (window_end.isoformat() if window_end else row.get("end_date") or row.get("start_date") or ""),
                "date_precision": row_precision(row),
                "date_label": row.get("date_label") or "",
                "exact_date": row_precision(row) == "day",
                "official_source": row.get("official_source") or "",
                "source": row.get("source") or "",
                "entry_date": row.get("entry_date") or "",
                "last_checked": row.get("last_checked") or "",
                "type": row.get("event_type") or row.get("medium") or "",
                "category": row.get("category") or "",
                "related": row.get("related_game") or "",
                "confirmation": row.get("confirmation") or row.get("status") or row.get("date_status") or "",
                "attendance_mode": row.get("attendance_mode") or "",
                "location": row.get("location") or "",
                "country": row.get("country") or "",
                "language": row.get("language") or "",
                "format": row.get("format") or row.get("medium") or "",
                "correlated_announced": row.get("correlated_announced") or "",
                "wikipedia_url": row.get("wikipedia_url") or "",
                "source": row.get("source") or "",
                "promo_start": xs.get("promo_start") or "",
                "promo_end": xs.get("promo_end") or "",
                "product_count": xs.get("product_count") or len(products),
                "game_count": xs.get("game_count") or 0,
                "attach_count": xs.get("attach_count") or 0,
                "hero": (xs.get("hero") or {}).get("canonical_title") if xs.get("hero") else "",
                "products": products,
                "in_short": (xs.get("in_short") or [])[:3],
            }
        )

    with_products = sum(1 for card in event_cards if card["product_count"])
    exact_count = sum(1 for card in event_cards if card["exact_date"])
    precision_mix: dict[str, int] = {}
    for card in event_cards:
        level = card["date_precision"]
        precision_mix[level] = precision_mix.get(level, 0) + 1
    return {
        "found": True,
        "start_year": start_year,
        "start_month": start_month,
        "end_year": end_year,
        "end_month": end_month,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "kind": kind or "all",
        "precision": (precision or "all").strip().lower(),
        "precision_mix": precision_mix,
        "exact_count": exact_count,
        "event_count": len(event_cards),
        "events_with_products": with_products,
        "unique_products": len(all_titles),
        "in_short": [
            f"Range {range_start.isoformat()} → {range_end.isoformat()}.",
            f"{len(event_cards)} event / release windows overlap this period.",
            f"{exact_count} have a confirmed day; the rest are month/quarter/year windows.",
            f"{with_products} windows have promote / cross-sell products mapped.",
            f"{len(all_titles)} unique catalog titles appear across those windows.",
        ],
        "events": event_cards,
        "products": sorted(all_titles.values(), key=lambda row: (row.get("role") != "game", row.get("canonical_title") or "")),
    }


def format_calendar_range(payload: dict) -> str:
    lines = [
        f"Range: {payload.get('range_start')} → {payload.get('range_end')}",
        f"Events: {payload.get('event_count')} · with products: {payload.get('events_with_products')} · unique SKUs: {payload.get('unique_products')}",
        "",
    ]
    for card in payload.get("events") or []:
        timing = card.get("date_label") or f"{card.get('start')} → {card.get('end') or card.get('start')}"
        precision = card.get("date_precision") or "day"
        marker = "" if card.get("exact_date") else f"  [{precision} window]"
        lines.append(f"{timing}{marker}  {card.get('name')}")
        hero = card.get("hero") or ""
        if hero:
            lines.append(f"   hero: {hero} · products: {card.get('product_count')}")
        for product in (card.get("products") or [])[:5]:
            lines.append(
                f"   - [{product.get('role')}] {product.get('canonical_title')} ({product.get('platform')})"
            )
        if not card.get("products"):
            lines.append("   - (no mapped catalog products yet)")
        lines.append("")
    return "\n".join(lines).rstrip()
