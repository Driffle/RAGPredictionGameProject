"""Daily Wikipedia / Wikidata checks for game and event announcements."""

from __future__ import annotations

import re
import time
from datetime import date, datetime

from src.http import wikipedia_api, wikidata_sparql

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
EVENTISH = re.compile(
    r"award|expo|show|fest|con\b|championship|direct|showcase|cup|tournament|"
    r"week|sale|conference|summit|festival|invitational|worlds|major|gamescom|"
    r"comic-con|blizzcon|pax |gdc|wwdc",
    re.I,
)
SKIP_EVENT = re.compile(r"layoff|shut down|closure|died|death|cancelled the", re.I)
HORIZON_START = date(2026, 1, 1)
HORIZON_END = date(2030, 12, 31)


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if len(text) >= 10:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    for fmt in ("%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _clean_cell(text: str) -> str:
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S | re.I)
    text = re.sub(r'^(?:colspan|rowspan)="?\d+"?\s*\|?\s*', "", text.strip(), flags=re.I)
    text = re.sub(r"\{\{[^}]+\}\}", " ", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(
        r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
        lambda m: (m.group(2) or m.group(1).split("#", 1)[0]).strip(),
        text,
    )
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip(" |")


def _wiki_title(cell: str) -> str:
    match = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", cell)
    if match:
        title = (match.group(2) or match.group(1).split("#", 1)[0]).strip()
    else:
        title = _clean_cell(cell)
    title = re.sub(r"\s*\((WW|NA|EU|JP|video game|upcoming)\)\s*", "", title, flags=re.I)
    return title.strip()


def _parse_flexible_date(cell: str, year: int) -> date | None:
    dts = re.search(r"\{\{dts\|([^}|]+)", cell, re.I)
    if dts:
        parsed = _iso_date(dts.group(1).strip())
        if parsed:
            return parsed
        cell = dts.group(1)
    cleaned = _clean_cell(cell)
    parsed = _iso_date(cleaned)
    if parsed:
        return parsed
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:\s*,\s*(\d{4}))?",
        cleaned,
        re.I,
    )
    if match:
        month = MONTHS[match.group(1).lower()]
        day = int(match.group(2))
        use_year = int(match.group(3) or year)
        try:
            return date(use_year, month, day)
        except ValueError:
            return date(use_year, month, 1)
    match = re.search(
        r"^(January|February|March|April|May|June|July|August|September|October|November|December)$",
        cleaned,
        re.I,
    )
    if match:
        return date(year, MONTHS[match.group(1).lower()], 1)
    quarter = re.search(r"\bQ([1-4])\b", cleaned, re.I)
    if quarter:
        return date(year, 1 + (int(quarter.group(1)) - 1) * 3, 1)
    if re.search(r"\bTBA\b|\bTBD\b", cleaned, re.I):
        return date(year, 12, 31)
    return None


def _table_rows(wikitext: str) -> list[list[str]]:
    rows: list[list[str]] = []
    current: list[str] = []
    in_table = False
    for line in wikitext.splitlines():
        if line.startswith("{|"):
            in_table = True
            current = []
            continue
        if not in_table:
            continue
        if line.startswith("|}"):
            if current:
                rows.append(current)
            in_table = False
            current = []
            continue
        if line.startswith("|-"):
            if current:
                rows.append(current)
            current = []
            continue
        if line.startswith("!"):
            continue
        if line.startswith("|"):
            payload = line[1:]
            payload = re.sub(r"^(?:colspan|rowspan)=\"?\d+\"?\s*\|?\s*", "", payload, flags=re.I)
            parts = [part.strip() for part in payload.split("||")]
            current.extend(parts)
    return rows


def wikipedia_wikitext(page: str) -> str:
    payload = wikipedia_api(
        {"action": "parse", "page": page, "prop": "wikitext", "format": "json", "redirects": "1"}
    )
    return payload.get("parse", {}).get("wikitext", {}).get("*") or ""


def fetch_wikipedia_games(years: tuple[int, ...] = (2026, 2027, 2028, 2029, 2030)) -> list[dict]:
    games: list[dict] = []
    seen: set[str] = set()
    for year in years:
        for page in (f"List_of_video_games_released_in_{year}", f"{year}_in_video_games"):
            try:
                text = wikipedia_wikitext(page)
            except Exception:
                text = ""
            time.sleep(0.35)
            if not text or '"missing"' in text[:200]:
                continue
            for row in _table_rows(text):
                if len(row) < 2:
                    continue
                date_cell, title_cell = row[0], row[1]
                title = _wiki_title(title_cell)
                if not title or len(title) < 2 or title.lower() in {"title", "event", "date"}:
                    continue
                cleaned_date = _clean_cell(date_cell)
                tba = bool(re.search(r"\bTBA\b|\bTBD\b|to be announced|unannounced", cleaned_date, re.I))
                release = _parse_flexible_date(date_cell, year) or _parse_flexible_date(title_cell, year)
                if release is None:
                    # Keep announced titles without a firm day as year planning windows.
                    release = date(year, 12, 31)
                    tba = True
                if release.year != year and abs(release.year - year) > 1:
                    continue
                key = f"{title.lower()}|{release.isoformat()}"
                if key in seen:
                    continue
                seen.add(key)
                platforms = _clean_cell(row[2]) if len(row) > 2 else ""
                genre = _clean_cell(row[4]) if len(row) > 4 else (_clean_cell(row[3]) if len(row) > 3 else "")
                developer = _clean_cell(row[5]) if len(row) > 5 else ""
                publisher = _clean_cell(row[6]) if len(row) > 6 else developer
                slug = re.sub(r"\s+", "_", title)
                if tba:
                    confirmation = "announced TBA"
                elif release <= date.today():
                    confirmation = "confirmed"
                else:
                    confirmation = "announced"
                games.append(
                    {
                        "canonical_title": title,
                        "product_title": title,
                        "release_date": release.isoformat(),
                        "platforms": platforms,
                        "platform": platforms.split(",")[0].strip() if platforms else "Multi",
                        "genre": genre,
                        "developer": developer,
                        "publisher": publisher,
                        "wikipedia_url": f"https://en.wikipedia.org/wiki/{slug.replace(' ', '_')}",
                        "source": f"wikipedia:{page}",
                        "confirmation": confirmation,
                        "product_type": "announced",
                        "horizon": HORIZON_START <= release <= HORIZON_END,
                    }
                )
    return games


EVENT_YEARS = (2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030)


def fetch_wikipedia_events(years: tuple[int, ...] = EVENT_YEARS) -> list[dict]:
    events: list[dict] = []
    for year in years:
        try:
            text = wikipedia_wikitext(f"{year}_in_video_games")
        except Exception:
            text = ""
        time.sleep(0.35)
        if not text:
            continue
        lower = text.lower()
        start = lower.find("major events")
        chunk = text[start : start + 25000] if start >= 0 else text[:20000]
        current_month = 1
        for row in _table_rows(chunk):
            if not row:
                continue
            joined = " ".join(row)
            month_hit = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)",
                joined,
                re.I,
            )
            if month_hit and len(row[0]) < 20:
                current_month = MONTHS[month_hit.group(1).lower()]
            day_cell = row[1] if len(row) > 2 else row[0]
            event_cell = row[-1]
            if SKIP_EVENT.search(event_cell) or not EVENTISH.search(event_cell):
                continue
            days = re.findall(r"\d{1,2}", day_cell)
            start_day = int(days[0]) if days else 1
            end_day = int(days[-1]) if days else start_day
            try:
                start = date(year, current_month, min(start_day, 28))
                end = date(year, current_month, min(end_day, 28))
            except ValueError:
                continue
            if end < start:
                end = start
            name = _wiki_title(event_cell) or _clean_cell(event_cell)[:80]
            if not name:
                continue
            events.append(
                {
                    "kind": "event",
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "event": name,
                    "category": "Gaming",
                    "related_game": "Multi-platform",
                    "event_type": "Announcement",
                    "status": "Confirmed",
                    "wikipedia_url": f"https://en.wikipedia.org/wiki/{year}_in_video_games",
                    "source": f"wikipedia:{year}_in_video_games",
                    "confirmation": "confirmed",
                    "summary": _clean_cell(event_cell)[:240],
                }
            )
    return events


def fetch_wikipedia_adaptations(years: tuple[int, ...] = EVENT_YEARS) -> list[dict]:
    rows: list[dict] = []
    for year in years:
        try:
            text = wikipedia_wikitext(f"{year}_in_video_games")
        except Exception:
            text = ""
        time.sleep(0.35)
        if not text:
            continue
        idx = text.lower().find("video game-based film")
        chunk = text[idx:] if idx >= 0 else ""
        for row in _table_rows(chunk):
            if len(row) < 4:
                continue
            title = _wiki_title(row[0])
            release = _parse_flexible_date(row[1], year)
            if not title or not release:
                continue
            rows.append(
                {
                    "kind": "adaptation",
                    "start_date": release.isoformat(),
                    "end_date": release.isoformat(),
                    "ip_adaptation": title,
                    "medium": _clean_cell(row[2]) if len(row) > 2 else "Film / TV",
                    "distributor": _clean_cell(row[3]) if len(row) > 3 else "",
                    "related_game": _clean_cell(row[4]) if len(row) > 4 else title,
                    "date_status": "Confirmed",
                    "wikipedia_url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "source": f"wikipedia:{year}_in_video_games",
                    "confirmation": "confirmed",
                }
            )
    return rows


def fetch_wikidata_games(years: tuple[int, ...] = (2026, 2027, 2028, 2029, 2030)) -> list[dict]:
    games: list[dict] = []
    seen: set[str] = set()
    for year in years:
        query = f"""
        SELECT ?item ?itemLabel ?date ?wiki WHERE {{
          ?item wdt:P31/wdt:P279* wd:Q7889 .
          ?item wdt:P577 ?date .
          FILTER(YEAR(?date) = {year})
          OPTIONAL {{ ?wiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 500
        """
        try:
            bindings = wikidata_sparql(query, timeout=75)
        except Exception:
            bindings = []
        time.sleep(0.4)
        for row in bindings:
            label = (row.get("itemLabel") or {}).get("value") or ""
            if not label or re.fullmatch(r"Q\d+", label):
                continue
            stamp = ((row.get("date") or {}).get("value") or "")[:10]
            parsed = _iso_date(stamp)
            if not parsed:
                continue
            key = f"{label.lower()}|{parsed.isoformat()}"
            if key in seen:
                continue
            seen.add(key)
            wiki = (row.get("wiki") or {}).get("value") or ""
            qid = ((row.get("item") or {}).get("value") or "").rsplit("/", 1)[-1]
            confirmation = "confirmed" if parsed <= date.today() else "announced"
            games.append(
                {
                    "canonical_title": label,
                    "product_title": label,
                    "release_date": parsed.isoformat(),
                    "platforms": "",
                    "platform": "Multi",
                    "genre": "",
                    "developer": "",
                    "publisher": "",
                    "wikipedia_url": wiki,
                    "wikidata_id": qid,
                    "source": "wikidata",
                    "confirmation": confirmation,
                    "product_type": "announced",
                    "horizon": HORIZON_START <= parsed <= HORIZON_END,
                }
            )
    return games


def fetch_wikidata_adaptations(
    years: tuple[int, ...] = EVENT_YEARS,
) -> list[dict]:
    """Cross-media works directly based on video games, across media types."""
    adaptations: list[dict] = []
    seen: set[str] = set()
    for year in years:
        query = f"""
        SELECT DISTINCT ?item ?itemLabel ?date ?typeLabel ?sourceLabel ?distributorLabel ?wiki WHERE {{
          ?item wdt:P577 ?date ;
                wdt:P144 ?source ;
                wdt:P31 ?type .
          ?source wdt:P31/wdt:P279* wd:Q7889 .
          FILTER(YEAR(?date) = {year})
          OPTIONAL {{ ?item wdt:P750 ?distributor . }}
          OPTIONAL {{ ?wiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 500
        """
        try:
            bindings = wikidata_sparql(query, timeout=75)
        except Exception:
            bindings = []
        time.sleep(0.4)
        for row in bindings:
            title = (row.get("itemLabel") or {}).get("value") or ""
            related = (row.get("sourceLabel") or {}).get("value") or ""
            stamp = ((row.get("date") or {}).get("value") or "")[:10]
            parsed = _iso_date(stamp)
            if not title or not related or not parsed or re.fullmatch(r"Q\d+", title):
                continue
            key = f"{title.lower()}|{parsed.isoformat()}"
            if key in seen:
                continue
            seen.add(key)
            qid = ((row.get("item") or {}).get("value") or "").rsplit("/", 1)[-1]
            adaptations.append(
                {
                    "kind": "adaptation",
                    "start_date": parsed.isoformat(),
                    "end_date": parsed.isoformat(),
                    "ip_adaptation": title,
                    "medium": (row.get("typeLabel") or {}).get("value") or "Cross-media release",
                    "distributor": (row.get("distributorLabel") or {}).get("value") or "",
                    "related_game": related,
                    "date_status": "Wikidata release date",
                    "wikipedia_url": (row.get("wiki") or {}).get("value") or "",
                    "wikidata_id": qid,
                    "source": "wikidata:video-game-adaptation",
                    "confirmation": "wikidata release date",
                    "format": (row.get("typeLabel") or {}).get("value") or "",
                    "scope": "unknown",
                }
            )
    return adaptations


def in_horizon(value: str | date | None) -> bool:
    parsed = value if isinstance(value, date) else _iso_date(str(value or ""))
    if not parsed:
        return False
    return HORIZON_START <= parsed <= HORIZON_END
