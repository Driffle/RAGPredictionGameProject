"""Join Google Trends search volume and Wikipedia pageviews onto lookups.

The Events and Products desks search named titles (Marvel's Wolverine, Tokyo
Game Show, …). The Trends desk should show the same queries with:

- Google Trends RSS approximate search traffic when the topic is trending today
- Wikimedia pageviews in the launch / event window (the free historical signal)
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import unquote

from src.calendar_dedupe import calendar_name, is_product_release_window, is_quarter_timeframe
from src.load_data import parse_date
from src.match import normalize_franchise_text
from src.promote import product_role

WINDOW_PAD_DAYS = 14
PRODUCT_PAST_DAYS = 21
PRODUCT_FUTURE_DAYS = 90
EVENT_PAST_DAYS = 7
EVENT_FUTURE_DAYS = 60
WATCHLIST_PRODUCTS = 24
WATCHLIST_EVENTS = 12
PIN_PRODUCTS = 40
PIN_EVENTS = 24
LOOKUP_LIMIT = 80


def wiki_article_from_url(url: str | None) -> str:
    """English Wikipedia article title from a page URL, or empty if unusable."""
    text = (url or "").strip()
    if "/wiki/" not in text:
        return ""
    slug = text.split("/wiki/", 1)[1].split("#", 1)[0].split("?", 1)[0]
    title = unquote(slug).replace("_", " ").strip()
    if not title or title.lower().endswith(" in video games"):
        return ""
    if title.startswith("List of "):
        return ""
    return title


def _clamp_window(center: date | None, as_of: date, *, pad: int = WINDOW_PAD_DAYS) -> tuple[str, str]:
    if center is None:
        return "", ""
    start = center - timedelta(days=pad)
    end = center + timedelta(days=pad)
    return start.isoformat(), end.isoformat()


def _event_dates(row: dict) -> tuple[date | None, date | None]:
    start = parse_date(row.get("start_date") or row.get("runtime_start") or row.get("start"))
    end = parse_date(row.get("end_date") or row.get("runtime_end") or row.get("end")) or start
    return start, end


def _product_release(row: dict) -> date | None:
    return parse_date(row.get("release_date") or row.get("release_start"))


def _queries_for_name(name: str) -> list[str]:
    text = (name or "").strip()
    if not text:
        return []
    queries = [text]
    seen = {text.lower()}
    for word in text.replace("'", " ").replace("’", " ").split():
        cleaned = word.strip(":-/")
        if len(cleaned) < 4:
            continue
        key = cleaned.lower()
        if key in seen or key in {"game", "games", "show", "fest", "the"}:
            continue
        seen.add(key)
        queries.append(cleaned)
    return queries[:6]


def _edition_base(title: str) -> str:
    text = (title or "").lower()
    for sep in (" - ", " – ", " — "):
        if sep in text:
            text = text.split(sep, 1)[0]
    return " ".join(text.split())


def _product_target(row: dict, day: date) -> dict | None:
    title = (row.get("canonical_title") or row.get("product_title") or "").strip()
    if not title or product_role(row) in {"currency", "dlc"}:
        return None
    release = _product_release(row)
    window_start, window_end = _clamp_window(release, day) if release else ("", "")
    return {
        "query": title,
        "kind": "product",
        "window_start": window_start,
        "window_end": window_end,
        "wiki_article": wiki_article_from_url(row.get("wikipedia_url")) or title,
        "queries": _queries_for_name(title),
        "release_date": release.isoformat() if release else "",
    }


def _event_target(row: dict, day: date) -> dict | None:
    if is_quarter_timeframe(row) or is_product_release_window(row):
        return None
    name = calendar_name(row)
    if not name:
        return None
    start, end = _event_dates(row)
    if start is None:
        return None
    window_start, window_end = start.isoformat(), (end or start).isoformat()
    if end and (end - start).days < WINDOW_PAD_DAYS:
        padded_start, padded_end = _clamp_window(start, day)
        window_start = min(padded_start, start.isoformat())
        window_end = max(padded_end, (end or start).isoformat())
    return {
        "query": name,
        "kind": "event",
        "window_start": window_start,
        "window_end": window_end,
        "wiki_article": wiki_article_from_url(row.get("wikipedia_url")) or name,
        "queries": _queries_for_name(name),
        "release_date": start.isoformat(),
    }


def lookup_targets(
    catalog: list[dict],
    events: list[dict],
    *,
    as_of: date | None = None,
    pin_products: list[dict] | None = None,
    pin_events: list[dict] | None = None,
) -> list[dict]:
    """Product and event search terms from the live desks, with launch windows first."""
    day = as_of or date.today()
    product_lo = day - timedelta(days=PRODUCT_PAST_DAYS)
    product_hi = day + timedelta(days=PRODUCT_FUTURE_DAYS)
    event_lo = day - timedelta(days=EVENT_PAST_DAYS)
    event_hi = day + timedelta(days=EVENT_FUTURE_DAYS)

    products: list[tuple[int, int, dict]] = []
    seen_titles: set[str] = set()
    for row in catalog:
        item = _product_target(row, day)
        if not item:
            continue
        title_key = item["query"].lower()
        if title_key in seen_titles:
            continue
        release = _product_release(row)
        if release is None or release < product_lo or release > product_hi:
            continue
        seen_titles.add(title_key)
        announced = (row.get("product_type") or "").lower() == "announced" or bool(row.get("wikipedia_url"))
        products.append(
            (
                0 if announced else 1,
                abs((release - day).days),
                item,
            )
        )
    products.sort(key=lambda item: (item[0], item[1]))

    chosen_products: list[dict] = []
    seen_editions: set[str] = set()
    for _, _, item in products:
        base = _edition_base(item["query"])
        if base in seen_editions:
            continue
        seen_editions.add(base)
        chosen_products.append(item)
        if len(chosen_products) >= WATCHLIST_PRODUCTS:
            break

    event_rows: list[tuple[int, dict]] = []
    seen_events: set[str] = set()
    for row in events:
        item = _event_target(row, day)
        if not item:
            continue
        name_key = item["query"].lower()
        if name_key in seen_events:
            continue
        start, end = _event_dates(row)
        if start is None or end < event_lo or start > event_hi:
            continue
        seen_events.add(name_key)
        event_rows.append((abs((start - day).days), item))
    event_rows.sort(key=lambda item: item[0])

    merged: list[dict] = []
    seen_keys: set[str] = set()

    def take(item: dict | None, *, cap: int | None = None) -> None:
        if not item:
            return
        key = f"{item['kind']}:{item['query'].lower()}"
        if key in seen_keys:
            return
        if cap is not None and sum(1 for row in merged if row["kind"] == item["kind"]) >= cap:
            return
        seen_keys.add(key)
        merged.append(item)

    for row in pin_products or []:
        take(_product_target(row, day), cap=PIN_PRODUCTS)
    for row in pin_events or []:
        take(_event_target(row, day), cap=PIN_EVENTS)
    for item in chosen_products:
        take(item)
    for _, item in event_rows[:WATCHLIST_EVENTS]:
        take(item)
    return merged[:LOOKUP_LIMIT]


def watchlist_for_lookups(
    catalog: list[dict],
    events: list[dict],
    *,
    as_of: date | None = None,
    pin_products: list[dict] | None = None,
    pin_events: list[dict] | None = None,
) -> tuple[dict[str, list[str]], dict[str, tuple[date, date]]]:
    """Wikipedia article → franchise queries, plus preferred pageview windows."""
    extra: dict[str, list[str]] = {}
    windows: dict[str, tuple[date, date]] = {}
    for target in lookup_targets(
        catalog,
        events,
        as_of=as_of,
        pin_products=pin_products,
        pin_events=pin_events,
    ):
        article = target["wiki_article"]
        extra[article] = target["queries"]
        start = parse_date(target.get("window_start"))
        end = parse_date(target.get("window_end"))
        if start and end:
            windows[article] = (start, end)
    return extra, windows


def _series_window_views(series: list, start: str, end: str) -> int:
    total = 0
    matched = 0
    lo = (start or "")[:10]
    hi = (end or "")[:10]
    for point in series or []:
        if not point:
            continue
        stamp, views = point[0], int(point[1] or 0)
        day = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}" if len(stamp) >= 8 and stamp[4] != "-" else stamp[:10]
        if lo and hi and (day < lo or day > hi):
            continue
        total += views
        matched += 1
    if matched == 0:
        return sum(int(point[1] or 0) for point in (series or []) if point)
    return total


_YEAR = re.compile(r"\b20\d{2}\b")


def _name_hit(search: str, name: str) -> bool:
    a = normalize_franchise_text(search)
    b = normalize_franchise_text(name)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(b) >= 8 and b in a:
        return True
    if len(a) >= 8 and a in b:
        return True
    b_core = " ".join(_YEAR.sub(" ", b).split())
    a_core = " ".join(_YEAR.sub(" ", a).split())
    if len(b_core) >= 8 and b_core in a_core:
        return True
    tokens = [word for word in b_core.split() if len(word) >= 4]
    return len(tokens) >= 2 and all(token in a for token in tokens)


def _blank(target: dict) -> dict:
    return {
        "query": target["query"],
        "kind": target["kind"],
        "window_start": target.get("window_start") or "",
        "window_end": target.get("window_end") or "",
        "google_searches": 0,
        "google_label": "",
        "google_geos": [],
        "google_topics": [],
        "wiki_article": target.get("wiki_article") or "",
        "wiki_views": 0,
        "wiki_window_views": 0,
        "wiki_baseline": 0,
        "spike_ratio": 0.0,
        "wiki_as_of": "",
        "searches": 0,
        "search_source": "",
    }


def _attach_google(row: dict, trend: dict) -> None:
    traffic = int(trend.get("traffic") or 0)
    title = (trend.get("title") or "").strip()
    geo = (trend.get("geo") or "").strip()
    if title and title not in row["google_topics"]:
        row["google_topics"].append(title)
    if geo and geo not in row["google_geos"]:
        row["google_geos"].append(geo)
    if traffic >= row["google_searches"]:
        row["google_searches"] = traffic
        row["google_label"] = trend.get("traffic_label") or (f"{traffic:,}+" if traffic else "")


def _attach_wiki(row: dict, wiki: dict) -> None:
    views = int(wiki.get("views") or 0)
    window_views = _series_window_views(
        wiki.get("series") or [],
        row.get("window_start") or "",
        row.get("window_end") or "",
    ) or int(wiki.get("window_views") or 0)
    if views < row["wiki_views"] and window_views <= row["wiki_window_views"]:
        return
    row["wiki_article"] = wiki.get("article") or row["wiki_article"]
    row["wiki_views"] = views
    row["wiki_window_views"] = window_views
    row["wiki_baseline"] = int(wiki.get("baseline") or 0)
    row["spike_ratio"] = float(wiki.get("spike_ratio") or 0)
    row["wiki_as_of"] = wiki.get("as_of") or ""


def _with_search_count(row: dict) -> dict:
    google = int(row.get("google_searches") or 0)
    wiki = int(row.get("wiki_window_views") or 0) or int(row.get("wiki_views") or 0)
    if google:
        row["searches"] = google
        row["search_source"] = "google_trends"
    elif wiki:
        row["searches"] = wiki
        row["search_source"] = "wikipedia"
    else:
        row["searches"] = 0
        row["search_source"] = ""
    return row


def build_lookup_interest(
    *,
    google: list[dict],
    wiki: list[dict],
    catalog: list[dict],
    events: list[dict],
    as_of: date | None = None,
    pin_products: list[dict] | None = None,
    pin_events: list[dict] | None = None,
) -> list[dict]:
    """One row per product/event search term with search and view counts."""
    targets = lookup_targets(
        catalog,
        events,
        as_of=as_of,
        pin_products=pin_products,
        pin_events=pin_events,
    )
    rows = {f"{item['kind']}:{item['query'].lower()}": _blank(item) for item in targets}
    by_article = {
        normalize_franchise_text(item["wiki_article"]): f"{item['kind']}:{item['query'].lower()}"
        for item in targets
        if item.get("wiki_article")
    }

    for trend in google:
        title = trend.get("title") or ""
        for row in rows.values():
            if _name_hit(title, row["query"]):
                _attach_google(row, trend)

    for article_row in wiki:
        article = article_row.get("article") or ""
        key = by_article.get(normalize_franchise_text(article))
        if key and key in rows:
            _attach_wiki(rows[key], article_row)
            continue
        for row in rows.values():
            if _name_hit(article, row["query"]) or _name_hit(article, row.get("wiki_article") or ""):
                _attach_wiki(row, article_row)

    ordered = [_with_search_count(row) for row in rows.values()]
    ordered.sort(
        key=lambda row: (
            -(row["searches"] or 0),
            -(row["google_searches"] or 0),
            -(row["wiki_window_views"] or row["wiki_views"] or 0),
            row.get("window_start") or "9999",
            row["query"].lower(),
        )
    )
    return ordered[:LOOKUP_LIMIT]


def fill_missing_lookup_wiki(
    bundle: dict,
    catalog: list[dict],
    events: list[dict],
    *,
    as_of: date | None = None,
    pin_products: list[dict] | None = None,
    pin_events: list[dict] | None = None,
) -> dict:
    """Fetch Wikipedia pageviews for lookup titles missing from a cached bundle."""
    from src.trends import fetch_wiki_pageviews

    extra, windows = watchlist_for_lookups(
        catalog,
        events,
        as_of=as_of,
        pin_products=pin_products,
        pin_events=pin_events,
    )
    have = {normalize_franchise_text(row.get("article")) for row in bundle.get("wikipedia") or []}
    missing = {article: queries for article, queries in extra.items() if normalize_franchise_text(article) not in have}
    if not missing:
        return bundle
    fetched = fetch_wiki_pageviews(
        as_of=as_of,
        days=14,
        extra_watchlist=missing,
        include_default=False,
        windows=windows,
    )
    return {**bundle, "wikipedia": list(bundle.get("wikipedia") or []) + fetched}
