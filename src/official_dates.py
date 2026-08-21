"""Official date overrides confirmed from publisher / organizer sources.

These win over Wikipedia scrapes and horizon planning templates so a stale
year-page parse cannot put The Game Awards in September or leave a released
title on a wrong year.
"""

from __future__ import annotations

# Product titles keyed by lowercase canonical title.
# Sources noted in comments; confirmation must match how firm the date is.
OFFICIAL_PRODUCT_DATES: dict[str, dict] = {
    "grand theft auto vi": {
        "release_date": "2026-11-19",
        "date_precision": "day",
        "confirmation": "confirmed",
        "source_note": "Rockstar Games / Take-Two — rockstargames.com/VI",
    },
    "marvel's wolverine": {
        "release_date": "2026-09-15",
        "date_precision": "day",
        "confirmation": "confirmed",
        "source_note": "Marvel.com / PlayStation Store / Insomniac — Sep 15, 2026",
    },
    "resident evil requiem": {
        "release_date": "2026-02-27",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Capcom press release — Feb 27, 2026",
    },
    "007 first light": {
        "release_date": "2026-05-27",
        "date_precision": "day",
        "confirmation": "confirmed",
        "source_note": "IO Interactive support / 007.com — May 27, 2026",
    },
    "death stranding 2: on the beach": {
        "release_date": "2025-06-26",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Kojima Productions / PlayStation — PS5 Jun 26, 2025 (PC Mar 19, 2026)",
    },
    "mafia: the old country": {
        "release_date": "2025-08-08",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "2K Newsroom — Aug 8, 2025",
    },
    "metroid prime 4: beyond": {
        "release_date": "2025-12-04",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Nintendo — Dec 4, 2025",
    },
    "hollow knight: silksong": {
        "release_date": "2025-09-04",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Team Cherry — Sep 4, 2025",
    },
    "ghost of yōtei": {
        "release_date": "2025-10-02",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "PlayStation Blog — Oct 2, 2025",
    },
    "ghost of yotei": {
        "release_date": "2025-10-02",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "PlayStation Blog — Oct 2, 2025",
    },
    "monster hunter wilds": {
        "release_date": "2025-02-28",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Capcom — Feb 28, 2025",
    },
    "doom: the dark ages": {
        "release_date": "2025-05-15",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Bethesda / id Software — May 15, 2025",
    },
    "fable": {
        "release_date": "2027-02-23",
        "date_precision": "day",
        "confirmation": "confirmed",
        "source_note": "Xbox / Playground Games — Feb 23, 2027",
    },
    "crimson desert": {
        "release_date": "2026-03-19",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Pearl Abyss — Mar 19, 2026",
    },
    "forza horizon 6": {
        "release_date": "2026-05-19",
        "date_precision": "day",
        "confirmation": "released / catalog",
        "source_note": "Forza.net / Playground Games — May 19, 2026 (Xbox/PC)",
    },
}

# Event name (lowercase) → year → override window.
# Only years with a confirmed organizer date are listed.
OFFICIAL_EVENT_DATES: dict[str, dict[int, dict]] = {
    "the game awards": {
        2022: {
            "start_date": "2022-12-08",
            "end_date": "2022-12-08",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2022 in video games — Dec 8, 2022",
        },
        2023: {
            "start_date": "2023-12-07",
            "end_date": "2023-12-07",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2023 in video games — Dec 7, 2023",
        },
        2024: {
            "start_date": "2024-12-12",
            "end_date": "2024-12-12",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2024 in video games — Dec 12, 2024",
        },
        2025: {
            "start_date": "2025-12-11",
            "end_date": "2025-12-11",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2025 in video games — Dec 11, 2025",
        },
        2026: {
            "start_date": "2026-12-10",
            "end_date": "2026-12-10",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "thegameawards.com — Dec 10, 2026",
        },
    },
    "gamescom": {
        2022: {
            "start_date": "2022-08-24",
            "end_date": "2022-08-28",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2022 in video games — Aug 24–28, 2022",
        },
        2023: {
            "start_date": "2023-08-23",
            "end_date": "2023-08-27",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2023 in video games — Aug 23–27, 2023",
        },
        2024: {
            "start_date": "2024-08-21",
            "end_date": "2024-08-25",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2024 in video games — Aug 21–25, 2024",
        },
        2025: {
            "start_date": "2025-08-20",
            "end_date": "2025-08-24",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2025 in video games — Aug 20–24, 2025",
        },
        2026: {
            "start_date": "2026-08-26",
            "end_date": "2026-08-30",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "gamescom.global / Koelnmesse — Aug 26–30, 2026",
        },
    },
    "gamescom opening night live": {
        2026: {
            "start_date": "2026-08-25",
            "end_date": "2026-08-25",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "gamescom.global — Opening Night Live Aug 25, 2026",
        },
    },
    "tokyo game show": {
        2022: {
            "start_date": "2022-09-15",
            "end_date": "2022-09-18",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2022 in video games — Sep 15–18, 2022",
        },
        2023: {
            "start_date": "2023-09-21",
            "end_date": "2023-09-24",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2023 in video games — Sep 21–24, 2023",
        },
        2024: {
            "start_date": "2024-09-26",
            "end_date": "2024-09-29",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2024 in video games — Sep 26–29, 2024",
        },
        2025: {
            "start_date": "2025-09-25",
            "end_date": "2025-09-28",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2025 in video games — Sep 25–28, 2025",
        },
        2026: {
            "start_date": "2026-09-17",
            "end_date": "2026-09-21",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "tgs.cesa.or.jp — Sep 17–21, 2026",
        },
    },
    "summer game fest": {
        2022: {
            "start_date": "2022-06-09",
            "end_date": "2022-06-14",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia Summer Game Fest — Jun 9–14, 2022",
        },
        2023: {
            "start_date": "2023-06-08",
            "end_date": "2023-06-11",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia Summer Game Fest — Jun 8–11, 2023",
        },
        2024: {
            "start_date": "2024-06-07",
            "end_date": "2024-06-10",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia Summer Game Fest — Jun 7–10, 2024",
        },
        2025: {
            "start_date": "2025-06-06",
            "end_date": "2025-06-09",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia Summer Game Fest — Jun 6–9, 2025",
        },
        2026: {
            "start_date": "2026-06-05",
            "end_date": "2026-06-08",
            "confirmation": "confirmed",
            "status": "Confirmed",
            "source_note": "Wikipedia 2026 in video games / VGC — Jun 5–8, 2026",
        },
    },
}


def audit_product_dates(rows: list[dict]) -> list[dict]:
    """Return rows whose stored release date disagrees with a confirmed source."""
    issues: list[dict] = []
    for row in rows:
        title = (row.get("canonical_title") or row.get("product_title") or "").strip().lower()
        patch = OFFICIAL_PRODUCT_DATES.get(title)
        if not patch:
            continue
        stored = (row.get("release_date") or "")[:10]
        if stored != patch["release_date"]:
            issues.append(
                {
                    "title": row.get("canonical_title") or row.get("product_title"),
                    "stored": stored,
                    "expected": patch["release_date"],
                    "source": patch["source_note"],
                }
            )
    return issues


def apply_product_overrides(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        title = (row.get("canonical_title") or row.get("product_title") or "").strip().lower()
        patch = OFFICIAL_PRODUCT_DATES.get(title)
        if not patch:
            out.append(row)
            continue
        updated = dict(row)
        updated["release_date"] = patch["release_date"]
        updated["date_precision"] = patch["date_precision"]
        updated["confirmation"] = patch["confirmation"]
        updated["status"] = patch["confirmation"]
        updated["official_source"] = patch["source_note"]
        if "announced_release" in updated:
            updated["announced_release"] = patch["release_date"]
        out.append(updated)
    return out


def apply_event_overrides(rows: list[dict]) -> list[dict]:
    """Force confirmed organizer dates; drop duplicate wrong-year windows for the same event."""
    kept: list[dict] = []
    seen_official: set[tuple[str, int]] = set()
    for row in rows:
        name = (row.get("event") or row.get("ip_adaptation") or "").strip().lower()
        year_map = OFFICIAL_EVENT_DATES.get(name)
        if not year_map:
            kept.append(row)
            continue
        start = (row.get("start_date") or "")[:10]
        try:
            year = int(start[:4])
        except ValueError:
            kept.append(row)
            continue
        patch = year_map.get(year)
        if not patch:
            kept.append(row)
            continue
        key = (name, year)
        if key in seen_official:
            # Drop stale duplicates (e.g. TGA 2026 scraped as September).
            continue
        seen_official.add(key)
        updated = dict(row)
        updated["start_date"] = patch["start_date"]
        updated["end_date"] = patch["end_date"]
        updated["confirmation"] = patch["confirmation"]
        updated["status"] = patch["status"]
        updated["official_source"] = patch["source_note"]
        updated["date_precision"] = "day"
        kept.append(updated)
    return kept
