"""Load the product catalog CSV and the events/adaptations ODS calendar."""

from __future__ import annotations

import csv
import gzip
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from src.paths import calendar_path, catalog_path

NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}

GAME_TYPES = {"game", "dlc", "dlc,game"}
PLACEHOLDER_DATE = date(2079, 1, 1)
# Storefront exports occasionally carry corrupt stamps like 0017-01-01 or
# 0018-01-01; anything before the medium existed is treated as unknown.
MIN_VALID_YEAR = 1971


def parse_date(value: str | None) -> date | None:
    """Parse catalog ISO dates or calendar DD/MM/YYYY values (optional trailing +)."""
    if not value:
        return None
    text = value.strip().rstrip("+").strip()
    if not text:
        return None
    iso = text[:10]
    if len(iso) == 10 and iso[4] == "-" and iso[7] == "-":
        try:
            parsed = date.fromisoformat(iso)
            return parsed if parsed.year >= MIN_VALID_YEAR else None
        except ValueError:
            pass
    candidates = [text]
    if len(text) >= 10:
        candidates.append(text[:10])
    for candidate in candidates:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
            if parsed.year < MIN_VALID_YEAR:
                return None
            return parsed
    return None


def gzip_sidecar(path: Path) -> Path:
    return Path(str(path) + ".gz")


def open_tabular(path: Path):
    """Open a CSV, preferring a newer or only `.gz` sidecar when present."""
    gz = gzip_sidecar(path)
    target = path
    if str(path).endswith(".gz"):
        target = path
    elif gz.exists() and (not path.exists() or gz.stat().st_mtime >= path.stat().st_mtime):
        target = gz
    elif not path.exists() and gz.exists():
        target = gz
    if str(target).endswith(".gz"):
        return gzip.open(target, "rt", encoding="utf-8", newline="")
    return target.open(newline="", encoding="utf-8")


def is_game_product(product_type: str | None) -> bool:
    value = (product_type or "").strip().lower()
    if "gift" in value:
        return False
    return value in GAME_TYPES or value.startswith("dlc") or value.startswith("game")


def canonical_title(title: str | None) -> str:
    """Strip region / platform / storefront suffixes from a catalog title."""
    if not title:
        return ""
    text = title.strip()
    for sep in (" - Steam - ", " - Xbox Live - ", " - PSN - ", " - Nintendo - ", " - Epic Games - "):
        if sep in text:
            text = text.split(sep, 1)[0]
    if " (" in text:
        text = text.split(" (", 1)[0]
    return text.strip()


def load_catalog(*, games_only: bool = True, drop_placeholder_dates: bool = True, include_live: bool = True) -> list[dict]:
    """Load catalog rows. Gift cards are dropped when games_only=True."""
    rows: list[dict] = []
    with open_tabular(catalog_path()) as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            product_type = (raw.get("product_type") or "").strip()
            if games_only and not is_game_product(product_type):
                continue
            release = parse_date(raw.get("release_date"))
            if drop_placeholder_dates and release and release >= PLACEHOLDER_DATE:
                release = None
            title = (raw.get("product_title") or "").strip()
            rows.append(
                {
                    "product_id": (raw.get("product_id") or "").strip(),
                    "product_title": title,
                    "canonical_title": canonical_title(title),
                    "product_sku": (raw.get("product_sku") or "").strip(),
                    "slug": (raw.get("slug") or "").strip(),
                    "product_type": product_type,
                    "platform": (raw.get("platform") or "").strip(),
                    "platform_id": (raw.get("platform_id") or "").strip(),
                    "status": (raw.get("status") or "").strip(),
                    "release_date": release.isoformat() if release else "",
                    "release_date_parsed": release,
                }
            )
    if include_live:
        rows = _apply_live_catalog(rows, games_only=games_only)
    return rows


def _apply_live_catalog(rows: list[dict], *, games_only: bool) -> list[dict]:
    from src.database import live_announced, live_overlay

    overlay = live_overlay()
    for row in rows:
        extra = overlay.get((row.get("canonical_title") or "").lower()) or {}
        for key, value in extra.items():
            if value:
                row[key] = value
    existing = {(row.get("canonical_title") or "").lower() for row in rows}
    for item in live_announced():
        key = (item.get("canonical_title") or "").lower()
        if not key or key in existing:
            continue
        if games_only and (item.get("product_type") or "announced") == "gift":
            continue
        parsed = parse_date(item.get("release_date"))
        item = dict(item)
        item["release_date_parsed"] = parsed
        if parsed and not item.get("release_date"):
            item["release_date"] = parsed.isoformat()
        rows.append(item)
        existing.add(key)
    return rows


def _cell_text(cell: ET.Element) -> str:
    parts = [node.text or "" for node in cell.findall(".//text:p", NS)]
    return " ".join(parts).strip()


def _expand_row(row: ET.Element) -> list[str]:
    values: list[str] = []
    for cell in row.findall("table:table-cell", NS):
        repeat = int(cell.get(f"{{{NS['table']}}}number-columns-repeated") or 1)
        text = _cell_text(cell)
        if repeat > 40 and not text:
            break
        values.extend([text] * min(repeat, 12))
    while values and not values[-1]:
        values.pop()
    return values


def _ods_rows(path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    sheet = root.find(".//table:table", NS)
    if sheet is None:
        return []
    rows = []
    for row in sheet.findall("table:table-row", NS):
        values = _expand_row(row)
        if any(value.strip() for value in values):
            rows.append(values)
    return rows


def _row_kind(values: list[str]) -> str | None:
    if not values or values[0].strip().lower() != "start date":
        return None
    third = values[2].strip().lower() if len(values) > 2 else ""
    if third == "event":
        return "events_header"
    if "adaptation" in third or third.startswith("ip"):
        return "adaptations_header"
    return "header"


def load_calendar() -> dict[str, list[dict]]:
    """Split the ODS into industry events and media adaptations."""
    events: list[dict] = []
    adaptations: list[dict] = []
    section = None
    for values in _ods_rows(calendar_path()):
        kind = _row_kind(values)
        if kind == "events_header":
            section = "events"
            continue
        if kind == "adaptations_header":
            section = "adaptations"
            continue
        if kind == "header":
            continue
        padded = values + [""] * 7
        start = parse_date(padded[0])
        end = parse_date(padded[1])
        if section == "events":
            events.append(
                {
                    "kind": "event",
                    "start_date": start.isoformat() if start else "",
                    "end_date": end.isoformat() if end else "",
                    "start_date_parsed": start,
                    "end_date_parsed": end,
                    "event": padded[2].strip(),
                    "category": padded[3].strip(),
                    "related_game": padded[4].strip(),
                    "event_type": padded[5].strip(),
                    "status": padded[6].strip(),
                    "source": "ods",
                    "entry_date": start.isoformat() if start else "",
                }
            )
        elif section == "adaptations":
            adaptations.append(
                {
                    "kind": "adaptation",
                    "start_date": start.isoformat() if start else "",
                    "end_date": end.isoformat() if end else "",
                    "start_date_parsed": start,
                    "end_date_parsed": end,
                    "ip_adaptation": padded[2].strip(),
                    "medium": padded[3].strip(),
                    "distributor": padded[4].strip(),
                    "related_game": padded[5].strip(),
                    "date_status": padded[6].strip(),
                    "source": "ods",
                    "entry_date": start.isoformat() if start else "",
                }
            )
    return {"events": events, "adaptations": adaptations}


def load_events() -> list[dict]:
    from src.database import live_events

    rows = live_events()
    return rows if rows else load_calendar()["events"]


def load_adaptations() -> list[dict]:
    from src.database import live_adaptations

    rows = live_adaptations()
    return rows if rows else load_calendar()["adaptations"]
