"""Announced-but-unreleased titles and event correlation helpers.

Rows without a firm day use a year/quarter planning window and must stay
labeled as announced / TBA rather than confirmed release dates.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.calendar_dedupe import is_quarter_timeframe
from src.dates import annotate_product, label_for, window_for
from src.match import GENERIC_RELATED, franchise_keys_for_text, franchise_queries


# High-value announced titles that may be missing from Wikipedia tables when
# only a year or TBA window is public.
CURATED_ANNOUNCED = [
    {
        "canonical_title": "Grand Theft Auto VI",
        "release_date": "2026-11-19",
        "date_precision": "day",
        "platforms": "PlayStation 5, Xbox Series X/S",
        "developer": "Rockstar Games",
        "publisher": "Rockstar Games",
        "genre": "Action-adventure",
        "confirmation": "confirmed",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Grand_Theft_Auto_VI",
        "franchise": "Grand Theft Auto",
    },
    {
        "canonical_title": "The Witcher 4",
        "release_date": "2027-12-31",
        "platforms": "Multi",
        "developer": "CD Projekt Red",
        "publisher": "CD Projekt",
        "genre": "Action RPG",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/The_Witcher_4",
        "franchise": "The Witcher",
    },
    {
        "canonical_title": "Metroid Prime 4: Beyond",
        "release_date": "2025-12-04",
        "date_precision": "day",
        "platforms": "Nintendo Switch, Nintendo Switch 2",
        "developer": "Retro Studios",
        "publisher": "Nintendo",
        "genre": "Action-adventure",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Metroid_Prime_4:_Beyond",
        "franchise": "Metroid",
    },
    {
        "canonical_title": "Death Stranding 2: On the Beach",
        "release_date": "2025-06-26",
        "date_precision": "day",
        "platforms": "PlayStation 5, PC",
        "developer": "Kojima Productions",
        "publisher": "Sony Interactive Entertainment",
        "genre": "Action",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Death_Stranding_2:_On_the_Beach",
        "franchise": "Death Stranding",
    },
    {
        "canonical_title": "Resident Evil Requiem",
        "release_date": "2026-02-27",
        "date_precision": "day",
        "platforms": "PlayStation 5, Xbox Series X/S, PC, Nintendo Switch 2",
        "developer": "Capcom",
        "publisher": "Capcom",
        "genre": "Survival horror",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Resident_Evil_Requiem",
        "franchise": "Resident Evil",
    },
    {
        "canonical_title": "Mafia: The Old Country",
        "release_date": "2025-08-08",
        "date_precision": "day",
        "platforms": "PlayStation 5, Xbox Series X/S, PC",
        "developer": "Hangar 13",
        "publisher": "2K",
        "genre": "Action-adventure",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Mafia:_The_Old_Country",
        "franchise": "Mafia",
    },
    {
        "canonical_title": "007 First Light",
        "release_date": "2026-05-27",
        "date_precision": "day",
        "platforms": "Multi",
        "developer": "IO Interactive",
        "publisher": "IO Interactive",
        "genre": "Action-adventure",
        "confirmation": "confirmed",
        "wikipedia_url": "https://en.wikipedia.org/wiki/007_First_Light",
        "franchise": "James Bond",
    },
    {
        "canonical_title": "Fable",
        "release_date": "2027-02-23",
        "date_precision": "day",
        "platforms": "Xbox Series X/S, PC, PlayStation 5",
        "developer": "Playground Games",
        "publisher": "Xbox Game Studios",
        "genre": "Action RPG",
        "confirmation": "confirmed",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Fable_(2027_video_game)",
        "franchise": "Fable",
    },
    {
        "canonical_title": "Perfect Dark",
        "release_date": "2027-12-31",
        "platforms": "Xbox Series X/S, PC",
        "developer": "The Initiative / Crystal Dynamics",
        "publisher": "Xbox Game Studios",
        "genre": "Stealth / shooter",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Perfect_Dark_(upcoming_game)",
        "franchise": "Perfect Dark",
    },
    {
        "canonical_title": "Pragmata",
        "release_date": "2026-12-31",
        "platforms": "PlayStation 5, Xbox Series X/S, PC",
        "developer": "Capcom",
        "publisher": "Capcom",
        "genre": "Action-adventure",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Pragmata",
        "franchise": "Pragmata",
    },
    {
        "canonical_title": "Okami 2",
        "release_date": "2028-12-31",
        "platforms": "Multi",
        "developer": "Clovers",
        "publisher": "Capcom",
        "genre": "Action-adventure",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/%C5%8Ckami_2",
        "franchise": "Okami",
    },
    {
        "canonical_title": "Hollow Knight: Silksong",
        "release_date": "2025-09-04",
        "date_precision": "day",
        "platforms": "Multi",
        "developer": "Team Cherry",
        "publisher": "Team Cherry",
        "genre": "Metroidvania",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Hollow_Knight:_Silksong",
        "franchise": "Hollow Knight",
    },
    {
        "canonical_title": "Chronicles of Darkness",
        "release_date": "2027-12-31",
        "platforms": "Multi",
        "developer": "TBA",
        "publisher": "Paradox Interactive",
        "genre": "RPG",
        "confirmation": "announced TBA",
        "wikipedia_url": "",
        "franchise": "World of Darkness",
    },
    {
        "canonical_title": "BioShock 4",
        "release_date": "2029-12-31",
        "platforms": "Multi",
        "developer": "Cloud Chamber",
        "publisher": "2K",
        "genre": "Immersive sim",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/BioShock",
        "franchise": "BioShock",
    },
    {
        "canonical_title": "The Elder Scrolls VI",
        "release_date": "2030-12-31",
        "platforms": "Multi",
        "developer": "Bethesda Game Studios",
        "publisher": "Bethesda Softworks",
        "genre": "Action RPG",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/The_Elder_Scrolls_VI",
        "franchise": "The Elder Scrolls",
    },
    {
        "canonical_title": "Marvel's Wolverine",
        "release_date": "2026-09-15",
        "date_precision": "day",
        "platforms": "PlayStation 5",
        "developer": "Insomniac Games",
        "publisher": "Sony Interactive Entertainment",
        "genre": "Action-adventure",
        "confirmation": "confirmed",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Marvel%27s_Wolverine",
        "franchise": "Marvel / Wolverine",
    },
    {
        "canonical_title": "Ghost of Yōtei",
        "release_date": "2025-10-02",
        "date_precision": "day",
        "platforms": "PlayStation 5",
        "developer": "Sucker Punch Productions",
        "publisher": "Sony Interactive Entertainment",
        "genre": "Action-adventure",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Ghost_of_Y%C5%8Dtei",
        "franchise": "Ghost of Tsushima",
    },
    {
        "canonical_title": "Monster Hunter Wilds",
        "release_date": "2025-02-28",
        "date_precision": "day",
        "platforms": "PlayStation 5, Xbox Series X/S, PC",
        "developer": "Capcom",
        "publisher": "Capcom",
        "genre": "Action RPG",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Monster_Hunter_Wilds",
        "franchise": "Monster Hunter",
    },
    {
        "canonical_title": "EA Sports FC 27",
        "release_date": "2026-09-25",
        "platforms": "Multi",
        "developer": "EA Sports",
        "publisher": "Electronic Arts",
        "genre": "Sports",
        "confirmation": "announced cycle",
        "wikipedia_url": "https://en.wikipedia.org/wiki/EA_Sports_FC",
        "franchise": "EA Sports FC",
    },
    {
        "canonical_title": "Madden NFL 27",
        "release_date": "2026-08-14",
        "platforms": "Multi",
        "developer": "EA Tiburon",
        "publisher": "Electronic Arts",
        "genre": "Sports",
        "confirmation": "announced cycle",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Madden_NFL",
        "franchise": "Madden NFL",
    },
    {
        "canonical_title": "NBA 2K27",
        "release_date": "2026-09-04",
        "platforms": "Multi",
        "developer": "Visual Concepts",
        "publisher": "2K",
        "genre": "Sports",
        "confirmation": "announced cycle",
        "wikipedia_url": "https://en.wikipedia.org/wiki/NBA_2K",
        "franchise": "NBA 2K",
    },
    {
        "canonical_title": "Doom: The Dark Ages",
        "release_date": "2025-05-15",
        "date_precision": "day",
        "platforms": "Multi",
        "developer": "id Software",
        "publisher": "Bethesda Softworks",
        "genre": "FPS",
        "confirmation": "released / catalog",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Doom:_The_Dark_Ages",
        "franchise": "Doom",
    },
    {
        "canonical_title": "Assassin's Creed Codename Hexe",
        "release_date": "2027-12-31",
        "platforms": "Multi",
        "developer": "Ubisoft",
        "publisher": "Ubisoft",
        "genre": "Action-adventure",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Assassin%27s_Creed",
        "franchise": "Assassin's Creed",
    },
    {
        "canonical_title": "OD",
        "release_date": "2026-12-31",
        "platforms": "Xbox Series X/S, PC",
        "developer": "Kojima Productions",
        "publisher": "Xbox Game Studios",
        "genre": "Horror",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/OD_(video_game)",
        "franchise": "OD",
    },
    {
        "canonical_title": "Intergalactic: The Heretic Prophet",
        "release_date": "2028-12-31",
        "platforms": "PlayStation 5",
        "developer": "Naughty Dog",
        "publisher": "Sony Interactive Entertainment",
        "genre": "Action-adventure",
        "confirmation": "announced TBA",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Intergalactic:_The_Heretic_Prophet",
        "franchise": "Intergalactic",
    },
]


def curated_announced_games(*, today: str | None = None) -> list[dict]:
    stamp = today or date.today().isoformat()
    rows: list[dict] = []
    for item in CURATED_ANNOUNCED:
        release = item["release_date"]
        platform = (item.get("platforms") or "Multi").split(",")[0].strip() or "Multi"
        dated = annotate_product(item)
        rows.append(
            {
                "date_precision": dated["date_precision"],
                "release_start": dated["release_start"],
                "release_end": dated["release_end"],
                "release_label": dated["release_label"],
                "product_id": f"announced:{item['canonical_title'].lower().replace(' ', '-')[:48]}",
                "product_sku": "",
                "canonical_title": item["canonical_title"],
                "product_title": item["canonical_title"],
                "product_type": "announced",
                "platform": platform,
                "platforms": item.get("platforms") or platform,
                "status": item["confirmation"],
                "release_date": release,
                "slug": item["canonical_title"].lower().replace(" ", "-"),
                "genre": item.get("genre") or "",
                "developer": item.get("developer") or "",
                "publisher": item.get("publisher") or "",
                "wikipedia_url": item.get("wikipedia_url") or "",
                "confirmation": item["confirmation"],
                "source": "announced_registry",
                "franchise": item.get("franchise") or item["canonical_title"],
                "last_checked": stamp,
                "announced_release": release,
            }
        )
    return rows


def release_window_events(announced: list[dict]) -> list[dict]:
    """Turn announced product dates into merchandising windows on the event calendar.

    The window mirrors how precise the announcement is: an exact date gets a
    launch fortnight, a month/quarter/year announcement covers that period so a
    date-range search lands on the real timing instead of a 31 December stub.
    """
    rows: list[dict] = []
    for game in announced:
        title = (game.get("canonical_title") or "").strip()
        release = (game.get("release_date") or "").strip()
        if not title or len(release) < 10 or is_quarter_timeframe(title):
            continue
        try:
            day = date.fromisoformat(release[:10])
        except ValueError:
            continue
        precision = game.get("date_precision") or ""
        window_start, window_end = window_for(release, precision or None)
        if window_start is None or window_end is None:
            continue
        precision = precision or ("day" if window_start == window_end else "month")
        exact = precision == "day"
        if exact:
            start = day
            end = day + timedelta(days=14)
        else:
            start = window_start
            end = window_end
        tba = precision in ("quarter", "year")
        rows.append(
            {
                "kind": "event",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "date_precision": precision,
                "runtime_start": window_start.isoformat(),
                "runtime_end": window_end.isoformat(),
                "date_label": label_for(release, precision),
                "event": f"{title} release window",
                "category": "Announced Product",
                "related_game": title,
                "event_type": "Product Release",
                "status": "Announced planning window" if tba else "Announced release window",
                "wikipedia_url": game.get("wikipedia_url") or "",
                "source": "announced_product_window",
                "confirmation": game.get("confirmation") or "announced",
                "summary": (
                    f"Merchandising window for announced title {title}"
                    + (
                        f" across {label_for(release, precision)} (no exact day announced)."
                        if tba
                        else f" around {label_for(release, precision)}."
                    )
                ),
                "attendance_mode": "digital",
                "scope": "global",
                "location": "Online / retail",
                "organizer": game.get("publisher") or game.get("developer") or "",
                "cadence": "one-off",
                "correlated_announced": title,
            }
        )
    return rows


def _is_generic(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return not text or text in GENERIC_RELATED


def correlate_events_with_announced(events: list[dict], announced: list[dict]) -> list[dict]:
    """Attach announced titles to overlapping or franchise-matching event rows."""
    by_franchise: dict[str, list[dict]] = {}
    dated: list[tuple[date, dict]] = []
    for game in announced:
        title = game.get("canonical_title") or ""
        for key in franchise_keys_for_text(title) | franchise_keys_for_text(game.get("franchise")):
            by_franchise.setdefault(key, []).append(game)
        for query in franchise_queries(title)[:2]:
            by_franchise.setdefault(query, []).append(game)
        release = game.get("release_date") or ""
        if len(release) >= 10:
            try:
                dated.append((date.fromisoformat(release[:10]), game))
            except ValueError:
                pass

    enriched: list[dict] = []
    for row in events:
        out = dict(row)
        related = out.get("related_game") or ""
        keys = franchise_keys_for_text(related) | franchise_keys_for_text(out.get("event"))
        hits: list[dict] = []
        seen: set[str] = set()
        for key in keys:
            for game in by_franchise.get(key, []):
                title = game.get("canonical_title") or ""
                if title and title.lower() not in seen:
                    seen.add(title.lower())
                    hits.append(game)
        # Do not cross-pollinate one announced product's release window with
        # every other title launching in the same month.
        if out.get("source") != "announced_product_window":
            start = out.get("start_date") or ""
            end = out.get("end_date") or start
            if len(start) >= 10 and len(end) >= 10:
                try:
                    window_start = date.fromisoformat(start[:10]) - timedelta(days=45)
                    window_end = date.fromisoformat(end[:10]) + timedelta(days=45)
                except ValueError:
                    window_start = window_end = None
                if window_start and window_end:
                    event_type = f"{out.get('event_type') or ''} {out.get('category') or ''}".lower()
                    if any(
                        token in event_type
                        for token in (
                            "expo",
                            "showcase",
                            "festival",
                            "awards",
                            "commerce",
                            "sale",
                            "direct",
                            "conference",
                        )
                    ):
                        for release, game in dated:
                            if window_start <= release <= window_end:
                                title = game.get("canonical_title") or ""
                                if title and title.lower() not in seen:
                                    seen.add(title.lower())
                                    hits.append(game)
        if hits:
            names = [game["canonical_title"] for game in hits[:8]]
            out["correlated_announced"] = ", ".join(names)
            if _is_generic(related):
                out["related_game"] = ", ".join(names[:4])
            elif names[0].lower() not in related.lower():
                out["related_game"] = f"{related}, {names[0]}"
            summary = out.get("summary") or ""
            note = f"Correlated announced titles: {', '.join(names[:4])}."
            if note not in summary:
                out["summary"] = f"{summary} {note}".strip()
        enriched.append(out)
    return enriched
