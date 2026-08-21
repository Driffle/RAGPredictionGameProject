"""Country-wise product and event placement derived from calendar coverage."""

from __future__ import annotations

import re
from datetime import date, timedelta

from src.calendar_dedupe import canonical_event_name, is_quarter_timeframe

# Google Trends RSS still uses a short list (src.trends). Placement and the
# market/language picker use every geography below.

GEO_META = {
    "WW": {"country": "Worldwide", "language": "Multiple", "locale": "en"},
    "US": {"country": "United States", "language": "English", "locale": "en"},
    "CA": {"country": "Canada", "language": "English / Français", "locale": "en-CA"},
    "GB": {"country": "United Kingdom", "language": "English", "locale": "en-GB"},
    "IE": {"country": "Ireland", "language": "English", "locale": "en-IE"},
    "DE": {"country": "Germany", "language": "Deutsch", "locale": "de"},
    "FR": {"country": "France", "language": "Français", "locale": "fr"},
    "ES": {"country": "Spain", "language": "Español", "locale": "es"},
    "IT": {"country": "Italy", "language": "Italiano", "locale": "it"},
    "NL": {"country": "Netherlands", "language": "Nederlands", "locale": "nl"},
    "BE": {"country": "Belgium", "language": "Nederlands / Français", "locale": "nl"},
    "SE": {"country": "Sweden", "language": "Svenska", "locale": "sv"},
    "DK": {"country": "Denmark", "language": "Dansk", "locale": "da"},
    "NO": {"country": "Norway", "language": "Norsk", "locale": "nb"},
    "FI": {"country": "Finland", "language": "Suomi", "locale": "fi"},
    "PL": {"country": "Poland", "language": "Polski", "locale": "pl"},
    "CZ": {"country": "Czechia", "language": "Čeština", "locale": "cs"},
    "AT": {"country": "Austria", "language": "Deutsch", "locale": "de-AT"},
    "CH": {"country": "Switzerland", "language": "Deutsch / Français / Italiano", "locale": "de-CH"},
    "PT": {"country": "Portugal", "language": "Português", "locale": "pt-PT"},
    "HR": {"country": "Croatia", "language": "Hrvatski", "locale": "hr"},
    "TR": {"country": "Türkiye", "language": "Türkçe", "locale": "tr"},
    "JP": {"country": "Japan", "language": "日本語", "locale": "ja"},
    "KR": {"country": "South Korea", "language": "한국어", "locale": "ko"},
    "CN": {"country": "China", "language": "中文", "locale": "zh-CN"},
    "TW": {"country": "Taiwan", "language": "中文（台灣）", "locale": "zh-TW"},
    "HK": {"country": "Hong Kong", "language": "中文 / English", "locale": "zh-HK"},
    "SG": {"country": "Singapore", "language": "English", "locale": "en-SG"},
    "IN": {"country": "India", "language": "English / हिन्दी", "locale": "en-IN"},
    "TH": {"country": "Thailand", "language": "ไทย", "locale": "th"},
    "ID": {"country": "Indonesia", "language": "Bahasa Indonesia", "locale": "id"},
    "PH": {"country": "Philippines", "language": "English", "locale": "en-PH"},
    "VN": {"country": "Vietnam", "language": "Tiếng Việt", "locale": "vi"},
    "AU": {"country": "Australia", "language": "English", "locale": "en-AU"},
    "NZ": {"country": "New Zealand", "language": "English", "locale": "en-NZ"},
    "BR": {"country": "Brazil", "language": "Português", "locale": "pt-BR"},
    "MX": {"country": "Mexico", "language": "Español", "locale": "es-MX"},
    "AR": {"country": "Argentina", "language": "Español", "locale": "es-AR"},
    "CL": {"country": "Chile", "language": "Español", "locale": "es-CL"},
    "CO": {"country": "Colombia", "language": "Español", "locale": "es-CO"},
    "SA": {"country": "Saudi Arabia", "language": "العربية", "locale": "ar"},
    "AE": {"country": "United Arab Emirates", "language": "العربية / English", "locale": "ar"},
    "QA": {"country": "Qatar", "language": "العربية / English", "locale": "ar"},
    "MA": {"country": "Morocco", "language": "العربية / Français", "locale": "ar"},
    "ZA": {"country": "South Africa", "language": "English", "locale": "en-ZA"},
}

PLACEMENT_GEOS = tuple(code for code in GEO_META if code != "WW")
WORLDWIDE_GEO = "WW"

LOCATION_HINTS: dict[str, tuple[str, ...]] = {
    "US": (
        "united states",
        "u.s.a",
        "u.s.",
        "usa",
        "atlanta",
        "anaheim",
        "austin",
        "boston",
        "chicago",
        "las vegas",
        "los angeles",
        "new york",
        "orlando",
        "san diego",
        "seattle",
        "san francisco",
        "national harbor",
        "honolulu",
        "hawaii",
        "new orleans",
        "glendale",
        "hollywood",
        "florida",
        "fort worth",
        "santa clara",
        "cupertino",
        "dallas",
        "bellevue",
        "inglewood",
        "grapevine",
        "texas",
        "augusta",
    ),
    "CA": ("canada", "montreal", "montréal", "toronto", "vancouver", "ottawa"),
    "GB": (
        "united kingdom",
        "england",
        "scotland",
        "wales",
        "london",
        "brighton",
        "birmingham",
        "manchester",
        "edinburgh",
        "glasgow",
    ),
    "IE": ("ireland", "dublin"),
    "DE": ("germany", "deutschland", "berlin", "cologne", "köln", "hamburg", "munich", "münchen"),
    "FR": ("france", "paris", "lyon", "lille", "cannes"),
    "ES": ("spain", "españa", "madrid", "barcelona"),
    "IT": ("italy", "italia", "milan", "milano", "rome", "roma"),
    "NL": ("netherlands", "holland", "amsterdam", "rotterdam", "utrecht"),
    "BE": ("belgium", "antwerp", "antwerpen", "brussels", "bruxelles"),
    "SE": ("sweden", "swedish", "stockholm", "malmö", "malmo", "jönköping", "jonkoping"),
    "DK": ("denmark", "copenhagen", "københavn"),
    "NO": ("norway", "oslo", "bergen"),
    "FI": ("finland", "helsinki"),
    "PL": ("poland", "polish", "kraków", "krakow", "katowice", "warsaw", "warszawa"),
    "CZ": ("czech", "prague", "praha"),
    "AT": ("austria", "vienna", "wien"),
    "CH": ("switzerland", "zurich", "zürich", "geneva", "genève"),
    "PT": ("portugal", "lisbon", "lisboa"),
    "HR": ("croatia", "dubrovnik", "zagreb"),
    "TR": ("turkey", "türkiye", "istanbul"),
    "JP": (
        "japan",
        "tokyo",
        "osaka",
        "kyoto",
        "chiba",
        "makuhari",
        "yokohama",
    ),
    "KR": (
        "south korea",
        "korea",
        "korean",
        "busan",
        "seoul",
        "incheon",
        "g-star",
        "gstar",
        "bic fest",
        "busan indie",
    ),
    "CN": ("china", "chinese", "shanghai", "beijing", "chengdu", "guangzhou", "hangzhou", "chinajoy"),
    "TW": ("taiwan", "taipei", "taipei game show"),
    "HK": ("hong kong", "hongkong"),
    "SG": ("singapore",),
    "IN": ("india", "hyderabad", "mumbai", "bengaluru", "bangalore", "delhi", "chennai"),
    "TH": ("thailand", "bangkok"),
    "ID": ("indonesia", "jakarta"),
    "PH": ("philippines", "manila"),
    "VN": ("vietnam", "hanoi", "ho chi minh"),
    "AU": ("australia", "sydney", "melbourne", "brisbane", "perth"),
    "NZ": ("new zealand", "auckland", "wellington"),
    "BR": ("brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro"),
    "MX": ("mexico", "méxico", "mexico city", "ciudad de méxico"),
    "AR": ("argentina", "buenos aires"),
    "CL": ("chile", "santiago"),
    "CO": ("colombia", "bogotá", "bogota"),
    "SA": ("saudi", "riyadh", "jeddah", "esl riyadh", "gamers8"),
    "AE": ("united arab emirates", "dubai", "abu dhabi"),
    "QA": ("qatar", "doha"),
    "MA": ("morocco", "marrakech", "casablanca", "rabat"),
    "ZA": ("south africa", "johannesburg", "cape town"),
}

GLOBAL_HINTS = (
    "online",
    "worldwide",
    "world wide",
    "global",
    "digital",
    "streaming",
    "retail",
    "youtube",
    "twitch",
)

# Locations that are not places (bad ODS / scrape cells).
NON_PLACES = ("gaming", "planning window")

# Named events whose calendar templates omit a city. Longest needle wins.
# digital=True also places the window in the Worldwide section.
_EVENT_HOSTS: tuple[tuple[str, tuple[str, ...], str, bool], ...] = (
    ("nintendo direct", ("JP",), "Kyoto", True),
    ("steam next fest", ("US",), "Bellevue", True),
    ("steam winter sale", ("US",), "Bellevue", True),
    ("steam awards", ("US",), "Bellevue", True),
    ("xbox developer direct", ("US",), "Redmond", True),
    ("xbox games showcase", ("US",), "Redmond", True),
    ("playstation state of play", ("JP",), "Tokyo", True),
    ("state of play", ("JP",), "Tokyo", True),
    ("capcom showcase", ("JP",), "Osaka", True),
    ("ubisoft forward", ("FR",), "Paris", True),
    ("pc gaming show", ("GB",), "London", True),
    ("summer game fest", ("US",), "Los Angeles", True),
    ("the game awards", ("US",), "Los Angeles", True),
    ("gamescom latam", ("BR",), "São Paulo", False),
    ("gamescom opening night live", ("DE",), "Cologne", True),
    ("future games show at gamescom", ("DE",), "Cologne", True),
    ("gamescom", ("DE",), "Cologne", False),
    ("devcom", ("DE",), "Cologne", False),
    ("gdc", ("US",), "San Francisco", False),
    ("ces gaming", ("US",), "Las Vegas", False),
    ("sxsw gaming", ("US",), "Austin", False),
    ("pax east", ("US",), "Boston", False),
    ("pax west", ("US",), "Seattle", False),
    ("d.i.c.e. awards", ("US",), "Las Vegas", False),
    ("dice awards", ("US",), "Las Vegas", False),
    ("anime expo", ("US",), "Los Angeles", False),
    ("d23", ("US",), "Anaheim", False),
    ("blizzcon", ("US",), "Anaheim", False),
    ("wwdc", ("US",), "Cupertino", False),
    ("jump festa", ("JP",), "Chiba", False),
    ("bafta games awards", ("GB",), "London", False),
    ("golden joystick awards", ("GB",), "London", False),
    ("roland-garros", ("FR",), "Paris", False),
    ("french open", ("FR",), "Paris", False),
    ("the masters", ("US",), "Augusta", False),
    ("pga championship", ("US",), "United States", False),
    ("the open championship", ("GB",), "United Kingdom", False),
    ("nba playoffs", ("US",), "United States", False),
    ("stanley cup", ("US", "CA"), "", False),
    ("nfl season", ("US",), "United States", False),
    ("mlb postseason", ("US",), "United States", False),
    ("iihf world championship", ("CH",), "Switzerland", False),
    ("f1 world championship", ("GB",), "United Kingdom", True),
    ("formula 1", ("GB",), "United Kingdom", True),
    ("six invitational", ("US",), "Boston", False),
    ("esports world cup", ("SA",), "Riyadh", False),
    ("esports awards", ("US",), "Las Vegas", False),
    ("evo", ("US",), "Las Vegas", False),
    ("pokémon world championships", ("US",), "United States", True),
    ("pokemon world championships", ("US",), "United States", True),
    ("league of legends worlds", ("WW",), "", True),
    ("league of legends msi", ("WW",), "", True),
    ("valorant champions", ("WW",), "", True),
    ("counter-strike major", ("WW",), "", True),
    ("rocket league world championship", ("US",), "United States", True),
    ("honor of kings world cup", ("CN", "SA"), "", False),
    ("fortnite global championship", ("US",), "United States", True),
    ("quakecon", ("US",), "Dallas", True),
    ("day of the devs", ("US",), "Los Angeles", True),
    ("2026 fifa world cup", ("US", "MX", "CA"), "", False),
    ("fifa world cup 2026", ("US", "MX", "CA"), "", False),
    ("fifa women's world cup", ("BR",), "Brazil", False),
    ("fifa world cup 2030", ("ES", "PT", "MA"), "", False),
    ("2030 fifa world cup", ("ES", "PT", "MA"), "", False),
    ("2028 summer olympics", ("US",), "Los Angeles", False),
    ("summer olympics", ("US",), "Los Angeles", False),
    ("uefa euro", ("GB", "IE"), "", False),
    ("iem katowice", ("PL",), "Katowice", False),
    ("taipei game show", ("TW",), "Taipei", False),
    ("tokyo game show", ("JP",), "Tokyo", False),
    ("chinajoy", ("CN",), "Shanghai", False),
    ("paris games week", ("FR",), "Paris", False),
    ("tour de france", ("FR",), "France", False),
)

EVENT_HOSTS = tuple(sorted(_EVENT_HOSTS, key=lambda row: len(row[0]), reverse=True))


def _haystack(row: dict) -> str:
    parts = [
        row.get("location") or "",
        row.get("event") or "",
        row.get("ip_adaptation") or "",
        row.get("related_game") or "",
        row.get("organizer") or "",
        row.get("scope") or "",
    ]
    return " ".join(parts).lower()


def _is_worldwide(row: dict, haystack: str) -> bool:
    location = (row.get("location") or "").strip().lower()
    scope = (row.get("scope") or "").strip().lower()
    attendance = (row.get("attendance_mode") or "").strip().lower()
    if attendance == "digital":
        return True
    if scope == "global":
        return True
    if location in {"online", "global", "worldwide", "online / retail"}:
        return True
    return any(hint in haystack for hint in GLOBAL_HINTS)


def _hint_hits(haystack: str, hint: str) -> bool:
    """Match a place hint without treating 'usa' as a substring of 'Busan'."""
    pattern = rf"(?<![a-z0-9]){re.escape(hint)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def host_spec_for_event(name: str) -> dict | None:
    """Look up a named event's host countries, city, and display location."""
    text = (name or "").strip().lower()
    if not text:
        return None
    for needle, geos, city, digital in EVENT_HOSTS:
        if _hint_hits(text, needle):
            return {
                "geos": geos,
                "city": city,
                "digital": digital,
                "location": _location_from_host(geos, city, digital),
                "mode": "digital" if digital else "physical",
            }
    return None


def _location_from_host(geos: tuple[str, ...], city: str, digital: bool) -> str:
    countries = [GEO_META[geo]["country"] for geo in geos if geo != WORLDWIDE_GEO and geo in GEO_META]
    city = (city or "").strip()
    if city and countries and city.lower() not in {item.lower() for item in countries}:
        if len(countries) == 1:
            label = f"{city}, {countries[0]}"
        else:
            label = f"{city} ({', '.join(countries)})"
    elif countries:
        label = ", ".join(countries)
    else:
        label = "International (rotating host countries)"
    if digital:
        if countries:
            return f"{label} · Online / worldwide"
        return "Online / Worldwide"
    return label


def _unique_geos(codes: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for geo in codes:
        if geo in GEO_META and geo not in seen:
            seen.add(geo)
            out.append(geo)
    return tuple(out)


def geos_for_event(row: dict) -> tuple[str, ...]:
    """Return geographies where an event should be placed.

    Physical/hybrid city events map to that country only. Named hosts
    (GDC, Nintendo Direct, Roland-Garros, …) fill in a country even when
    the calendar row left location blank. Digital and worldwide windows
    also land in the WW bucket — never the United States by default.
    Unknown cities are left unmapped rather than dumped into US.
    """
    name = row.get("event") or row.get("ip_adaptation") or ""
    host = host_spec_for_event(name)
    haystack = _haystack(row)
    location = (row.get("location") or "").strip().lower()
    if location in NON_PLACES or location[:1].isdigit():
        haystack = _haystack({**row, "location": ""})

    matched: list[str] = []
    for geo, hints in LOCATION_HINTS.items():
        if any(_hint_hits(haystack, hint) for hint in hints):
            matched.append(geo)
    if host:
        matched.extend(geo for geo in host["geos"] if geo != WORLDWIDE_GEO)

    worldwide = _is_worldwide(row, haystack) or bool(host and host["digital"])
    if host and WORLDWIDE_GEO in host["geos"]:
        worldwide = True

    geos = list(matched)
    if worldwide:
        geos.append(WORLDWIDE_GEO)
    return _unique_geos(geos)


def _country_already_in(location: str, countries: list[str]) -> bool:
    low = location.lower()
    return any(country.lower() in low for country in countries)


def location_display_for(row: dict, geos: tuple[str, ...] | None = None) -> str:
    geos = geos if geos is not None else geos_for_event(row)
    name = row.get("event") or row.get("ip_adaptation") or ""
    host = host_spec_for_event(name)
    raw = (row.get("location") or "").strip()
    countries = [GEO_META[geo]["country"] for geo in geos if geo != WORLDWIDE_GEO]
    low = raw.lower()
    if raw and low not in NON_PLACES and not raw[:1].isdigit():
        if low in {"online", "global", "worldwide", "online / retail"}:
            if host:
                return host["location"]
            if countries:
                return f"{', '.join(countries)} · Online / worldwide"
            return "Online / Worldwide"
        if countries and not _country_already_in(raw, countries):
            if len(countries) == 1:
                return f"{raw}, {countries[0]}"
            return f"{raw} ({', '.join(countries)})"
        return raw
    if host:
        return host["location"]
    if countries:
        return ", ".join(countries)
    if WORLDWIDE_GEO in geos:
        return "Online / Worldwide"
    return raw


def annotate_event_geo(row: dict) -> dict:
    """Country, language, and display location for an event row."""
    geos = geos_for_event(row)
    host = host_spec_for_event(row.get("event") or row.get("ip_adaptation") or "")
    primary = next((geo for geo in geos if geo != WORLDWIDE_GEO), WORLDWIDE_GEO if geos else "")
    meta = GEO_META.get(primary) or GEO_META[WORLDWIDE_GEO]
    countries = []
    for geo in geos:
        info = GEO_META.get(geo)
        if not info:
            continue
        countries.append({"geo": geo, **info})
    languages: list[str] = []
    for item in countries:
        language = item.get("language") or ""
        if language and language not in languages:
            languages.append(language)
    country_label = meta["country"]
    if primary == WORLDWIDE_GEO:
        country_label = "Worldwide" if geos else ""
    return {
        "geos": geos,
        "country_code": primary,
        "country": country_label,
        "language": meta["language"],
        "locale": meta["locale"],
        "countries": countries,
        "languages": languages,
        "location_display": location_display_for(row, geos),
        "digital": bool(host and host["digital"]),
    }


def apply_event_geo(row: dict) -> dict:
    """Stamp country, language, and a country-bearing location onto a calendar row."""
    info = annotate_event_geo(row)
    out = dict(row)
    out["location"] = info["location_display"] or out.get("location") or ""
    out["country"] = info["country"]
    out["country_code"] = info["country_code"]
    out["language"] = info["language"]
    out["locale"] = info["locale"]
    out["geos"] = ",".join(info["geos"])
    return out


def market_sections(row: dict, products: list[dict] | None = None) -> list[dict]:
    """One section per host country (plus Worldwide) with language and SKUs."""
    info = annotate_event_geo(row)
    recs = products or []
    return [
        {
            **item,
            "location": info["location_display"],
            "products": recs[:12],
        }
        for item in info["countries"]
    ]


def placement_payload(
    events: list[dict],
    adaptations: list[dict],
    plans: list[dict],
    *,
    on: date | None = None,
    horizon_days: int = 365,
    limit: int = 24,
) -> dict:
    """Build one section per country (plus Worldwide) from upcoming events."""
    today = on or date.today()
    start = today.isoformat()
    end = (today + timedelta(days=horizon_days)).isoformat()
    rows = []
    for row in events + adaptations:
        row_end = (row.get("end_date") or row.get("start_date") or "")[:10]
        row_start = (row.get("start_date") or "")[:10]
        if row_start and row_end >= start and row_start <= end:
            rows.append(row)

    plan_by_event: dict[str, list[dict]] = {}
    for plan in plans:
        name = (plan.get("event") or "").strip().lower()
        if name:
            plan_by_event.setdefault(name, []).append(plan)

    geo_keys = (WORLDWIDE_GEO,) + PLACEMENT_GEOS
    placements = {
        geo: {
            **GEO_META[geo],
            "geo": geo,
            "events": [],
            "products": [],
        }
        for geo in geo_keys
    }
    event_seen = {geo: set() for geo in geo_keys}
    product_seen = {geo: set() for geo in geo_keys}

    for row in sorted(rows, key=lambda item: item.get("start_date") or "9999"):
        name = row.get("event") or row.get("ip_adaptation") or ""
        if is_quarter_timeframe(name):
            continue
        geos = geos_for_event(row)
        geo_info = annotate_event_geo(row)
        event_card = {
            "name": name,
            "start": row.get("start_date") or "",
            "end": row.get("end_date") or row.get("start_date") or "",
            "location": geo_info["location_display"]
            or row.get("location")
            or ("Online / Worldwide" if WORLDWIDE_GEO in geos and len(geos) == 1 else ""),
            "country": geo_info["country"],
            "country_code": geo_info["country_code"],
            "language": geo_info["language"],
            "locale": geo_info["locale"],
            "scope": row.get("scope") or ("global" if geos == (WORLDWIDE_GEO,) else "regional"),
            "kind": row.get("kind") or "event",
            "related": row.get("related_game") or "",
            "placement_scope": "global" if geos == (WORLDWIDE_GEO,) else "country",
        }
        for geo in geos:
            if geo not in placements:
                continue
            listing_key = (canonical_event_name(name), (row.get("start_date") or "")[:10])
            if name and listing_key not in event_seen[geo] and listing_key[0]:
                event_seen[geo].add(listing_key)
                placements[geo]["events"].append(event_card)
            for plan in plan_by_event.get(name.lower(), []):
                title = plan.get("canonical_title") or ""
                if not title or title.lower() in product_seen[geo]:
                    continue
                product_seen[geo].add(title.lower())
                placements[geo]["products"].append(
                    {
                        "canonical_title": title,
                        "event": name,
                        "platform": plan.get("platform") or "",
                        "role": plan.get("role") or "game",
                        "placement_scope": event_card["placement_scope"],
                    }
                )

    for geo, payload in placements.items():
        payload["events"].sort(
            key=lambda row: (
                0 if row["placement_scope"] == "country" else 1,
                row.get("start") or "9999",
            )
        )
        payload["products"].sort(
            key=lambda row: (
                0 if row["placement_scope"] == "country" else 1,
                row.get("event") or "",
                row.get("canonical_title") or "",
            )
        )
        payload["events"] = payload["events"][:limit]
        payload["products"] = payload["products"][:limit]
        payload["event_count"] = len(event_seen[geo])
        payload["product_count"] = len(product_seen[geo])

    active = [geo for geo in geo_keys if event_seen[geo] or product_seen[geo]]
    return {
        "as_of": start,
        "horizon_end": end,
        "tracked_geos": active,
        "markets": [
            {"geo": geo, **GEO_META[geo]}
            for geo in PLACEMENT_GEOS
        ],
        "placements": placements,
    }
