"""Match calendar franchises to catalog product titles."""

from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache

GENERIC_RELATED = {
    "multi-platform",
    "multi-game",
    "pc",
    "steam",
    "pc / steam",
    "pc / console",
    "pc / console / mobile",
    "pc / playstation / xbox / nintendo",
    "playstation / xbox / nintendo / pc",
    "pc / playstation / xbox / nintendo / anime",
    "xbox / pc",
    "playstation",
    "nintendo",
    "indie",
    "gaming",
    "anime",
    "anime games / jrpg",
    "shonen jump franchises",
    "apple / mac / ios",
    "marvel, dc, star wars, gaming adaptations",
    "marvel, dc, star wars",
    "marvel, dc, anime, gaming",
    "marvel, dc, anime",
    "disney, marvel, star wars",
}

# Keep named IPs even when they sit in a comma-separated platform-ish field.
FRANCHISE_ALIASES = {
    "warcraft": ["warcraft", "world of warcraft"],
    "diablo": ["diablo"],
    "overwatch": ["overwatch"],
    "pubg": ["pubg", "battlegrounds"],
    "league of legends": ["league of legends"],
    "counter-strike 2": ["counter-strike", "counter strike", "cs2"],
    "rainbow six siege": ["rainbow six", "rainbow six siege"],
    "pga tour 2k": ["pga tour", "pga 2k"],
    "nba 2k": ["nba 2k"],
    "nhl": ["nhl"],
    "ea sports fc": ["ea sports fc", "fifa"],
    "tennis games": ["topspin", "ao tennis", "matchpoint - tennis"],
    "cycling games": ["tour de france", "pro cycling manager"],
    "nintendo franchises": ["mario", "zelda", "pokemon", "pokémon"],
    "street fighter": ["street fighter"],
    "tekken": ["tekken"],
    "mortal kombat": ["mortal kombat"],
    "quake": ["quake"],
    "doom": ["doom"],
    "bethesda": ["bethesda"],
    "pokemon": ["pokemon", "pokémon"],
    "fortnite": ["fortnite"],
    "valorant": ["valorant"],
    "rocket league": ["rocket league"],
    "honor of kings": ["honor of kings"],
    "f1": ["f1"],
    "madden nfl": ["madden nfl"],
    "mlb the show": ["mlb the show"],
    "resident evil": ["resident evil"],
    "monster hunter": ["monster hunter"],
    "assassin's creed": ["assassin's creed", "assassins creed"],
    "far cry": ["far cry"],
    "mario": ["mario"],
    "zelda": ["zelda", "legend of zelda"],
    "devil may cry": ["devil may cry"],
    "among us": ["among us"],
    "angry birds": ["angry birds"],
    "ark: survival evolved": ["ark:"],
    "sekiro: shadows die twice": ["sekiro"],
    "fallout": ["fallout"],
    "the last of us": ["the last of us"],
    "god of war": ["god of war"],
    "tomb raider": ["tomb raider"],
    "life is strange": ["life is strange"],
    "mass effect": ["mass effect"],
    "minecraft": ["minecraft"],
    "cyberpunk 2077": ["cyberpunk"],
    "horizon": ["horizon zero dawn", "horizon forbidden west"],
    "ghost of tsushima": ["ghost of tsushima"],
    "sonic": ["sonic"],
    "helldivers": ["helldivers"],
    "death stranding": ["death stranding"],
    "elden ring": ["elden ring"],
    "call of duty": ["call of duty", "modern warfare"],
    "spider-man": [
        "spider-man",
        "spiderman",
        "spider man",
        "miles morales",
        "spider-verse",
        "spider verse",
        "into the spider verse",
        "across the spider verse",
        "beyond the spider verse",
    ],
    "batman": ["batman", "arkham"],
    "star wars": ["star wars"],
    "superman": ["superman"],
    "supergirl": ["supergirl"],
    "wolverine": ["wolverine"],
    "guardians of the galaxy": ["guardians of the galaxy"],
    "injustice": ["injustice"],
    "gotham knights": ["gotham knights"],
    "suicide squad": ["suicide squad"],
    "marvel": ["marvel", "avengers", "mcu"],
    "dc": ["dc comics", "dc universe", "dcu"],
    "disney": ["disney", "pixar", "kingdom hearts", "disney dreamlight", "disney infinity"],
    "teenage mutant ninja turtles": ["teenage mutant ninja turtles", "tmnt", "mutant mayhem"],
    "transformers": ["transformers"],
    "grand theft auto": ["grand theft auto", "gta"],
    "the witcher": ["the witcher", "witcher"],
    "metroid": ["metroid"],
    "hollow knight": ["hollow knight", "silksong"],
    "bioshock": ["bioshock"],
    "the elder scrolls": ["the elder scrolls", "elder scrolls", "skyrim", "oblivion"],
    "mafia": ["mafia"],
    "fable": ["fable"],
    "okami": ["okami", "ōkami"],
}


def normalize_franchise_text(value: str | None) -> str:
    """Normalize punctuation so Spider-Man, Spider Man, and Spiderman correlate."""
    text = (value or "").lower().replace("’", "'")
    text = re.sub(r"[-_:.'’]+", " ", text)
    text = re.sub(r"\bspider\s*man\b", "spiderman", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Character IPs that merchandising treats as the Marvel or DC catalog.
CHARACTER_UNIVERSE = {
    "spider-man": "marvel",
    "wolverine": "marvel",
    "guardians of the galaxy": "marvel",
    "batman": "dc",
    "superman": "dc",
    "supergirl": "dc",
    "injustice": "dc",
    "gotham knights": "dc",
    "suicide squad": "dc",
}

MARVEL_CATALOG_QUERIES = (
    "marvel",
    "avengers",
    "spider-man",
    "spiderman",
    "miles morales",
    "spider-verse",
    "wolverine",
    "guardians of the galaxy",
    "midnight suns",
    "deadpool",
    "x-men",
    "fantastic four",
    "venom",
    "captain america",
    "black panther",
    "daredevil",
)

DC_CATALOG_QUERIES = (
    "batman",
    "arkham",
    "superman",
    "supergirl",
    "injustice",
    "gotham knights",
    "gotham",
    "suicide squad",
    "justice league",
    "wonder woman",
    "lego batman",
    "lego dc",
)

UNIVERSE_QUERIES = {
    "marvel": list(MARVEL_CATALOG_QUERIES),
    "dc": list(DC_CATALOG_QUERIES),
}

_MARVEL_NAME_HINTS = (
    "marvel",
    "avengers",
    "mcu",
    "spider man",
    "spiderman",
    "brand new day",
    "secret wars",
    "fantastic four",
    "deadpool",
    "wolverine",
    "thunderbolts",
    "captain america",
    "black panther",
    "daredevil",
    "guardians of the galaxy",
    "born again",
    "spider verse",
    "what if",
    "x men 97",
    "friendly neighborhood spider",
    "i am groot",
    "moon girl",
    "marvel zombies",
    "eyes of wakanda",
)
_DC_NAME_HINTS = (
    "dc comics",
    "dc universe",
    "dcu",
    "superman",
    "supergirl",
    "batman",
    "clayface",
    "man of tomorrow",
    "wonder woman",
    "suicide squad",
    "lanterns",
    "joker",
    "aquaman",
    "harley quinn",
    "creature commandos",
    "caped crusader",
    "kite man",
    "league of super pets",
    "my adventures with superman",
)


@lru_cache(maxsize=32768)
def franchise_keys_for_text(value: str | None) -> frozenset[str]:
    """Return canonical franchise keys mentioned by a title or related-IP field."""
    normalized = normalize_franchise_text(value)
    keys: set[str] = set()
    for key, aliases in FRANCHISE_ALIASES.items():
        candidates = [key, *aliases]
        for alias in candidates:
            normalized_alias = normalize_franchise_text(alias)
            if normalized_alias and re.search(
                rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", normalized
            ):
                keys.add(key)
                break
    extra = {CHARACTER_UNIVERSE[key] for key in keys if key in CHARACTER_UNIVERSE}
    return keys | extra


def _is_superhero_media(row: dict) -> bool:
    kind = (row.get("kind") or "").lower()
    event_type = f"{row.get('event_type') or ''} {row.get('medium') or ''} {row.get('format') or ''}".lower()
    if kind == "adaptation" or row.get("ip_adaptation"):
        return True
    return any(token in event_type for token in ("film", "theatrical", "ott", "series", "streaming"))


def superhero_universe_for_row(row: dict | str | None) -> str | None:
    """Marvel or DC when the row is a superhero film/series, else None.

    Conventions and mixed 'Marvel, DC, Star Wars' related-game fields stay
    generic so they do not swallow the whole superhero catalog.
    """
    if not isinstance(row, dict):
        text = normalize_franchise_text(row)
        if any(hint in text for hint in _MARVEL_NAME_HINTS):
            return "marvel"
        if any(hint in text for hint in _DC_NAME_HINTS) or re.search(r"\bdc\b", text):
            return "dc"
        return None
    related = normalize_franchise_text(row.get("related_game") or "")
    if related in {"marvel", "mcu"}:
        return "marvel"
    if related in {"dc", "dcu", "dc comics"}:
        return "dc"
    if not _is_superhero_media(row):
        return None
    blob = normalize_franchise_text(
        f"{row.get('event') or ''} {row.get('ip_adaptation') or ''} {row.get('related_game') or ''}"
    )
    if any(hint in blob for hint in _MARVEL_NAME_HINTS):
        return "marvel"
    if any(hint in blob for hint in _DC_NAME_HINTS) or re.search(r"\bdc\b", blob):
        return "dc"
    return None


def franchises_overlap(left: str | None, right: str | None) -> bool:
    return bool(franchise_keys_for_text(left) & franchise_keys_for_text(right))


def franchise_queries(related_game: str | None) -> list[str]:
    """Turn a calendar 'related game' field into searchable title fragments."""
    raw = (related_game or "").strip()
    if not raw:
        return []
    lowered = raw.lower()
    if lowered in GENERIC_RELATED:
        return []

    queries: list[str] = []
    for chunk in re.split(r",|/|;", raw):
        name = chunk.strip()
        if len(name) < 3:
            continue
        if name.lower() in GENERIC_RELATED:
            continue
        key = name.lower()
        if key in FRANCHISE_ALIASES:
            queries.extend(FRANCHISE_ALIASES[key])
        else:
            queries.append(name.lower())
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


EVENT_TYPE_QUERIES = {
    "football": ["ea sports fc", "fifa", "football manager", "efootball"],
    "golf": ["pga tour", "ea sports pga"],
    "basketball": ["nba 2k"],
    "ice hockey": ["nhl"],
    "tennis": ["topspin", "ao tennis", "matchpoint - tennis"],
    "cycling": ["tour de france", "pro cycling manager"],
    "motorsport": ["f1"],
    "american football": ["madden nfl"],
    "baseball": ["mlb the show"],
    "fighting games": ["street fighter", "tekken", "mortal kombat"],
}


def _unique_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        if query and query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def queries_for_calendar_row(row: dict) -> list[str]:
    """Franchise queries from related-game, adaptation title, event name, and announced ties."""
    queries: list[str] = []
    related = (row.get("related_game") or "").strip()
    if related and related.lower() not in GENERIC_RELATED and "," not in related and "/" not in related:
        # Prefer exact announced title before broad franchise expansion.
        queries.append(related.lower())
    queries.extend(franchise_queries(row.get("related_game")))
    if row.get("kind") == "adaptation" or row.get("ip_adaptation"):
        queries.extend(franchise_queries(row.get("ip_adaptation")))
    queries.extend(franchise_queries(row.get("event")))
    queries.extend(franchise_queries(row.get("correlated_announced")))
    event_type = (row.get("event_type") or "").strip().lower()
    queries.extend(EVENT_TYPE_QUERIES.get(event_type, []))
    universe = superhero_universe_for_row(row)
    if universe:
        queries.extend(UNIVERSE_QUERIES.get(universe) or [])
    return _unique_queries(queries)


def _compile_queries(queries: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    # Trailing (?![a-z]) lets "nba 2k" match "NBA 2K25" while still rejecting "fifania".
    return [
        (query, re.compile(rf"(?<!\w){re.escape(query)}(?![a-z])", re.I))
        for query in queries
    ]


GUEST_CROSSOVER = (
    "dead by daylight",
    "fortnite x",
    "crossover",
    "outfit dlc",
)


def _query_score(canonical: str, full_title: str, compiled: list[tuple[str, re.Pattern[str]]]) -> int:
    """Higher is a tighter franchise match (prefix beats a mid-title cameo)."""
    best = 0
    haystacks = (canonical.lower(), full_title.lower())
    blob = " ".join(haystacks)
    guest = any(marker in blob for marker in GUEST_CROSSOVER)
    for query, pattern in compiled:
        if query not in blob:
            continue
        for text in haystacks:
            if not pattern.search(text):
                continue
            if text == query or text.startswith(query + " ") or text.startswith(query + ":"):
                best = max(best, 3)
            elif text.startswith(query):
                best = max(best, 2)
            elif guest:
                best = max(best, 1)
            else:
                # "Marvel's Spider-Man 2" is a primary IP match, not a cameo.
                best = max(best, 2)
    return best
    return best


def match_catalog(
    catalog: list[dict],
    queries: list[str],
    *,
    limit: int = 25,
    min_score: int = 1,
) -> list[dict]:
    ranked = rank_catalog(catalog, queries, min_score=min_score)
    return [row for _, row in ranked[:limit]]


def rank_catalog(
    catalog: list[dict],
    queries: list[str],
    *,
    min_score: int = 1,
    title_index: dict[str, list[dict]] | None = None,
) -> list[tuple[int, dict]]:
    if not queries:
        return []
    if title_index:
        candidates: list[dict] = []
        seen: set[int] = set()
        for query in queries:
            tokens = re.findall(r"[a-z0-9]+", query.lower())
            if not tokens:
                continue
            # Require the longest token so "sports" alone does not pull the whole catalog.
            token = max(tokens, key=len)
            if len(token) < 2:
                continue
            for row in title_index.get(token, ()):
                marker = id(row)
                if marker in seen:
                    continue
                seen.add(marker)
                candidates.append(row)
        catalog = candidates
    compiled = _compile_queries(queries)
    ranked: list[tuple[int, dict]] = []
    seen_titles: set[str] = set()
    for row in catalog:
        canonical = row.get("canonical_title") or row.get("product_title") or ""
        score = _query_score(canonical, row.get("product_title") or "", compiled)
        if score < min_score:
            continue
        key = canonical.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        ranked.append((score, row))
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].get("release_date") or "",
            item[1].get("canonical_title") or "",
        ),
        reverse=True,
    )
    return ranked


def build_title_index(catalog: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for row in catalog:
        title = f"{row.get('canonical_title') or ''} {row.get('product_title') or ''}".lower()
        seen: set[str] = set()
        for token in re.findall(r"[a-z0-9]+", title):
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            index.setdefault(token, []).append(row)
    return index


def catalog_around_window(
    catalog: list[dict],
    start: date | None,
    end: date | None,
    *,
    pad_days: int = 21,
) -> list[dict]:
    """Catalog games whose release date falls near an event window."""
    if start is None and end is None:
        return []
    window_start = (start or end) - timedelta(days=pad_days)
    window_end = (end or start) + timedelta(days=pad_days)
    hits = []
    seen: set[str] = set()
    for row in catalog:
        release = row.get("release_date_parsed")
        if not isinstance(release, date):
            continue
        if window_start <= release <= window_end:
            key = row.get("canonical_title") or row["product_title"]
            if key in seen:
                continue
            seen.add(key)
            hits.append(row)
    hits.sort(key=lambda row: row["release_date_parsed"] or date.min)
    return hits
