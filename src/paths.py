import sys
from pathlib import Path

def _root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _root()
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DAILY_DIR = DATA_PROCESSED / "daily"

CATALOG_CSV = DATA_RAW / "game_products.csv"
CATALOG_CSV_GZ = DATA_RAW / "game_products.csv.gz"
CALENDAR_ODS = DATA_RAW / "events_and_adaptations.ods"

# Fallback if the large catalog copy was gitignored / not copied.
ORIGINAL_CATALOG_CSV = Path(
    "/Users/driffle/Downloads/"
    "list_of_all_game_products_by_release_date___project_data___2026-08-12T07_18_22.452484Z.csv"
)
ORIGINAL_CALENDAR_ODS = Path(
    "/Users/driffle/Desktop/RAGPredictionGameProjectDataset.ods"
)


def catalog_path() -> Path:
    if CATALOG_CSV.exists():
        return CATALOG_CSV
    if CATALOG_CSV_GZ.exists():
        return CATALOG_CSV_GZ
    if ORIGINAL_CATALOG_CSV.exists():
        return ORIGINAL_CATALOG_CSV
    raise FileNotFoundError(
        f"Catalog CSV not found at {CATALOG_CSV}, {CATALOG_CSV_GZ}, or {ORIGINAL_CATALOG_CSV}"
    )


def calendar_path() -> Path:
    if CALENDAR_ODS.exists():
        return CALENDAR_ODS
    if ORIGINAL_CALENDAR_ODS.exists():
        return ORIGINAL_CALENDAR_ODS
    raise FileNotFoundError(
        f"Calendar ODS not found at {CALENDAR_ODS} or {ORIGINAL_CALENDAR_ODS}"
    )
