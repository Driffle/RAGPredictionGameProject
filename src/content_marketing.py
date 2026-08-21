"""Content-marketing kits for product × event promo windows.

Builds social keywords/hashtags, posting times, SEO terms, and affiliate-link
templates for short-form pieces across lead-in, live, and afterglow phases.
URLs are store-search templates — replace YOURTAG before publishing.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import quote_plus

from src.match import superhero_universe_for_row
from src.promote import promo_family, product_role
from src.match import superhero_universe_for_row

PLATFORMS = (
    ("tiktok", "TikTok", "18:00–21:00 local"),
    ("instagram", "Instagram Reels", "11:00–13:00 and 19:00–21:00 local"),
    ("youtube_shorts", "YouTube Shorts", "12:00–15:00 and 18:00–21:00 local"),
    ("x", "X / Twitter", "08:00–10:00 and during live sessions"),
)

FAMILY_TAGS = {
    "sports": ["#GameDay", "#WatchAlong", "#SportsGaming", "#PlayAtHome"],
    "esports": ["#Esports", "#GameTok", "#ClipIt", "#ProPlay"],
    "adaptation": ["#GameToScreen", "#MustWatch", "#IPDrop", "#MovieTok"],
    "awards": ["#GOTY", "#GameAwards", "#Nominees", "#AwardsSeason"],
    "commerce": ["#GameDeals", "#Wishlist", "#SteamSale", "#BundleUp"],
    "expo": ["#GamingExpo", "#Showcase", "#HandsOn", "#BoothTour"],
    "default": ["#Gaming", "#GameTok", "#VideoGames", "#PlayNow"],
}

UNIVERSE_TAGS = {
    "marvel": ["#Marvel", "#MCU", "#MarvelGames", "#Avengers"],
    "dc": ["#DC", "#DCU", "#DCComics", "#SuperheroGames"],
}

PHASE_CADENCE = {
    "lead_in": "1 short-form piece per weekday",
    "live": "2–3 short-form pieces per day",
    "afterglow": "1 recap + 1 evergreen CTA",
}

PHASE_HOOK = {
    "lead_in": "countdown teaser",
    "live": "live clip / watch-along",
    "afterglow": "recap + buy CTA",
}


def _words(text: str) -> list[str]:
    return [part for part in re.findall(r"[A-Za-z0-9]+", text or "") if part]


def hashtag(text: str) -> str:
    words = _words(text)
    if not words:
        return ""
    tag = "#" + "".join(word[:1].upper() + word[1:] for word in words)
    return tag[:42]


def _slug_query(text: str) -> str:
    return quote_plus(re.sub(r"\s+", " ", (text or "").strip())[:80])


def _parse_day(value: str | None) -> date | None:
    stamp = (value or "")[:10]
    if len(stamp) < 10:
        return None
    try:
        return date.fromisoformat(stamp)
    except ValueError:
        return None


def seo_keywords(product: str, event: str, family: str, role: str) -> list[str]:
    title = (product or "").strip()
    event_name = (event or "").strip()
    year = ""
    match = re.search(r"\b(20[2-3]\d)\b", f"{title} {event_name}")
    if match:
        year = match.group(1)
    seeds = [
        f"{title} {event_name}".strip(),
        f"buy {title}",
        f"{title} gameplay",
        f"{event_name} watch along" if family == "sports" else f"{event_name} highlights",
        f"{title} DLC" if role == "dlc" else f"{title} bundle",
        f"{title} {year}".strip() if year else f"{title} release",
        f"{event_name} merch",
        f"best {title} deal",
    ]
    universe = superhero_universe_for_row(event_name)
    if universe == "marvel":
        seeds.extend(
            [
                f"Marvel games {event_name}".strip(),
                f"play Marvel before {event_name}".strip(),
                f"{title} MCU",
                f"best Marvel games {year or '2026'}".strip(),
                f"{title} Avengers Doomsday" if "avengers" in event_name.lower() else f"{title} Marvel movie",
            ]
        )
    elif universe == "dc":
        seeds.extend(
            [
                f"DC games {event_name}".strip(),
                f"play DC before {event_name}".strip(),
                f"{title} DCU",
                f"best DC games {year or '2026'}".strip(),
                f"{title} Superman" if "super" in event_name.lower() else f"{title} DC movie",
            ]
        )
    out: list[str] = []
    seen: set[str] = set()
    for raw in seeds:
        key = re.sub(r"\s+", " ", raw).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(re.sub(r"\s+", " ", raw).strip())
    return out[:10]


def social_pack(product: str, event: str, family: str) -> dict:
    product_tag = hashtag(product)
    event_tag = hashtag(event)
    core = [tag for tag in (product_tag, event_tag, "#ad") if tag]
    family_tags = FAMILY_TAGS.get(family) or FAMILY_TAGS["default"]
    universe = superhero_universe_for_row(event)
    universe_tags = UNIVERSE_TAGS.get(universe) or []
    keywords = [product, event, f"{product} {event}", "gameplay", "drop"]
    if universe == "marvel":
        keywords.extend(["Marvel games", "MCU watch along", f"{product} Marvel"])
    elif universe == "dc":
        keywords.extend(["DC games", "DCU watch along", f"{product} DC"])
    packs = {}
    extras = {
        "tiktok": ["#FYP", "#ForYou"] + universe_tags[:2] + family_tags[:2],
        "instagram": ["#Reels", "#InstaGaming"] + universe_tags[:2] + family_tags[:2],
        "youtube_shorts": ["#Shorts", "#YouTubeGaming"] + universe_tags[:2] + family_tags[:2],
        "x": ["#gaming"] + universe_tags[:2] + family_tags[:2],
    }
    for key, label, when in PLATFORMS:
        tags = []
        for tag in core + extras.get(key, []):
            if tag and tag not in tags:
                tags.append(tag)
        packs[key] = {
            "platform": label,
            "hashtags": tags[:8],
            "keywords": [item for item in keywords if item][:5],
            "best_times": when,
        }
    return packs


def affiliate_link(title: str, platform: str) -> dict:
    query = _slug_query(title)
    plat = (platform or "").lower()
    if "steam" in plat or plat in {"pc", "windows"}:
        return {
            "network": "Steam",
            "label": "Steam store search",
            "url": f"https://store.steampowered.com/search/?term={query}",
            "note": "Swap for your Steamworks partner / curator link before posting.",
        }
    if any(token in plat for token in ("playstation", "ps5", "ps4", "psn")):
        return {
            "network": "PlayStation Store",
            "label": "PlayStation Store search",
            "url": f"https://store.playstation.com/search/{query}",
            "note": "Use your PlayStation Stars / partner tagged destination.",
        }
    if "xbox" in plat or "microsoft" in plat:
        return {
            "network": "Xbox / Microsoft Store",
            "label": "Xbox search",
            "url": f"https://www.xbox.com/en-US/search?q={query}",
            "note": "Replace with your Microsoft Store affiliate URL.",
        }
    if "nintendo" in plat or "switch" in plat:
        return {
            "network": "Nintendo eShop",
            "label": "Nintendo search",
            "url": f"https://www.nintendo.com/us/search/#q={query}&p=1&cat=gme",
            "note": "Replace with your Nintendo partner / eShop tracked URL.",
        }
    if "epic" in plat:
        return {
            "network": "Epic Games Store",
            "label": "Epic Games Store search",
            "url": f"https://store.epicgames.com/en-US/browse?q={query}&sortBy=relevancy",
            "note": "Use your Epic Support-A-Creator code in on-screen copy.",
        }
    return {
        "network": "Amazon Associates",
        "label": "Amazon search (insert YOURTAG)",
        "url": f"https://www.amazon.com/s?k={query}&tag=YOURTAG",
        "note": "Replace YOURTAG with the Amazon Associates tracking ID before publishing.",
    }


def _phase_post_day(phase: dict) -> str:
    start = _parse_day(phase.get("start"))
    end = _parse_day(phase.get("end")) or start
    name = phase.get("name") or "live"
    if not start:
        return ""
    if name == "lead_in":
        return start.isoformat()
    if name == "afterglow":
        return start.isoformat()
    if end and end > start:
        mid = start + timedelta(days=max(0, (end - start).days // 2))
        return mid.isoformat()
    return start.isoformat()


def _pieces(plan: dict, social: dict, seo: list[str]) -> list[dict]:
    product = plan.get("canonical_title") or ""
    event = plan.get("event") or ""
    family = plan.get("promo_family") or promo_family(plan)
    role = plan.get("role") or product_role(plan)
    affiliate = affiliate_link(product, plan.get("platform") or "")
    pieces = []
    platforms = list(PLATFORMS)
    phases = list(plan.get("phases") or [])
    if not phases:
        phases = [
            {
                "name": "live",
                "label": "Event runtime",
                "start": plan.get("promo_start") or plan.get("runtime_start") or "",
                "end": plan.get("promo_end") or plan.get("runtime_end") or "",
            }
        ]
    for index, phase in enumerate(phases):
        name = phase.get("name") or "live"
        hook = PHASE_HOOK.get(name, "clip")
        key, label, when = platforms[index % len(platforms)]
        pack = social.get(key) or {}
        title = f"{product} × {event}: {hook}"
        if role == "currency" and name == "live":
            title = f"{product} points pack during {event}"
        elif role == "dlc" and name == "afterglow":
            title = f"{product} add-on after {event}"
        pieces.append(
            {
                "format": label,
                "platform": key,
                "phase": name,
                "phase_label": phase.get("label") or name,
                "title": title,
                "post_on": _phase_post_day(phase),
                "when": f"{phase.get('start') or ''} → {phase.get('end') or ''} · {when}",
                "cadence": PHASE_CADENCE.get(name, PHASE_CADENCE["live"]),
                "hashtags": pack.get("hashtags") or [],
                "seo_keywords": seo[:5],
                "affiliate": affiliate,
            }
        )
    return pieces[:4]


def correlation_from_plan(plan: dict) -> dict | None:
    product = (plan.get("canonical_title") or "").strip()
    event = (plan.get("event") or "").strip()
    if not product or not event:
        return None
    family = plan.get("promo_family") or promo_family(plan)
    role = plan.get("role") or product_role(plan)
    social = social_pack(product, event, family)
    seo = seo_keywords(product, event, family, role)
    schedule = []
    for phase in plan.get("phases") or []:
        name = phase.get("name") or "live"
        schedule.append(
            {
                "phase": name,
                "label": phase.get("label") or name,
                "start": phase.get("start") or "",
                "end": phase.get("end") or "",
                "cadence": PHASE_CADENCE.get(name, PHASE_CADENCE["live"]),
                "when": next((row[2] for row in PLATFORMS), "18:00–21:00 local"),
            }
        )
    top_tags = (social.get("tiktok") or {}).get("hashtags") or []
    return {
        "product": product,
        "event": event,
        "role": role,
        "family": family,
        "platform": plan.get("platform") or "",
        "promo_start": plan.get("promo_start") or "",
        "promo_end": plan.get("promo_end") or "",
        "runtime_start": plan.get("runtime_start") or plan.get("event_start") or "",
        "runtime_end": plan.get("runtime_end") or plan.get("event_end") or "",
        "social": social,
        "seo_keywords": seo,
        "top_hashtags": top_tags[:5],
        "affiliate": affiliate_link(product, plan.get("platform") or ""),
        "post_times": {key: pack.get("best_times") for key, pack in social.items()},
        "schedule": schedule,
        "pieces": _pieces(plan, social, seo),
    }


def content_kit_for_plans(
    plans: list[dict] | None,
    *,
    perspective: str = "product",
    limit: int = 6,
) -> dict:
    correlations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for plan in plans or []:
        key = (
            (plan.get("canonical_title") or "").strip().lower(),
            (plan.get("event") or "").strip().lower(),
        )
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        row = correlation_from_plan(plan)
        if not row:
            continue
        correlations.append(row)
        if len(correlations) >= limit:
            break
    return {
        "perspective": perspective,
        "correlation_count": len(correlations),
        "disclaimer": (
            "Affiliate URLs are store-search templates. Insert your network tag "
            "(Amazon YOURTAG, Steam partner, console store) before publishing. "
            "Mark paid partnerships (#ad) on every platform."
        ),
        "correlations": correlations,
    }
