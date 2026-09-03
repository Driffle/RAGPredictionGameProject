"""Daily search-interest signals from open APIs (no paid keys).

Sources:
- Google Trends daily RSS (https://trends.google.com/trending/rss?geo=XX)
- Wikimedia pageviews for known game / movie IPs
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from statistics import median
from urllib.parse import quote, unquote

from src.http import http_get

HT_NS = {"ht": "https://trends.google.com/trending/rss"}
DEFAULT_GEOS = ("US", "GB", "DE", "JP", "BR", "AU")

# Wikipedia article titles for IPs we can merchandise. Underscores are OK.
WIKI_WATCHLIST = {
    "Spider-Man": ["spider-man", "spiderman", "miles morales"],
    "Marvel's Spider-Man 2": ["spider-man", "spiderman", "miles morales"],
    "Batman": ["batman", "arkham"],
    "Superman": ["superman"],
    "Star Wars": ["star wars"],
    "Minecraft": ["minecraft"],
    "Fortnite": ["fortnite"],
    "Grand Theft Auto": ["grand theft auto", "gta"],
    "Grand Theft Auto VI": ["grand theft auto", "gta"],
    "Call of Duty": ["call of duty", "modern warfare"],
    "EA Sports FC": ["ea sports fc", "fifa"],
    "FIFA": ["fifa", "ea sports fc"],
    "Madden NFL": ["madden nfl"],
    "NBA 2K": ["nba 2k"],
    "The Last of Us": ["the last of us"],
    "The Last of Us (TV series)": ["the last of us"],
    "God of War": ["god of war"],
    "Resident Evil": ["resident evil"],
    "Street Fighter": ["street fighter"],
    "Super Mario": ["mario"],
    "The Legend of Zelda": ["zelda", "legend of zelda"],
    "Pokémon": ["pokemon", "pokémon"],
    "Sonic the Hedgehog": ["sonic"],
    "Fallout": ["fallout"],
    "Fallout (American TV series)": ["fallout"],
    "Cyberpunk 2077": ["cyberpunk"],
    "Elden Ring": ["elden ring"],
    "Counter-Strike 2": ["counter-strike", "counter strike"],
    "League of Legends": ["league of legends"],
    "Valorant": ["valorant"],
    "Helldivers 2": ["helldivers"],
    "Assassin's Creed": ["assassin's creed", "assassins creed"],
    "Ghost of Tsushima": ["ghost of tsushima"],
    "Horizon Zero Dawn": ["horizon zero dawn"],
    "Death Stranding": ["death stranding"],
    "Among Us": ["among us"],
    "Rocket League": ["rocket league"],
    "World of Warcraft": ["warcraft", "world of warcraft"],
    "Diablo": ["diablo"],
    "Overwatch": ["overwatch"],
    "F1 (formula racing)": ["f1"],
    "PGA Tour": ["pga tour"],
    "Marvel's Wolverine": ["wolverine", "marvel's wolverine"],
    "Ghost of Yōtei": ["ghost of yotei", "ghost of tsushima"],
    "Intergalactic: The Heretic Prophet": ["intergalactic"],
    "Resident Evil Requiem": ["resident evil"],
}


def parse_traffic(value: str | None) -> int:
    if not value:
        return 0
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def fetch_google_trends(geos: tuple[str, ...] = DEFAULT_GEOS) -> list[dict]:
    """Daily trending searches from Google's public RSS feed."""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def one_geo(geo: str) -> list[dict]:
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        try:
            xml = http_get(url).decode("utf-8", "replace")
            root = ET.fromstring(xml)
        except Exception:
            return []
        local = []
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            traffic = item.findtext("ht:approx_traffic", default="", namespaces=HT_NS)
            news: list[str] = []
            for news_item in item.findall("ht:news_item", HT_NS):
                headline = (news_item.findtext("ht:news_item_title", default="", namespaces=HT_NS) or "").strip()
                source = (news_item.findtext("ht:news_item_source", default="", namespaces=HT_NS) or "").strip()
                if headline:
                    news.append(f"{headline} ({source})" if source else headline)
            local.append(
                {
                    "source": "google_trends",
                    "geo": geo,
                    "title": title,
                    "traffic": parse_traffic(traffic),
                    "traffic_label": traffic,
                    "published": (item.findtext("pubDate") or "").strip(),
                    "news": news[:3],
                    "blob": " ".join([title, *news[:3]]),
                }
            )
        return local

    with ThreadPoolExecutor(max_workers=6) as pool:
        for fetched in pool.map(one_geo, geos):
            for row in fetched:
                key = (row["geo"], row["title"].lower())
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    rows.sort(key=lambda row: (-row["traffic"], row["geo"], row["title"].lower()))
    return rows


def _wiki_article_path(title: str) -> str:
    cleaned = unquote((title or "").replace(" ", "_"))
    return quote(cleaned, safe=":_()")


def _pageview_range(
    as_of: date,
    days: int,
    window: tuple[date, date] | None,
) -> tuple[date, date]:
    yesterday = as_of - timedelta(days=1)
    if window:
        start, end = window
        end = min(end, yesterday)
        if end < start or (end - start).days < max(3, days - 1):
            start = yesterday - timedelta(days=days)
            end = yesterday
        else:
            start = min(start, end)
        return start, end
    return yesterday - timedelta(days=days), yesterday


def fetch_wiki_pageviews(
    as_of: date | None = None,
    days: int = 10,
    extra_watchlist: dict[str, list[str]] | None = None,
    *,
    include_default: bool = True,
    windows: dict[str, tuple[date, date]] | None = None,
) -> list[dict]:
    """Recent English Wikipedia pageviews for the game/movie watchlist."""
    day = as_of or date.today()
    watchlist: dict[str, list[str]] = dict(WIKI_WATCHLIST) if include_default else {}
    if extra_watchlist:
        watchlist.update(extra_watchlist)

    def one_article(article: str, queries: list[str]) -> dict | None:
        start, end = _pageview_range(day, days, (windows or {}).get(article))
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia/all-access/user/{_wiki_article_path(article)}/"
            f"daily/{start:%Y%m%d}/{end:%Y%m%d}"
        )
        try:
            payload = json.loads(http_get(url).decode("utf-8", "replace"))
        except Exception:
            return None
        series = payload.get("items") or []
        if len(series) < 3:
            return None
        points = [(item["timestamp"][:8], int(item["views"])) for item in series]
        last_day, last_views = points[-1]
        prior = [views for _, views in points[:-1]]
        baseline = median(prior) if prior else last_views
        ratio = last_views / baseline if baseline else 1.0
        return {
            "source": "wikipedia_pageviews",
            "article": article,
            "queries": queries,
            "as_of": f"{last_day[:4]}-{last_day[4:6]}-{last_day[6:8]}",
            "views": last_views,
            "baseline": int(baseline),
            "spike_ratio": round(ratio, 2),
            "series": points,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "window_views": sum(views for _, views in points),
        }

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(one_article, article, queries)
            for article, queries in watchlist.items()
        ]
        for future in as_completed(futures):
            row = future.result()
            if row:
                rows.append(row)
    rows.sort(key=lambda row: (-row["spike_ratio"], -row["views"]))
    return rows


def collect_trend_bundle(
    as_of: date | None = None,
    extra_watchlist: dict[str, list[str]] | None = None,
    windows: dict[str, tuple[date, date]] | None = None,
) -> dict:
    google = fetch_google_trends()
    wiki = fetch_wiki_pageviews(
        as_of=as_of,
        days=14 if extra_watchlist else 10,
        extra_watchlist=extra_watchlist,
        windows=windows,
    )
    return {
        "fetched_on": (as_of or date.today()).isoformat(),
        "google_trends": google,
        "wikipedia": wiki,
    }
