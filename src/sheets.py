"""Export product and event datasets to Excel workbooks with provenance columns."""

from __future__ import annotations

from pathlib import Path

from src.paths import DATA_PROCESSED
from src.provenance import display_source, stamp_provenance

SHEETS_DIR = DATA_PROCESSED / "sheets"


def _rows_for_sheet(rows: list[dict], columns: list[str]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        stamped = stamp_provenance(row)
        payload = {col: stamped.get(col, "") for col in columns}
        payload["source"] = display_source(stamped)
        out.append(payload)
    return out


def _write_workbook(path: Path, sheets: dict[str, tuple[list[str], list[dict]]]) -> Path:
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    book.remove(book.active)
    for title, (columns, rows) in sheets.items():
        worksheet = book.create_sheet(title[:31])
        worksheet.append(columns)
        for row in _rows_for_sheet(rows, columns):
            worksheet.append([row.get(col, "") for col in columns])
    book.save(path)
    return path


PRODUCT_COLUMNS = [
    "product_id",
    "canonical_title",
    "product_title",
    "product_sku",
    "product_type",
    "platform",
    "platforms",
    "status",
    "confirmation",
    "release_date",
    "release_start",
    "release_end",
    "date_precision",
    "release_label",
    "genre",
    "developer",
    "publisher",
    "franchise",
    "wikipedia_url",
    "source",
    "official_source",
    "entry_date",
    "last_checked",
]

EVENT_COLUMNS = [
    "event",
    "ip_adaptation",
    "kind",
    "category",
    "event_type",
    "medium",
    "format",
    "related_game",
    "start_date",
    "end_date",
    "runtime_start",
    "runtime_end",
    "date_precision",
    "date_label",
    "status",
    "confirmation",
    "date_status",
    "attendance_mode",
    "scope",
    "location",
    "organizer",
    "distributor",
    "wikipedia_url",
    "source",
    "official_source",
    "entry_date",
    "last_checked",
    "correlated_announced",
]


def export_dataset_sheets(
    *,
    products: list[dict],
    announced: list[dict],
    events: list[dict],
    adaptations: list[dict],
) -> dict[str, str]:
    """Write Excel sheets used by the daily rebuild (source + entry_date included)."""
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "products": _write_workbook(
            SHEETS_DIR / "products.xlsx",
            {
                "Products": (PRODUCT_COLUMNS, products),
                "Announced": (PRODUCT_COLUMNS, announced),
            },
        ),
        "events": _write_workbook(
            SHEETS_DIR / "events.xlsx",
            {
                "Events": (EVENT_COLUMNS, events),
                "Adaptations": (EVENT_COLUMNS, adaptations),
            },
        ),
    }
    return {name: str(path) for name, path in paths.items()}
