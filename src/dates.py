"""Release/runtime date precision helpers.

Datasets mix exact dates with month, quarter, and year-wide announcements.
Storing only a single ISO day loses that distinction and makes a Q4/TBA row
look like a 31 December release. These helpers keep the representative day
but also record how precise it is, the true window it covers, and a label
the UI can show ("September 2026" instead of "1 Sep 2026").
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

PRECISIONS = ("day", "month", "quarter", "year")


def parse_iso(value: str | date | None) -> date | None:
    if isinstance(value, date):
        return value
    text = (value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def infer_precision(value: str | date | None, confirmation: str | None = None) -> str:
    """Guess how precise a stored date is.

    Legacy rows encode year-wide/TBA windows as 31 December and quarter or
    month windows as the first day of the period.
    """
    day = parse_iso(value)
    if day is None:
        return "year"
    status = (confirmation or "").lower()
    if day.month == 12 and day.day == 31:
        return "year"
    if "tba" in status or "tbd" in status:
        return "year" if day.day == 1 and day.month == 1 else "month"
    if day.day == 1:
        return "quarter" if day.month in (1, 4, 7, 10) else "month"
    return "day"


def window_for(value: str | date | None, precision: str | None = None) -> tuple[date | None, date | None]:
    """Inclusive (start, end) span the date actually represents."""
    day = parse_iso(value)
    if day is None:
        return None, None
    level = precision if precision in PRECISIONS else infer_precision(day)
    if level == "day":
        return day, day
    if level == "month":
        return date(day.year, day.month, 1), date(day.year, day.month, monthrange(day.year, day.month)[1])
    if level == "quarter":
        first_month = 1 + 3 * ((day.month - 1) // 3)
        last_month = first_month + 2
        return (
            date(day.year, first_month, 1),
            date(day.year, last_month, monthrange(day.year, last_month)[1]),
        )
    return date(day.year, 1, 1), date(day.year, 12, 31)


def label_for(value: str | date | None, precision: str | None = None) -> str:
    day = parse_iso(value)
    if day is None:
        return "TBA"
    level = precision if precision in PRECISIONS else infer_precision(day)
    if level == "day":
        return f"{day.day} {MONTH_NAMES[day.month - 1][:3]} {day.year}"
    if level == "month":
        return f"{MONTH_NAMES[day.month - 1]} {day.year}"
    if level == "quarter":
        return f"Q{1 + (day.month - 1) // 3} {day.year}"
    return str(day.year)


def describe(value: str | date | None, *, confirmation: str | None = None, precision: str | None = None) -> dict:
    """Precision, window, and display label for one stored date."""
    level = precision if precision in PRECISIONS else infer_precision(value, confirmation)
    start, end = window_for(value, level)
    return {
        "date_precision": level,
        "window_start": start.isoformat() if start else "",
        "window_end": end.isoformat() if end else "",
        "date_label": label_for(value, level),
        "is_exact": level == "day",
    }


def annotate_event(row: dict) -> dict:
    """Add runtime_start / runtime_end / precision / label to a calendar row."""
    out = dict(row)
    confirmation = f"{row.get('confirmation') or ''} {row.get('status') or ''} {row.get('date_status') or ''}"
    stated = row.get("date_precision")
    start_info = describe(row.get("start_date"), confirmation=confirmation, precision=stated)
    end_info = describe(row.get("end_date") or row.get("start_date"), confirmation=confirmation, precision=stated)
    runtime_start = start_info["window_start"] or row.get("start_date") or ""
    runtime_end = end_info["window_end"] or end_info["window_start"] or runtime_start
    if runtime_end and runtime_start and runtime_end < runtime_start:
        runtime_end = runtime_start
    out["date_precision"] = start_info["date_precision"]
    out["runtime_start"] = runtime_start
    out["runtime_end"] = runtime_end
    out["date_label"] = (
        start_info["date_label"]
        if runtime_start == runtime_end or start_info["date_precision"] != "day"
        else f"{start_info['date_label']} → {end_info['date_label']}"
    )
    return out


def annotate_product(row: dict) -> dict:
    """Add release window + precision + label to a catalog/announced row."""
    out = dict(row)
    stated = row.get("date_precision")
    info = describe(
        row.get("release_date"),
        confirmation=f"{row.get('confirmation') or ''} {row.get('status') or ''}",
        precision=stated,
    )
    out["date_precision"] = info["date_precision"]
    out["release_start"] = row.get("release_start") or info["window_start"]
    out["release_end"] = row.get("release_end") or info["window_end"]
    out["release_label"] = info["date_label"]
    return out


def confirmation_kind(row: dict | None) -> str:
    """Normalize a calendar/catalog row to confirmed, tentative, or cancelled."""
    row = row or {}
    blob = f"{row.get('confirmation') or ''} {row.get('status') or ''} {row.get('date_status') or ''}".lower()
    if any(token in blob for token in ("cancel", "cancelled", "canceled", "scrapped", "abandoned")):
        return "cancelled"
    if row.get("official_source") or "confirm" in blob or blob.strip() in {
        "known cycle",
        "released / catalog",
        "released",
        "official",
    }:
        return "confirmed"
    if any(token in blob for token in ("tba", "tbd", "rumor", "unconfirm", "tentative", "planning", "announce")):
        return "tentative"
    precision = (row.get("date_precision") or "").lower()
    if precision in {"month", "quarter", "year"}:
        return "tentative"
    if precision == "day":
        return "confirmed"
    start = row.get("start_date") or row.get("runtime_start") or row.get("release_date") or ""
    return "confirmed" if infer_precision(start, blob) == "day" else "tentative"
