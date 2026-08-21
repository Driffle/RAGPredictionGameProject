"""Daily audits: official-date mismatches + day-over-day product/event changes."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.official_dates import OFFICIAL_EVENT_DATES, audit_product_dates
from src.paths import DAILY_DIR, DATA_PROCESSED
from src.provenance import display_source

SNAPSHOT_DIR = DATA_PROCESSED / "live" / "snapshots"
CHANGES_FIELDS = [
    "as_of",
    "kind",
    "change_type",
    "title",
    "field",
    "before",
    "after",
    "source",
    "detail",
]


def _norm(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _conf(row: dict) -> str:
    return _norm(row.get("confirmation") or row.get("status") or row.get("date_status")).lower()


def _is_cancelled(text: str) -> bool:
    return any(token in text for token in ("cancel", "cancelled", "canceled", "scrapped", "abandoned"))


def _is_confirmed(text: str) -> bool:
    return "confirm" in text or text in {"known cycle", "released / catalog", "released"}


def _is_unconfirmed(text: str) -> bool:
    return any(token in text for token in ("tba", "announce", "rumor", "unconfirm", "tbd", "window"))


def product_key(row: dict) -> str:
    return _norm(row.get("canonical_title") or row.get("product_title")).lower()


def event_key(row: dict) -> str:
    name = _norm(row.get("event") or row.get("ip_adaptation")).lower()
    if row.get("source") == "announced_product_window":
        return f"{name}|release-window"
    start = _norm(row.get("start_date"))[:7]
    return f"{name}|{start}"


def _index(rows: list[dict], key_fn) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        key = key_fn(row)
        if key:
            out[key] = row
    return out


def classify_product_change(before: dict, after: dict) -> list[dict]:
    """Detect delays, advances, cancellations, confirmation flips, title/date edits."""
    changes: list[dict] = []
    title = after.get("canonical_title") or before.get("canonical_title") or ""
    source = display_source(after) or display_source(before)

    old_date = _norm(before.get("release_date"))[:10]
    new_date = _norm(after.get("release_date"))[:10]
    if old_date and new_date and old_date != new_date:
        change_type = "delayed" if new_date > old_date else "advanced"
        changes.append(
            {
                "kind": "product",
                "change_type": change_type,
                "title": title,
                "field": "release_date",
                "before": old_date,
                "after": new_date,
                "source": source,
                "detail": f"Release moved {old_date} → {new_date}",
            }
        )

    old_title = _norm(before.get("canonical_title") or before.get("product_title"))
    new_title = _norm(after.get("canonical_title") or after.get("product_title"))
    if old_title and new_title and old_title.lower() != new_title.lower():
        changes.append(
            {
                "kind": "product",
                "change_type": "title_changed",
                "title": new_title,
                "field": "canonical_title",
                "before": old_title,
                "after": new_title,
                "source": source,
                "detail": f"Title renamed {old_title} → {new_title}",
            }
        )

    old_c, new_c = _conf(before), _conf(after)
    if old_c != new_c:
        if _is_cancelled(new_c) and not _is_cancelled(old_c):
            change_type = "cancelled"
        elif _is_unconfirmed(old_c) and _is_confirmed(new_c):
            change_type = "confirmed"
        else:
            change_type = "confirmation_changed"
        changes.append(
            {
                "kind": "product",
                "change_type": change_type,
                "title": title,
                "field": "confirmation",
                "before": old_c or "(empty)",
                "after": new_c or "(empty)",
                "source": source,
                "detail": f"Confirmation {old_c or '—'} → {new_c or '—'}",
            }
        )
    return changes


def classify_event_change(before: dict, after: dict) -> list[dict]:
    changes: list[dict] = []
    title = after.get("event") or after.get("ip_adaptation") or before.get("event") or ""
    source = display_source(after) or display_source(before)

    old_start = _norm(before.get("start_date"))[:10]
    new_start = _norm(after.get("start_date"))[:10]
    old_end = _norm(before.get("end_date"))[:10]
    new_end = _norm(after.get("end_date"))[:10]
    if (old_start and new_start and old_start != new_start) or (old_end and new_end and old_end != new_end):
        change_type = "delayed" if (new_start or "") > (old_start or "") else "date_changed"
        if old_start and new_start and new_start < old_start:
            change_type = "advanced"
        changes.append(
            {
                "kind": "event",
                "change_type": change_type,
                "title": title,
                "field": "runtime",
                "before": f"{old_start} → {old_end}",
                "after": f"{new_start} → {new_end}",
                "source": source,
                "detail": f"Event window moved {old_start}/{old_end} → {new_start}/{new_end}",
            }
        )

    old_name = _norm(before.get("event") or before.get("ip_adaptation"))
    new_name = _norm(after.get("event") or after.get("ip_adaptation"))
    if old_name and new_name and old_name.lower() != new_name.lower():
        changes.append(
            {
                "kind": "event",
                "change_type": "title_changed",
                "title": new_name,
                "field": "name",
                "before": old_name,
                "after": new_name,
                "source": source,
                "detail": f"Event renamed {old_name} → {new_name}",
            }
        )

    old_c, new_c = _conf(before), _conf(after)
    if old_c != new_c:
        if _is_cancelled(new_c) and not _is_cancelled(old_c):
            change_type = "cancelled"
        elif _is_unconfirmed(old_c) and _is_confirmed(new_c):
            change_type = "confirmed"
        else:
            change_type = "confirmation_changed"
        changes.append(
            {
                "kind": "event",
                "change_type": change_type,
                "title": title,
                "field": "confirmation",
                "before": old_c or "(empty)",
                "after": new_c or "(empty)",
                "source": source,
                "detail": f"Confirmation {old_c or '—'} → {new_c or '—'}",
            }
        )
    return changes


def diff_datasets(
    *,
    prev_products: list[dict],
    next_products: list[dict],
    prev_events: list[dict],
    next_events: list[dict],
    on: date | None = None,
) -> list[dict]:
    """Compare yesterday's snapshot to today's rebuild."""
    day = (on or date.today()).isoformat()
    changes: list[dict] = []

    before_p = _index(prev_products, product_key)
    after_p = _index(next_products, product_key)
    for key, row in after_p.items():
        if key not in before_p:
            changes.append(
                {
                    "as_of": day,
                    "kind": "product",
                    "change_type": "added",
                    "title": row.get("canonical_title") or row.get("product_title") or key,
                    "field": "presence",
                    "before": "",
                    "after": "added",
                    "source": display_source(row),
                    "detail": "New product entered the live dataset",
                }
            )
        else:
            for item in classify_product_change(before_p[key], row):
                changes.append({"as_of": day, **item})
    for key, row in before_p.items():
        if key not in after_p:
            changes.append(
                {
                    "as_of": day,
                    "kind": "product",
                    "change_type": "removed",
                    "title": row.get("canonical_title") or row.get("product_title") or key,
                    "field": "presence",
                    "before": "present",
                    "after": "removed",
                    "source": display_source(row),
                    "detail": "Product left the live dataset",
                }
            )

    before_e = _index(prev_events, event_key)
    after_e = _index(next_events, event_key)
    # Also match release windows / renamed months by bare name when keys diverge.
    before_by_name = {
        _norm(row.get("event") or row.get("ip_adaptation")).lower(): row for row in prev_events if row.get("event") or row.get("ip_adaptation")
    }
    for key, row in after_e.items():
        if key in before_e:
            for item in classify_event_change(before_e[key], row):
                changes.append({"as_of": day, **item})
            continue
        name = _norm(row.get("event") or row.get("ip_adaptation")).lower()
        if name and name in before_by_name and event_key(before_by_name[name]) != key:
            for item in classify_event_change(before_by_name[name], row):
                changes.append({"as_of": day, **item})
            continue
        changes.append(
            {
                "as_of": day,
                "kind": "event",
                "change_type": "added",
                "title": row.get("event") or row.get("ip_adaptation") or key,
                "field": "presence",
                "before": "",
                "after": "added",
                "source": display_source(row),
                "detail": "New event entered the live dataset",
            }
        )
    for key, row in before_e.items():
        if key not in after_e:
            name = _norm(row.get("event") or row.get("ip_adaptation")).lower()
            still = any(
                _norm(r.get("event") or r.get("ip_adaptation")).lower() == name for r in next_events
            )
            if still:
                continue
            changes.append(
                {
                    "as_of": day,
                    "kind": "event",
                    "change_type": "removed",
                    "title": row.get("event") or row.get("ip_adaptation") or key,
                    "field": "presence",
                    "before": "present",
                    "after": "removed",
                    "source": display_source(row),
                    "detail": "Event left the live dataset",
                }
            )
    return changes


def audit_event_dates(rows: list[dict]) -> list[dict]:
    """Flag events that disagree with pinned organizer dates."""
    issues: list[dict] = []
    for row in rows:
        name = _norm(row.get("event") or row.get("ip_adaptation")).lower()
        year_map = OFFICIAL_EVENT_DATES.get(name)
        if not year_map:
            continue
        start = _norm(row.get("start_date"))[:10]
        try:
            year = int(start[:4])
        except ValueError:
            continue
        patch = year_map.get(year)
        if not patch:
            continue
        if start != patch["start_date"] or _norm(row.get("end_date"))[:10] != patch["end_date"]:
            issues.append(
                {
                    "title": row.get("event") or row.get("ip_adaptation"),
                    "stored": f"{start} → {_norm(row.get('end_date'))[:10]}",
                    "expected": f"{patch['start_date']} → {patch['end_date']}",
                    "source": patch["source_note"],
                }
            )
    return issues


def _jsonable(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def save_snapshot(products: list[dict], events: list[dict], *, on: date | None = None) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    day = (on or date.today()).isoformat()
    path = SNAPSHOT_DIR / f"{day}.json"
    path.write_text(
        json.dumps(
            _jsonable({"as_of": day, "products": products, "events": events}),
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def load_previous_snapshot(*, on: date | None = None) -> dict | None:
    if not SNAPSHOT_DIR.exists():
        return None
    day = (on or date.today()).isoformat()
    candidates = sorted(
        (path for path in SNAPSHOT_DIR.glob("*.json") if path.stem < day),
        key=lambda path: path.stem,
        reverse=True,
    )
    if not candidates:
        return None
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def write_changes(changes: list[dict], *, on: date | None = None) -> Path:
    day = (on or date.today()).isoformat()
    folder = DAILY_DIR / day
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / "changes.json"
    json_path.write_text(json.dumps(changes, indent=2), encoding="utf-8")
    csv_path = folder / "changes.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHANGES_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in changes:
            writer.writerow(row)
    return json_path


def load_changes(day: date | None = None) -> list[dict]:
    path = DAILY_DIR / (day or date.today()).isoformat() / "changes.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def run_audits(
    *,
    products: list[dict],
    events: list[dict],
    on: date | None = None,
) -> dict:
    """Official-date audit + day-over-day change log for today's rebuild."""
    day = on or date.today()
    previous = load_previous_snapshot(on=day) or {"products": [], "events": []}
    changes = diff_datasets(
        prev_products=previous.get("products") or [],
        next_products=products,
        prev_events=previous.get("events") or [],
        next_events=events,
        on=day,
    )
    product_issues = audit_product_dates(products)
    event_issues = audit_event_dates(events)
    write_changes(changes, on=day)
    save_snapshot(products, events, on=day)

    summary = {
        "as_of": day.isoformat(),
        "change_count": len(changes),
        "by_type": {},
        "product_official_mismatches": product_issues,
        "event_official_mismatches": event_issues,
        "changes": changes[:80],
    }
    for row in changes:
        key = row.get("change_type") or "other"
        summary["by_type"][key] = summary["by_type"].get(key, 0) + 1

    audit_path = DAILY_DIR / day.isoformat() / "audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
