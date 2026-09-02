"""Timed marketing and promotion strategies for catalog products during equivalent events.

Example: EA Sports FC SKUs are promoted through the FIFA Women's World Cup window
(lead-in, live tournament, afterglow) — not as a generic always-on listing.
"""

from __future__ import annotations

import csv
import gzip
import re
from datetime import date, timedelta

from src.calendar_dedupe import is_gaming_world_event, is_quarter_timeframe
from src.dates import confirmation_kind
from src.documents import keyword_retrieve
from src.first_party import (
    is_owned_product,
    owned_search_queries,
    showcase_owner,
)
from src.load_data import gzip_sidecar, parse_date
from src.match import (
    build_title_index,
    catalog_around_window,
    franchise_keys_for_text,
    queries_for_calendar_row,
    rank_catalog,
    superhero_universe_for_row,
)
from src.paths import DATA_PROCESSED

CURRENCY_MARKERS = (
    "points",
    " fc points",
    " vc",
    "coins",
    "credits",
    "madden points",
    "the show packs",
)
LEAD_IN_DAYS = {
    "sports": 14,
    "esports": 10,
    "adaptation": 21,
    "awards": 10,
    "commerce": 3,
    "expo": 7,
    "default": 7,
}
AFTERGLOW_DAYS = {
    "sports": 7,
    "esports": 5,
    "adaptation": 14,
    "awards": 7,
    "commerce": 0,
    "expo": 3,
    "default": 3,
}


def promo_family(row: dict) -> str:
    if row.get("kind") == "adaptation":
        return "adaptation"
    event_type = (row.get("event_type") or "").lower()
    category = (row.get("category") or "").lower()
    name = (row.get("event") or "").lower()
    sports_types = {
        "golf",
        "basketball",
        "ice hockey",
        "tennis",
        "football",
        "cycling",
        "motorsport",
        "american football",
        "baseball",
    }
    if event_type in sports_types or category == "sports":
        return "sports"
    if "esports" in event_type or "esports" in category or event_type == "fighting games":
        return "esports"
    if "award" in event_type:
        return "awards"
    if "commerce" in event_type or "sale" in name:
        return "commerce"
    if any(token in event_type for token in ("expo", "showcase", "convention", "festival", "direct", "conference")):
        return "expo"
    return "default"


def calendar_label(row: dict) -> str:
    return (row.get("event") or row.get("ip_adaptation") or "").strip()


def product_role(row: dict) -> str:
    title = f"{row.get('canonical_title', '')} {row.get('product_title', '')}".lower()
    product_type = (row.get("product_type") or "").lower()
    if any(marker in title for marker in CURRENCY_MARKERS):
        return "currency"
    if product_type == "dlc" or title.rstrip().endswith("dlc") or " pack" in title:
        return "dlc"
    if product_type == "announced":
        return "game"
    return "game"


def edition_year(title: str | None, release_date: str | None = None) -> int:
    """Best-effort season/year so FC 26 outranks FIFA 15."""
    text = title or ""
    years = [int(match) for match in re.findall(r"\b(20[0-3]\d)\b", text)]
    if years:
        parsed = max(years)
    else:
        match = re.search(r"\b2k(\d{2})\b", text, re.I)
        if match:
            parsed = 2000 + int(match.group(1))
        else:
            match = re.search(
                r"\b(?:fc|fifa|nhl|ufc|madden nfl)\s*(\d{2})\b",
                text,
                re.I,
            )
            parsed = 0
            if match:
                value = int(match.group(1))
                if value >= 10:
                    parsed = 2000 + value
    if parsed:
        return parsed
    if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
        year = int(release_date[:4])
        if 1990 <= year <= 2035:
            return year
    return 0


def base_edition_title(title: str | None) -> str:
    text = title or ""
    text = re.sub(
        r"\s+(- )?(ultimate|deluxe|gold|complete|cross-gen|standard|legacy|definitive|pre-order.*|edition).*$",
        "",
        text,
        flags=re.I,
    )
    return text.strip() or (title or "")


def promotion_phases(row: dict) -> list[dict]:
    start = _parsed_start(row)
    end = _parsed_end(row) or start
    if start is None:
        return []
    family = promo_family(row)
    lead = LEAD_IN_DAYS[family]
    after = AFTERGLOW_DAYS[family]
    lead_start = start - timedelta(days=lead)
    live_end = end
    after_end = live_end + timedelta(days=after)
    phases = [
        {
            "name": "lead_in",
            "start": lead_start,
            "end": start - timedelta(days=1) if lead else start,
            "label": "Lead-in",
        },
        {
            "name": "live",
            "start": start,
            "end": live_end,
            "label": "Event runtime",
        },
    ]
    if after:
        phases.append(
            {
                "name": "afterglow",
                "start": live_end + timedelta(days=1),
                "end": after_end,
                "label": "Afterglow",
            }
        )
    return [phase for phase in phases if phase["end"] >= phase["start"]]


def _tactics(family: str, phase: str, role: str, event_type: str, *, event_name: str = "") -> list[str]:
    sport = (event_type or family).lower()
    if family == "sports":
        live_watch = (
            f"Watch-along merchandising: feature the current {sport} title next to live-score / tournament content"
        )
        if phase == "lead_in":
            if role == "game":
                return [
                    f"Pin the latest {sport} edition as the category hero 2 weeks before kickoff",
                    "Tease roster/kit/tournament modes that map to the real-world competition",
                    "Seed creators with 'play the tournament at home' loadouts; do not deep-discount the current SKU",
                ]
            if role == "currency":
                return [
                    "Soft-launch points/FUT/VC packs as an attach, not as the homepage hero",
                    "Bundle a small currency pack with the latest full game for pre-event shoppers",
                ]
            return [
                "List the latest content pack under the current full-game hero — not as its own campaign",
            ]
        if phase == "live":
            if role == "game":
                return [
                    live_watch,
                    "Daily storefront slot + push/email on match days in televised regions",
                    "Highlight co-op, Ultimate Team, or tournament brackets that mirror the live event",
                ]
            if role == "currency":
                return [
                    "Spike points-pack visibility on match days; keep the full game undiscounted",
                    "Time limited packs to kickoff / final-whistle windows in core geos",
                ]
            return [
                "Keep DLC nested under the live hero SKU on match-day merchandising",
            ]
        if role == "game":
            return [
                "Recap creative: 'play the final again' / career-mode restart for 7 days after the last match",
                "Convert event traffic with a short featured-listing holdover, then rotate off",
            ]
        if role == "currency":
            return [
                "One last attach offer, then drop points packs back to baseline merchandising",
            ]
        return [
            "Drop the content-pack attach when the afterglow window closes",
        ]
    if family == "esports":
        if phase == "lead_in":
            return [
                "Run pick'em / spectator-mode tutorials and feature the competitive title on the esports shelf",
                "Seed team or champion-skin DLC if the SKU has a cosmetics attach",
            ]
        if phase == "live":
            return [
                "Homepage takeover on series days; pair the game with watch-to-play / drop campaigns",
                "Geo-boost regions hosting or broadcasting the championship",
            ]
        return [
            "Winner-skin or 'play like the champions' recap for 5 days, then revert",
        ]
    if family == "adaptation":
        universe = superhero_universe_for_row(event_name)
        if universe == "marvel":
            if phase == "lead_in":
                return [
                    "Build a Marvel catalog rail 3 weeks out: Insomniac Spider-Man, Wolverine, Midnight Suns, Vs. Capcom, LEGO Avengers, and announced Marvel titles",
                    "SEO the film + 'Marvel games' / 'play Marvel before [film]' / character+MCU keywords",
                ]
            if phase == "live":
                return [
                    "Feature every Marvel SKU in the database for the theatrical window, not only the lead character",
                    "Pair upcoming Marvel releases (wishlist / pre-order) next to back-catalog heroes",
                ]
            return [
                "Hold the Marvel rail through afterglow; keep announced titles (Wolverine and later) on pre-order",
            ]
        if universe == "dc":
            if phase == "lead_in":
                return [
                    "Build a DC catalog rail: Arkham, Injustice, Gotham Knights, Suicide Squad, LEGO Batman, and Superman-related SKUs",
                    "SEO the film + 'DC games' / 'play DC before [film]' / Batman-Superman keywords",
                ]
            if phase == "live":
                return [
                    "Feature every DC SKU in the database for the theatrical window, not only the lead character",
                    "Cross-link Arkham / Injustice back-catalog with any announced DC titles",
                ]
            return [
                "Hold the DC rail through afterglow; rotate to evergreen superhero similar-IP after two weeks",
            ]
        if phase == "lead_in":
            return [
                "Play-before-you-watch campaign starting 3 weeks out; trailer + storefront bundle",
                "Sync creative with the studio/streamer's launch assets",
            ]
        if phase == "live":
            return [
                "Hold a featured placement for the theatrical/streaming window",
                "Cross-sell the game next to any soundtrack or tie-in DLC",
            ]
        return [
            "Two-week holdover for late streamers; then move to evergreen similar-IP rails",
        ]
    if family == "awards":
        return [
            "Build a 'play the nominees / winners' merchandising rail around the ceremony date",
            "Boost SKUs that match announced categories; rotate the moment winners drop",
        ]
    if family == "commerce":
        return [
            "Put equivalent titles on the sale rail for the commerce window only",
            "Lead with a genuine discount on back-catalog; protect current-gen pricing unless the sale requires it",
        ]
    if phase == "lead_in":
        return [
            "Wishlist / pre-order push for equivalent IPs likely to appear at the show",
            "Brief community and retail partners 7 days out",
        ]
    if phase == "live":
        return [
            "Amplify announcements the same day; feature matching catalog SKUs within hours of a trailer",
        ]
    return [
        "Convert announcement traffic with a 3-day featured hold and pre-order follow-up",
    ]


def _offer(family: str, role: str) -> str:
    if role == "currency":
        return "Attach offer (points/packs); do not replace the full-game hero"
    if role == "dlc":
        return "Content attach under the latest full game"
    if family == "sports":
        return "Featured listing + event creative; hold current-edition price, discount only the prior year"
    if family == "commerce":
        return "Timed sale price during the commerce window"
    if family == "adaptation":
        return "Tie-in featured placement; optional bundle with soundtrack/DLC"
    return "Featured merchandising during the event window"


def _parsed_start(row: dict) -> date | None:
    parsed = row.get("start_date_parsed")
    if isinstance(parsed, date):
        return parsed
    return parse_date(row.get("start_date") or row.get("runtime_start") or "")


def _parsed_end(row: dict) -> date | None:
    parsed = row.get("end_date_parsed")
    if isinstance(parsed, date):
        return parsed
    return parse_date(row.get("end_date") or row.get("runtime_end") or "") or _parsed_start(row)


def _is_junk_title(title: str) -> bool:
    return bool(
        re.search(
            r"playgrounds|mobile|arcade|random 1 key|try to get|\bbundle\b|kickoff|"
            r"^\d[\d.]*\s+.+\bsequel\b",
            title or "",
            re.I,
        )
    )


def event_bucket(row: dict) -> str:
    """Merchandising bucket used when a row has no tight franchise match."""
    name = calendar_label(row).lower()
    event_type = (row.get("event_type") or "").lower()
    category = (row.get("category") or "").lower()
    if row.get("kind") == "adaptation" or row.get("ip_adaptation"):
        return "adaptation"
    if "steam" in name:
        return "steam"
    if "nintendo" in name:
        return "nintendo"
    if "xbox" in name:
        return "xbox"
    if "playstation" in name or "state of play" in name:
        return "playstation"
    if promo_family(row) == "sports":
        return "sports"
    if "esports" in event_type or "esports" in category:
        return "esports"
    if "award" in event_type or "award" in name:
        return "awards"
    if any(token in name for token in ("anime", "jump festa", "comic-con", "comic con")):
        return "anime"
    return "expo"


def product_bucket(product: dict) -> str:
    platform = f"{product.get('platform') or ''} {product.get('platform_id') or ''}".lower()
    title = product.get("canonical_title") or product.get("product_title") or ""
    keys = franchise_keys_for_text(title)
    if keys & {"mario", "zelda", "pokemon", "metroid"} or any(
        token in platform for token in ("nintendo", "switch")
    ):
        return "nintendo"
    if "xbox" in platform:
        return "xbox"
    if any(token in platform for token in ("playstation", "psn", "ps5", "ps4", "ps3", "ps vita")):
        return "playstation"
    if any(token in platform for token in ("steam", "pc")):
        return "steam"
    return "expo"


def _unique_catalog(catalog: list[dict]) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for row in catalog:
        title = (row.get("canonical_title") or row.get("product_title") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def _event_keys(row: dict) -> set[str]:
    return (
        franchise_keys_for_text(row.get("related_game"))
        | franchise_keys_for_text(row.get("event") or row.get("ip_adaptation"))
        | franchise_keys_for_text(row.get("correlated_announced"))
    )


def _split_titles(value: str | None) -> list[str]:
    rows = []
    for chunk in re.split(r",|/|;", value or ""):
        name = chunk.strip()
        if len(name) >= 3 and name.lower() not in {
            "multi-platform",
            "multi-game",
            "pc",
            "steam",
            "indie",
            "gaming",
        }:
            rows.append(name)
    return rows


def _catalog_by_title(catalog: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in catalog:
        title = (row.get("canonical_title") or row.get("product_title") or "").strip()
        if title:
            index.setdefault(title.lower(), row)
    return index


def _pick_named_titles(catalog_index: dict[str, dict], names: list[str], *, limit: int = 2) -> list[dict]:
    chosen: list[dict] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        row = catalog_index.get(key)
        if not row:
            continue
        title = (row.get("canonical_title") or "").lower()
        if title in seen:
            continue
        seen.add(title)
        chosen.append(row)
        if len(chosen) >= limit:
            break
    return chosen


def _products_near_window(row: dict, catalog: list[dict], *, limit: int = 2) -> list[dict]:
    nearby = catalog_around_window(catalog, _parsed_start(row), _parsed_end(row), pad_days=21)
    chosen: list[dict] = []
    seen: set[str] = set()
    for item in nearby:
        title = item.get("canonical_title") or item.get("product_title") or ""
        if _is_junk_title(title) or product_role(item) != "game":
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) >= limit:
            break
    return chosen


def _products_in_bucket(
    row: dict,
    pool: list[dict],
    *,
    limit: int = 2,
) -> list[dict]:
    start = _parsed_start(row)
    scored: list[tuple[tuple, dict]] = []
    for item in pool:
        title = item.get("canonical_title") or item.get("product_title") or ""
        if _is_junk_title(title) or product_role(item) != "game":
            continue
        release = item.get("release_date_parsed")
        delta = 9999
        if isinstance(release, date) and start:
            delta = abs((release - start).days)
        announced = 0 if (item.get("product_type") or "").lower() == "announced" else 1
        scored.append(((delta, announced, -(edition_year(title, item.get("release_date"))), title.lower()), item))
    scored.sort(key=lambda item: item[0])
    chosen: list[dict] = []
    seen: set[str] = set()
    for _, item in scored:
        title = (item.get("canonical_title") or "").lower()
        if title in seen:
            continue
        seen.add(title)
        chosen.append(item)
        if len(chosen) >= limit:
            break
    return chosen


def select_owned_games(catalog: list[dict], spec, *, limit: int | None = 10) -> list[dict]:
    """Unique first-party games for a showcase owner, announced and upcoming first."""
    today = date.today().isoformat()
    scored: list[tuple[tuple, dict]] = []
    for item in catalog:
        if not is_owned_product(item, spec):
            continue
        title = item.get("canonical_title") or item.get("product_title") or ""
        if _is_junk_title(title) or product_role(item) != "game":
            continue
        announced = 0 if (item.get("product_type") or "").lower() == "announced" else 1
        release = item.get("release_date") or ""
        future = 0 if release >= today else 1
        scored.append(((announced, future, release, title.lower()), item))
    scored.sort(key=lambda item: item[0][2] or "", reverse=True)
    scored.sort(key=lambda item: (item[0][0], item[0][1], item[0][3]))
    chosen: list[dict] = []
    seen: set[str] = set()
    for _, item in scored:
        key = base_edition_title(item.get("canonical_title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        chosen.append(item)
        if limit and len(chosen) >= limit:
            break
    return chosen


def recommended_games_for_event(
    row: dict,
    catalog: list[dict],
    *,
    limit: int = 10,
    title_index: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Top catalog games to merchandise for this event window."""
    owner = showcase_owner(calendar_label(row))
    if owner:
        owned = select_owned_games(catalog, owner, limit=limit)
        if owned:
            return owned
    picked = products_for_event(row, catalog, title_index=title_index)
    games: list[dict] = []
    seen: set[str] = set()

    def add(item: dict) -> None:
        title = item.get("canonical_title") or item.get("product_title") or ""
        if not title or _is_junk_title(title) or product_role(item) != "game":
            return
        key = base_edition_title(title).lower()
        if not key or key in seen:
            return
        seen.add(key)
        games.append(item)

    for item in picked:
        add(item)
        if len(games) >= limit:
            return games[:limit]
    for item in _products_near_window(row, catalog, limit=limit):
        add(item)
        if len(games) >= limit:
            return games[:limit]
    bucket = event_bucket(row)
    pool = [item for item in catalog if product_bucket(item) == bucket]
    for item in _products_in_bucket(row, pool or catalog, limit=limit):
        add(item)
        if len(games) >= limit:
            return games[:limit]
    extra = [
        item
        for item in catalog
        if product_role(item) == "game" and not _is_junk_title(item.get("canonical_title") or "")
    ]
    extra.sort(key=lambda item: item.get("release_date") or "", reverse=True)
    for item in extra:
        add(item)
        if len(games) >= limit:
            break
    return games[:limit]


def products_for_event(
    row: dict,
    catalog: list[dict],
    *,
    catalog_index: dict[str, dict] | None = None,
    games_by_bucket: dict[str, list[dict]] | None = None,
    title_index: dict[str, list[dict]] | None = None,
    fallback_pool: list[dict] | None = None,
    fallback_cursor: list[int] | None = None,
) -> list[dict]:
    """At least one catalog SKU for this event: franchise, window, then bucket."""
    owner = showcase_owner(calendar_label(row))
    if owner:
        chosen = select_owned_games(catalog, owner, limit=10)
        if chosen:
            return chosen
    queries = queries_for_calendar_row(row)
    label = calendar_label(row).lower()
    rank_queries = [query for query in queries if query != label]
    universe = superhero_universe_for_row(row)
    chosen = _select_products(
        catalog,
        rank_queries or queries,
        title_index=title_index,
        universe=universe,
    ) if rank_queries else []
    if chosen:
        return chosen
    index = catalog_index or _catalog_by_title(catalog)
    named = _split_titles(row.get("correlated_announced")) + _split_titles(row.get("related_game"))
    chosen = _pick_named_titles(index, named, limit=2)
    if chosen:
        return chosen
    chosen = _products_near_window(row, catalog, limit=2)
    if chosen:
        return chosen
    bucket = event_bucket(row)
    if games_by_bucket:
        pool = games_by_bucket.get(bucket) or games_by_bucket.get("expo") or games_by_bucket.get("steam") or catalog
    else:
        pool = [item for item in catalog if product_bucket(item) == bucket or bucket in {"expo", "awards", "esports", "adaptation", "sports", "anime"}]
    chosen = _products_in_bucket(row, pool, limit=2)
    if chosen:
        return chosen
    pool = fallback_pool or [
        item
        for item in _unique_catalog(catalog)
        if product_role(item) == "game" and not _is_junk_title(item.get("canonical_title") or "")
    ]
    if not pool:
        return []
    cursor = fallback_cursor if fallback_cursor is not None else [0]
    item = pool[cursor[0] % len(pool)]
    cursor[0] += 1
    return [item]


def _nearest_event(product: dict, rows: list[dict], *, today: date) -> dict | None:
    if not rows:
        return None
    release = product.get("release_date_parsed")
    if not isinstance(release, date):
        release = parse_date(product.get("release_date") or "") or today
    future: list[tuple[int, dict]] = []
    past: list[tuple[int, dict]] = []
    for row in rows:
        start = _parsed_start(row)
        if start is None:
            continue
        if start >= release:
            future.append(((start - release).days, row))
        else:
            past.append(((release - start).days, row))
    future.sort(key=lambda item: item[0])
    past.sort(key=lambda item: item[0])
    if future:
        return future[0][1]
    if past:
        return past[0][1]
    return rows[0]


def _closest_event(rows: list[dict], around: date | None, *, today: date) -> dict | None:
    """Event whose runtime is nearest to `around` (inside the window counts as 0)."""
    if not rows:
        return None
    anchor = around or today
    scored: list[tuple[int, str, dict]] = []
    for row in rows:
        start = _parsed_start(row)
        end = _parsed_end(row) or start
        if start is None:
            continue
        if end and start <= anchor <= end:
            dist = 0
        elif anchor < start:
            dist = (start - anchor).days
        else:
            dist = (anchor - (end or start)).days
        scored.append((dist, start.isoformat(), row))
    if not scored:
        return rows[0]
    scored.sort(key=lambda item: (item[0], item[1]))
    return scored[0][2]


def best_event_for_product(
    product: dict,
    *,
    events_by_key: dict[str, list[dict]],
    events_by_bucket: dict[str, list[dict]],
    today: date,
) -> dict | None:
    title = product.get("canonical_title") or product.get("product_title") or ""
    keys = franchise_keys_for_text(title)
    candidates: list[dict] = []
    seen: set[int] = set()
    for key in keys:
        for row in events_by_key.get(key) or []:
            marker = id(row)
            if marker in seen:
                continue
            seen.add(marker)
            candidates.append(row)
    if candidates:
        return _nearest_event(product, candidates, today=today)
    bucket_rows = events_by_bucket.get(product_bucket(product)) or events_by_bucket.get("expo") or []
    hit = _nearest_event(product, bucket_rows, today=today)
    if hit:
        return hit
    for bucket in ("expo", "steam", "awards"):
        hit = _nearest_event(product, events_by_bucket.get(bucket) or [], today=today)
        if hit:
            return hit
    dated: list[dict] = []
    seen_ids: set[int] = set()
    for rows in events_by_bucket.values():
        for row in rows:
            marker = id(row)
            if marker in seen_ids:
                continue
            seen_ids.add(marker)
            dated.append(row)
    return _nearest_event(product, dated, today=today)


def _events_touching_bounds(rows: list[dict], start: str, end: str) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if is_quarter_timeframe(row):
            continue
        ev_start = _parsed_start(row)
        ev_end = _parsed_end(row) or ev_start
        if ev_start is None:
            continue
        if ev_start.isoformat() <= end and ev_end.isoformat() >= start:
            out.append(row)
    return out


def _calendar_indexes(rows: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    events_by_key: dict[str, list[dict]] = {}
    events_by_bucket: dict[str, list[dict]] = {}
    for row in rows:
        if is_quarter_timeframe(row) or _parsed_start(row) is None:
            continue
        for key in _event_keys(row):
            events_by_key.setdefault(key, []).append(row)
        events_by_bucket.setdefault(event_bucket(row), []).append(row)
    return events_by_key, events_by_bucket


def _merch_fallback_events(rows: list[dict], product: dict) -> list[dict]:
    """Expos and platform showcases that are not some other franchise's IP."""
    product_keys = franchise_keys_for_text(product.get("canonical_title") or "")
    bucket = product_bucket(product)
    out: list[dict] = []
    for row in rows:
        if not is_gaming_world_event(row):
            continue
        name = calendar_label(row).lower()
        event_type = (row.get("event_type") or "").lower()
        if "release window" in name or event_type in {"announcement", "tba", "product release"}:
            continue
        row_keys = _event_keys(row)
        if row_keys and not (row_keys & product_keys):
            continue
        ev_bucket = event_bucket(row)
        if ev_bucket in {"nintendo", "xbox", "playstation", "anime", "sports", "adaptation"} and ev_bucket != bucket:
            continue
        out.append(row)
    return out


def correlation_indexes(calendar: list[dict], start: str, end: str) -> tuple[list[dict], dict[str, list[dict]]]:
    """Dated events in [start, end] plus franchise-key lookup for reuse."""
    subset = _events_touching_bounds(calendar, start, end)
    return subset, _calendar_indexes(subset)[0]


def correlate_calendar_event(
    title: str,
    calendar: list[dict],
    *,
    around: str | None = None,
    year: str | None = None,
    span: bool = False,
    start_year: str = "2022",
    end_year: str = "2026",
    platform: str = "",
    subset: list[dict] | None = None,
    events_by_key: dict[str, list[dict]] | None = None,
) -> dict | None:
    """Named calendar event for a product: franchise first, then platform/expo.

    `year` keeps the match inside that calendar year (YoY). `span` keeps it
    inside 2022–2026. Otherwise any dated event is eligible.
    """
    if subset is None:
        if year:
            subset = _events_touching_bounds(calendar, f"{year}-01-01", f"{year}-12-31")
        elif span:
            subset = _events_touching_bounds(calendar, f"{start_year}-01-01", f"{end_year}-12-31")
            if not subset:
                subset = [row for row in calendar if not is_quarter_timeframe(row) and _parsed_start(row)]
        else:
            subset = [row for row in calendar if not is_quarter_timeframe(row) and _parsed_start(row)]
    if not subset:
        return None
    anchor = (around or "").strip()[:10]
    if year and (not anchor or not anchor.startswith(str(year))):
        anchor = f"{year}-06-15"
    product = {
        "canonical_title": title,
        "product_title": title,
        "release_date": anchor,
        "release_date_parsed": parse_date(anchor) if anchor else None,
        "platform": platform,
    }
    if events_by_key is None:
        events_by_key = _calendar_indexes(subset)[0]
    today = date.today()
    parsed_around = parse_date(anchor) if anchor else today
    keys = franchise_keys_for_text(title)
    candidates: list[dict] = []
    seen: set[int] = set()
    for key in keys:
        for row in events_by_key.get(key) or []:
            marker = id(row)
            if marker in seen:
                continue
            seen.add(marker)
            candidates.append(row)
    if candidates:
        return _closest_event(candidates, parsed_around, today=today)
    merch = _merch_fallback_events(subset, product)
    if merch:
        return _closest_event(merch, parsed_around, today=today)
    world = [row for row in subset if is_gaming_world_event(row)]
    return _closest_event(world or subset, parsed_around, today=today)


def make_promotion_plan(row: dict, product: dict) -> dict | None:
    return _make_plan(row, product, queries=queries_for_calendar_row(row))


def _select_products(
    catalog: list[dict],
    queries: list[str],
    *,
    title_index: dict[str, list[dict]] | None = None,
    universe: str | None = None,
    game_limit: int | None = None,
    max_total: int | None = None,
) -> list[dict]:
    ranked = rank_catalog(catalog, queries, min_score=1, title_index=title_index)
    preferred = queries[0] if queries else ""
    scored: list[tuple[tuple, dict]] = []
    for score, row in ranked:
        role = product_role(row)
        if role == "game" and score < 2:
            continue
        title = row.get("canonical_title") or row.get("product_title") or ""
        year = edition_year(title, row.get("release_date"))
        preferred_hit = 0 if preferred and preferred in title.lower() else 1
        announced_boost = 0
        if (row.get("product_type") or "").lower() == "announced":
            announced_boost = -1
        release = row.get("release_date") or ""
        future_boost = -1 if release >= date.today().isoformat() else 0
        scored.append(
            (
                (-score, preferred_hit, announced_boost, future_boost, -year, role != "game", len(title)),
                row,
            )
        )
    scored.sort(key=lambda item: item[0])

    chosen: list[dict] = []
    counts = {"game": 0, "currency": 0, "dlc": 0}
    if universe:
        limits = {"game": 40, "currency": 4, "dlc": 8}
        cap = 48
    else:
        limits = {"game": game_limit or 2, "currency": 1, "dlc": 1}
        cap = max_total or 4
    seen_titles: set[str] = set()
    seen_game_years: set[int] = set()
    for _, row in scored:
        role = product_role(row)
        title = row.get("canonical_title") or row["product_title"]
        if role == "game" and re.search(r"playgrounds|mobile|arcade|random 1 key|try to get", title, re.I):
            continue
        base = base_edition_title(title).lower()
        year = edition_year(title, row.get("release_date"))
        key = f"{role}:{base}:{year}"
        if key in seen_titles:
            continue
        if not universe:
            if role == "game" and year in seen_game_years:
                continue
            if role == "game" and seen_game_years:
                latest = max(seen_game_years)
                if not year or year < latest - 2:
                    continue
        if counts[role] >= limits[role]:
            continue
        seen_titles.add(key)
        if role == "game":
            seen_game_years.add(year)
        counts[role] += 1
        chosen.append(row)
        if sum(counts.values()) >= cap:
            break
    return chosen


def select_hero_products(catalog: list[dict], queries: list[str]) -> list[dict]:
    """Public wrapper used by daily trend matching."""
    return _select_products(catalog, queries)


def has_actionable_window(row: dict) -> bool:
    """Skip year-long TBA placeholders; keep real runtimes and confirmed dates."""
    start = _parsed_start(row)
    end = _parsed_end(row) or start
    if start is None:
        return False
    span = (end - start).days
    status = f"{row.get('status', '')} {row.get('date_status', '')}".lower()
    confirmed = any(token in status for token in ("confirm", "announce", "known cycle"))
    if span > 120 and not confirmed:
        return False
    return True


def _strategy_summary(row: dict, product: dict, family: str) -> str:
    label = calendar_label(row)
    title = product.get("canonical_title") or product.get("product_title")
    start = row.get("start_date")
    end = row.get("end_date")
    related = row.get("related_game") or title
    universe = superhero_universe_for_row(row)
    if universe == "marvel":
        return (
            f"Promote {title} with the full Marvel catalog during {label} "
            f"({related}) — existing and upcoming Marvel games, not only the film's lead character. "
            f"Runtime {start} to {end} with a play-before-you-watch lead-in."
        )
    if universe == "dc":
        return (
            f"Promote {title} with the full DC catalog during {label} "
            f"({related}) — Arkham, Injustice, and other DC games in the database. "
            f"Runtime {start} to {end} with a play-before-you-watch lead-in."
        )
    return (
        f"Promote {title} as the storefront equivalent of {label} "
        f"({related}) for the full event runtime {start} to {end}, "
        f"with a {family} lead-in and afterglow around those dates."
    )


def _make_plan(row: dict, product: dict, *, queries: list[str]) -> dict | None:
    phases = promotion_phases(row)
    if not phases:
        start = _parsed_start(row)
        end = _parsed_end(row) or start
        if start is None:
            return None
        phases = [{"name": "live", "start": start, "end": end, "label": "Event runtime"}]
    family = promo_family(row)
    event_type = row.get("event_type") or row.get("medium") or family
    role = product_role(product)
    phase_payload = [
        {
            "name": phase["name"],
            "label": phase["label"],
            "start": phase["start"].isoformat(),
            "end": phase["end"].isoformat(),
            "tactics": _tactics(family, phase["name"], role, event_type, event_name=calendar_label(row)),
        }
        for phase in phases
    ]
    return {
        "event": calendar_label(row),
        "event_kind": row.get("kind") or "event",
        "event_type": event_type,
        "category": row.get("category") or row.get("medium") or "",
        "related_game": row.get("related_game") or "",
        "event_start": row.get("start_date") or "",
        "event_end": row.get("end_date") or "",
        "runtime_start": row.get("runtime_start") or row.get("start_date") or "",
        "runtime_end": row.get("runtime_end") or row.get("end_date") or row.get("start_date") or "",
        "date_precision": row.get("date_precision") or "",
        "date_label": row.get("date_label") or "",
        "exact_date": (row.get("date_precision") or "day") == "day",
        "confirmation": confirmation_kind(row),
        "official_source": row.get("official_source") or "",
        "promo_family": family,
        "promo_start": phases[0]["start"].isoformat(),
        "promo_end": phases[-1]["end"].isoformat(),
        "product_id": product.get("product_id") or "",
        "product_sku": product.get("product_sku") or "",
        "canonical_title": product.get("canonical_title") or "",
        "product_title": product.get("product_title") or "",
        "platform": product.get("platform") or "",
        "product_type": product.get("product_type") or "",
        "role": role,
        "release_date": product.get("release_date") or "",
        "edition_year": edition_year(product.get("canonical_title"), product.get("release_date")),
        "offer": _offer(family, role),
        "strategy_summary": _strategy_summary(row, product, family),
        "phases": phase_payload,
        "queries": queries,
    }


def build_plans(
    events: list[dict],
    adaptations: list[dict],
    catalog: list[dict],
) -> list[dict]:
    """One promotion plan per (calendar row × selected equivalent product).

    Every dated event gets at least one catalog SKU, and every catalog title is
    assigned to at least one event (franchise first, then platform/window).
    """
    calendar = [row for row in list(events) + list(adaptations) if calendar_label(row)]
    unique = _unique_catalog(catalog)
    catalog_index = _catalog_by_title(unique)
    title_index = build_title_index(unique)
    fallback_pool = [
        item
        for item in unique
        if product_role(item) == "game" and not _is_junk_title(item.get("canonical_title") or "")
    ]
    games_by_bucket: dict[str, list[dict]] = {}
    for item in fallback_pool:
        games_by_bucket.setdefault(product_bucket(item), []).append(item)
    fallback_cursor = [0]
    plans: list[dict] = []
    mapped_titles: set[str] = set()
    events_with_products: set[str] = set()

    for row in calendar:
        owner = showcase_owner(calendar_label(row))
        queries = owned_search_queries(owner) if owner else queries_for_calendar_row(row)
        products = products_for_event(
            row,
            unique,
            catalog_index=catalog_index,
            games_by_bucket=games_by_bucket,
            title_index=title_index,
            fallback_pool=fallback_pool,
            fallback_cursor=fallback_cursor,
        )
        if not products:
            continue
        for product in products:
            plan = _make_plan(row, product, queries=queries)
            if not plan:
                continue
            plans.append(plan)
            title = (plan.get("canonical_title") or "").lower()
            if title:
                mapped_titles.add(title)
            events_with_products.add(calendar_label(row).lower())

    today = date.today()
    events_by_key: dict[str, list[dict]] = {}
    events_by_bucket: dict[str, list[dict]] = {}
    for row in calendar:
        if _parsed_start(row) is None:
            continue
        for key in _event_keys(row):
            events_by_key.setdefault(key, []).append(row)
        events_by_bucket.setdefault(event_bucket(row), []).append(row)

    for product in unique:
        title = (product.get("canonical_title") or "").strip()
        if not title or title.lower() in mapped_titles:
            continue
        row = best_event_for_product(
            product,
            events_by_key=events_by_key,
            events_by_bucket=events_by_bucket,
            today=today,
        )
        if not row:
            continue
        plan = _make_plan(row, product, queries=queries_for_calendar_row(row))
        if not plan:
            continue
        plans.append(plan)
        mapped_titles.add(title.lower())
        events_with_products.add(calendar_label(row).lower())

    # Last pass: dated events that still have no SKU share the fallback pool.
    for row in calendar:
        name = calendar_label(row).lower()
        if name in events_with_products or _parsed_start(row) is None:
            continue
        if not fallback_pool:
            break
        product = fallback_pool[fallback_cursor[0] % len(fallback_pool)]
        fallback_cursor[0] += 1
        plan = _make_plan(row, product, queries=queries_for_calendar_row(row))
        if plan:
            plans.append(plan)
            events_with_products.add(name)

    plans.sort(key=lambda plan: (plan["promo_start"], plan["event"], -plan["edition_year"]))
    return plans


def plans_active_on(plans: list[dict], day: date) -> list[dict]:
    """Plans whose promotion window (lead-in through afterglow) covers `day`."""
    stamp = day.isoformat()
    return [plan for plan in plans if plan["promo_start"] <= stamp <= plan["promo_end"]]


def promotion_document(plan: dict) -> dict:
    phase_lines = []
    for phase in plan.get("phases") or []:
        tactics = "; ".join(phase.get("tactics") or [])
        phase_lines.append(
            f"{phase['label']} ({phase['start']} to {phase['end']}): {tactics}"
        )
    text = "\n".join(
        [
            f"Promotion plan for {plan.get('canonical_title')}",
            f"Storefront equivalent of: {plan.get('event')} ({plan.get('related_game')})",
            f"Event type: {plan.get('event_type')} / {plan.get('promo_family')}",
            f"Event runtime: {plan.get('event_start')} to {plan.get('event_end')}",
            f"Promotion window: {plan.get('promo_start')} to {plan.get('promo_end')}",
            f"Product role: {plan.get('role')}",
            f"Offer: {plan.get('offer')}",
            plan.get("strategy_summary") or "",
            *phase_lines,
            "Promote this product during the equivalent real-world event timeframe, not year-round as a default.",
        ]
    )
    return {
        "id": f"promo:{plan.get('event')}:{plan.get('product_id')}",
        "kind": "promotion",
        "title": f"{plan.get('canonical_title')} × {plan.get('event')}",
        "text": text,
        "metadata": {
            "event": plan.get("event"),
            "promo_start": plan.get("promo_start"),
            "promo_end": plan.get("promo_end"),
            "role": plan.get("role"),
            "canonical_title": plan.get("canonical_title"),
        },
    }


def retrieve_promotions(
    plans: list[dict],
    query: str,
    *,
    on: date | None = None,
    limit: int = 8,
) -> list[tuple[float, dict]]:
    """RAG retrieve over promotion-plan documents, optionally filtered to a date."""
    subset = plans_active_on(plans, on) if on else plans
    documents = [promotion_document(plan) for plan in subset]
    hits = keyword_retrieve(documents, query, limit=limit)
    by_id = {promotion_document(plan)["id"]: plan for plan in subset}
    return [(score, by_id[doc["id"]]) for score, doc in hits if doc["id"] in by_id]


def flatten_plan_rows(plans: list[dict]) -> list[dict]:
    """One CSV row per plan × phase for merchandising calendars."""
    rows = []
    for plan in plans:
        for phase in plan.get("phases") or []:
            rows.append(
                {
                    "event": plan["event"],
                    "event_kind": plan["event_kind"],
                    "event_type": plan["event_type"],
                    "related_game": plan["related_game"],
                    "event_start": plan["event_start"],
                    "event_end": plan["event_end"],
                    "promo_family": plan["promo_family"],
                    "phase": phase["name"],
                    "phase_start": phase["start"],
                    "phase_end": phase["end"],
                    "product_id": plan["product_id"],
                    "product_sku": plan["product_sku"],
                    "canonical_title": plan["canonical_title"],
                    "platform": plan["platform"],
                    "role": plan["role"],
                    "offer": plan["offer"],
                    "tactics": " | ".join(phase.get("tactics") or []),
                    "strategy_summary": plan["strategy_summary"],
                }
            )
    return rows


def write_promotion_csv(plans: list[dict], path=None):
    path = path or (DATA_PROCESSED / "promotion_calendar.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = flatten_plan_rows(plans)
    if not rows:
        return path
    fieldnames = list(rows[0].keys())
    gz_path = gzip_sidecar(path)
    with gzip.open(gz_path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if path.exists() and path != gz_path:
        path.unlink()
    return gz_path
