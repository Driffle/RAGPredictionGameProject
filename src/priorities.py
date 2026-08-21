"""Rank today's marketing priorities from trends + equivalent-event windows."""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

from src.documents import keyword_retrieve
from src.match import normalize_franchise_text
from src.paths import DAILY_DIR
from src.promote import (
    edition_year,
    plans_active_on,
    product_role,
    select_hero_products,
)

# Map free-text trend / news language onto catalog franchise queries.
TREND_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"spider[-\s]?man|spiderman|miles morales", re.I), ["spider-man", "spiderman", "miles morales"]),
    (re.compile(r"\bbatman\b|arkham", re.I), ["batman", "arkham"]),
    (re.compile(r"\bsuperman\b", re.I), ["superman"]),
    (re.compile(r"star wars|andor|mandalorian", re.I), ["star wars"]),
    (re.compile(r"\bmarvel\b", re.I), ["marvel", "spider-man", "avengers"]),
    (re.compile(r"\bminecraft\b", re.I), ["minecraft"]),
    (re.compile(r"\bfortnite\b", re.I), ["fortnite"]),
    (re.compile(r"gta\s*vi?|grand theft auto", re.I), ["grand theft auto", "gta"]),
    (re.compile(r"call of duty|\bcod\b|warzone|modern warfare", re.I), ["call of duty", "modern warfare"]),
    (re.compile(r"ea sports fc|\bfifa\b", re.I), ["ea sports fc", "fifa"]),
    (re.compile(r"\bmadden(?:\s+nfl)?\b", re.I), ["madden nfl"]),
    (re.compile(r"\bnba\s*2k\b", re.I), ["nba 2k"]),
    (re.compile(r"\bpga tour\b|ea sports pga", re.I), ["pga tour"]),
    (re.compile(r"\bf1\s*(?:20\d{2}|\d{2})\b", re.I), ["f1"]),
    (re.compile(r"\btopspin\b|ao tennis|matchpoint(?:\s*-\s*tennis)?", re.I), ["topspin", "ao tennis"]),
    (re.compile(r"tour de france|pro cycling manager", re.I), ["tour de france", "pro cycling manager"]),
    (re.compile(r"last of us", re.I), ["the last of us"]),
    (re.compile(r"god of war", re.I), ["god of war"]),
    (re.compile(r"resident evil|\bbiohazard\b", re.I), ["resident evil"]),
    (re.compile(r"street fighter", re.I), ["street fighter"]),
    (re.compile(r"\bzelda\b|tears of the kingdom", re.I), ["zelda", "legend of zelda"]),
    (re.compile(r"\bmario\b", re.I), ["mario"]),
    (re.compile(r"pok[eé]mon", re.I), ["pokemon", "pokémon"]),
    (re.compile(r"\bsonic\b", re.I), ["sonic"]),
    (re.compile(r"\bfallout\b", re.I), ["fallout"]),
    (re.compile(r"cyberpunk|edgerunners", re.I), ["cyberpunk"]),
    (re.compile(r"elden ring", re.I), ["elden ring"]),
    (re.compile(r"counter-?strike|\bcs2\b", re.I), ["counter-strike"]),
    (re.compile(r"league of legends|\blol worlds\b", re.I), ["league of legends"]),
    (re.compile(r"\bvalorant\b", re.I), ["valorant"]),
    (re.compile(r"helldivers", re.I), ["helldivers"]),
    (re.compile(r"assassin'?s creed", re.I), ["assassin's creed", "assassins creed"]),
    (re.compile(r"ghost of tsushima", re.I), ["ghost of tsushima"]),
    (re.compile(r"\bhorizon\b zero|aloy", re.I), ["horizon zero dawn"]),
    (re.compile(r"death stranding", re.I), ["death stranding"]),
    (re.compile(r"among us", re.I), ["among us"]),
    (re.compile(r"rocket league", re.I), ["rocket league"]),
    (re.compile(r"warcraft|world of warcraft|\bwow\b", re.I), ["warcraft", "world of warcraft"]),
    (re.compile(r"\bdiablo\b", re.I), ["diablo"]),
    (re.compile(r"\boverwatch\b", re.I), ["overwatch"]),
    (re.compile(r"\bzelda\b", re.I), ["zelda"]),
]


def queries_from_text(text: str) -> list[str]:
    """Map a trend headline (and optional news) onto catalog franchise queries.

    Only known IP/sport patterns count — raw news copy is too noisy to tokenize.
    """
    queries: list[str] = []
    seen: set[str] = set()
    blob = text or ""
    for pattern, mapped in TREND_PATTERNS:
        if pattern.search(blob):
            for query in mapped:
                if query not in seen:
                    seen.add(query)
                    queries.append(query)
    return queries


def _traffic_score(traffic: int) -> float:
    if traffic <= 0:
        return 8.0
    return min(40.0, 8.0 + math.log10(traffic) * 10.0)


def match_google_trends(catalog: list[dict], google_rows: list[dict]) -> list[dict]:
    """Match only the search term itself, never incidental linked-news text."""
    hits: list[dict] = []
    for trend in google_rows:
        queries = queries_from_text(trend.get("title") or "")
        if not queries:
            continue
        products = select_hero_products(catalog, queries)
        if not products:
            continue
        hits.append({"trend": trend, "queries": queries, "products": products})
    return hits


def _dataset_names(rows: list[dict], fields: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    for row in rows:
        for field in fields:
            value = normalize_franchise_text(row.get(field))
            if len(value) >= 4:
                names.add(value)
    return names


def _named_dataset_match(title: str, names: set[str]) -> bool:
    """Match exact dataset names or multi-word names embedded in a search term."""
    normalized = normalize_franchise_text(title)
    if not normalized:
        return False
    if normalized in names:
        return True
    words = normalized.split()
    # Avoid treating generic one-word product names as evidence that unrelated
    # news is gaming-related. Explicit one-word franchises are handled by
    # TREND_PATTERNS and verified against the catalog below.
    for size in range(2, min(8, len(words)) + 1):
        for start in range(len(words) - size + 1):
            if " ".join(words[start : start + size]) in names:
                return True
    return False


def filter_trend_bundle(
    catalog: list[dict],
    events: list[dict],
    bundle: dict,
) -> dict:
    """Keep only trend rows tied to a product or event dataset term.

    Google RSS news remains useful as context after a term is accepted, but it
    never participates in acceptance. Wikipedia rows must resolve to a catalog
    product (or directly name a registered event).
    """
    product_names = _dataset_names(catalog, ("canonical_title", "product_title"))
    event_names = _dataset_names(
        events,
        ("event", "name", "ip_adaptation", "related_game"),
    )

    filtered_google: list[dict] = []
    for row in bundle.get("google_trends") or []:
        title = row.get("title") or ""
        mapped = match_google_trends(catalog, [row])
        if mapped or _named_dataset_match(title, product_names | event_names):
            filtered_google.append(row)

    filtered_wiki: list[dict] = []
    for row in bundle.get("wikipedia") or []:
        products = select_hero_products(catalog, row.get("queries") or [])
        if products or _named_dataset_match(row.get("article") or "", event_names):
            filtered_wiki.append(row)

    return {
        **bundle,
        "google_trends": filtered_google,
        "wikipedia": filtered_wiki,
        "filter": {
            "scope": "product_and_event_datasets",
            "google_kept": len(filtered_google),
            "google_removed": len(bundle.get("google_trends") or []) - len(filtered_google),
            "wikipedia_kept": len(filtered_wiki),
            "wikipedia_removed": len(bundle.get("wikipedia") or []) - len(filtered_wiki),
        },
    }


def match_wiki_spikes(catalog: list[dict], wiki_rows: list[dict], *, min_ratio: float = 1.25) -> list[dict]:
    hits: list[dict] = []
    for row in wiki_rows:
        if row.get("spike_ratio", 1) < min_ratio:
            continue
        products = select_hero_products(catalog, row.get("queries") or [])
        if not products:
            continue
        hits.append({"wiki": row, "products": products})
    return hits


def _reason_trend(trend: dict) -> str:
    news = (trend.get("news") or [None])[0]
    traffic = trend.get("traffic_label") or trend.get("traffic")
    geo = trend.get("geo")
    extra = f" Related coverage: {news}." if news else ""
    return (
        f"Google Trends ({geo}) lists “{trend.get('title')}” "
        f"({traffic} searches). Highlight equivalent catalog games today.{extra}"
    )


def _reason_wiki(row: dict) -> str:
    return (
        f"Wikipedia interest in “{row['article']}” is {row['spike_ratio']}× "
        f"the recent baseline ({row['views']:,} vs {row['baseline']:,} daily views, as of {row['as_of']})."
    )


def _reason_event(plan: dict) -> str:
    return plan.get("strategy_summary") or (
        f"Inside the equivalent-event window for {plan.get('event')} "
        f"({plan.get('event_start')} to {plan.get('event_end')})."
    )


def rank_daily_priorities(
    catalog: list[dict],
    plans: list[dict],
    bundle: dict,
    *,
    on: date | None = None,
    limit: int = 15,
) -> list[dict]:
    """Top SKUs to merchandise today: live trends first, then event windows."""
    day = on or date.today()
    combined: dict[str, dict] = {}

    ROLE_WEIGHT = {"game": 1.0, "dlc": 0.5, "currency": 0.3}

    def bucket(product: dict) -> dict:
        title = product.get("canonical_title") or product.get("product_title") or ""
        item = combined.get(title)
        if item is None:
            role = product_role(product)
            item = {
                "canonical_title": title,
                "product_id": product.get("product_id") or "",
                "product_sku": product.get("product_sku") or "",
                "platform": product.get("platform") or "",
                "role": role,
                "edition_year": edition_year(title, product.get("release_date")),
                "score": 0.0,
                "sources": [],
                "reasons": [],
                "tactics": [],
                "queries": [],
            }
            combined[title] = item
        return item

    for hit in match_google_trends(catalog, bundle.get("google_trends") or []):
        trend = hit["trend"]
        points = _traffic_score(int(trend.get("traffic") or 0))
        for product in hit["products"]:
            item = bucket(product)
            item["score"] += points * ROLE_WEIGHT.get(item["role"], 1.0)
            if "google_trends" not in item["sources"]:
                item["sources"].append("google_trends")
            item["reasons"].append(_reason_trend(trend))
            item["tactics"] = [
                "Feature this IP on the storefront homepage for the next 24 hours while search interest is elevated",
                "Reuse the trending headline/movie/news creative rather than generic key-art",
                "Hold current-edition price; attach DLC/currency underneath the hero SKU",
            ]
            item["queries"] = hit["queries"]
            item["trend_title"] = trend.get("title")
            item["trend_geo"] = trend.get("geo")

    for hit in match_wiki_spikes(catalog, bundle.get("wikipedia") or []):
        wiki = hit["wiki"]
        points = min(30.0, (wiki["spike_ratio"] - 1) * 25)
        for product in hit["products"]:
            item = bucket(product)
            item["score"] += points * ROLE_WEIGHT.get(item["role"], 1.0)
            if "wikipedia_pageviews" not in item["sources"]:
                item["sources"].append("wikipedia_pageviews")
            item["reasons"].append(_reason_wiki(wiki))
            if not item["tactics"]:
                item["tactics"] = [
                    "Raise merchandising rank while Wikipedia attention is above baseline",
                    "Pair the game with the related show/movie/IP landing module",
                ]
            item.setdefault("wiki_article", wiki["article"])

    for plan in plans_active_on(plans, day):
        if plan.get("role") != "game":
            continue
        title = plan.get("canonical_title") or ""
        product = {
            "canonical_title": title,
            "product_id": plan.get("product_id"),
            "product_sku": plan.get("product_sku"),
            "platform": plan.get("platform"),
            "product_type": plan.get("product_type") or "game",
            "product_title": plan.get("product_title") or title,
        }
        item = bucket(product)
        bonus = 18.0
        if item["sources"]:
            bonus += 12.0  # trend + scheduled event in the same day
        item["score"] += bonus
        if "event_window" not in item["sources"]:
            item["sources"].append("event_window")
        item["reasons"].append(_reason_event(plan))
        item["event"] = plan.get("event")
        item["promo_start"] = plan.get("promo_start")
        item["promo_end"] = plan.get("promo_end")
        if plan.get("phases") and not item["tactics"]:
            live = next((phase for phase in plan["phases"] if phase["name"] == "live"), plan["phases"][0])
            item["tactics"] = list(live.get("tactics") or [])

    ranked = sorted(
        combined.values(),
        key=lambda item: (
            -item["score"],
            0 if item["role"] == "game" else 1,
            -(item.get("edition_year") or 0),
            item["canonical_title"],
        ),
    )
    for index, item in enumerate(ranked[:limit], start=1):
        item["rank"] = index
        item["as_of"] = day.isoformat()
        item["reasons"] = item["reasons"][:4]
    return ranked[:limit]


def priority_document(item: dict) -> dict:
    text = "\n".join(
        [
            f"Daily marketing priority #{item.get('rank')}: {item.get('canonical_title')}",
            f"Date: {item.get('as_of')}",
            f"Sources: {', '.join(item.get('sources') or [])}",
            f"Score: {item.get('score'):.1f}",
            *(item.get("reasons") or []),
            "Tactics: " + "; ".join(item.get("tactics") or []),
        ]
    )
    return {
        "id": f"priority:{item.get('as_of')}:{item.get('product_id') or item.get('canonical_title')}",
        "kind": "daily_priority",
        "title": f"{item.get('canonical_title')} — {item.get('as_of')}",
        "text": text,
        "metadata": {
            "as_of": item.get("as_of"),
            "sources": item.get("sources"),
            "rank": item.get("rank"),
        },
    }


def retrieve_priorities(items: list[dict], query: str, *, limit: int = 8) -> list[tuple[float, dict]]:
    documents = [priority_document(item) for item in items]
    hits = keyword_retrieve(documents, query, limit=limit)
    by_id = {priority_document(item)["id"]: item for item in items}
    return [(score, by_id[doc["id"]]) for score, doc in hits if doc["id"] in by_id]


def daily_dir(day: date | None = None) -> Path:
    stamp = (day or date.today()).isoformat()
    path = DAILY_DIR / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_is_fresh(day: date | None = None, *, max_age_hours: int = 18) -> bool:
    path = daily_dir(day) / "trends.json"
    if not path.exists():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age < max_age_hours * 3600


def save_daily_brief(bundle: dict, priorities: list[dict], day: date | None = None) -> Path:
    folder = daily_dir(day)
    (folder / "trends.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    (folder / "priorities.json").write_text(json.dumps(priorities, indent=2), encoding="utf-8")
    if priorities:
        fieldnames = [
            "rank",
            "as_of",
            "canonical_title",
            "role",
            "platform",
            "score",
            "sources",
            "trend_title",
            "event",
            "reasons",
        ]
        with (folder / "priorities.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for item in priorities:
                writer.writerow(
                    {
                        **item,
                        "sources": "|".join(item.get("sources") or []),
                        "reasons": " || ".join(item.get("reasons") or []),
                    }
                )
    lines = [
        f"# Daily marketing brief — {(day or date.today()).isoformat()}",
        "",
        "Top catalog SKUs to highlight today, from Google Trends, Wikipedia attention, and equivalent-event windows.",
        "",
    ]
    for item in priorities:
        lines.append(f"## {item['rank']}. {item['canonical_title']}")
        lines.append(f"Sources: {', '.join(item.get('sources') or [])} · score {item['score']:.1f}")
        for reason in item.get("reasons") or []:
            lines.append(f"- {reason}")
        lines.append("")
    (folder / "brief.md").write_text("\n".join(lines), encoding="utf-8")
    return folder


def load_cached_brief(day: date | None = None) -> tuple[dict, list[dict]] | None:
    folder = daily_dir(day)
    trends_path = folder / "trends.json"
    prio_path = folder / "priorities.json"
    if not trends_path.exists() or not prio_path.exists():
        return None
    bundle = json.loads(trends_path.read_text(encoding="utf-8"))
    priorities = json.loads(prio_path.read_text(encoding="utf-8"))
    return bundle, priorities
