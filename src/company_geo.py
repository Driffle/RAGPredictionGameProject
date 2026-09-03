"""Map developers and publishers to the country where they are based."""

from __future__ import annotations

import re

from src.match import (
    company_key,
    franchise_companies_for_keys,
    franchise_keys_for_text,
    normalize_franchise_text,
)

# Longest / most specific keys first when matching substrings.
COMPANY_COUNTRIES: dict[str, str] = {
    "nintendo": "JP",
    "capcom": "JP",
    "square enix": "JP",
    "sega": "JP",
    "atlus": "JP",
    "bandai namco": "JP",
    "namco bandai": "JP",
    "konami": "JP",
    "koei tecmo": "JP",
    "fromsoftware": "JP",
    "from software": "JP",
    "platinumgames": "JP",
    "cygames": "JP",
    "game freak": "JP",
    "intelligent systems": "JP",
    "monolith soft": "JP",
    "hal laboratory": "JP",
    "arc system works": "JP",
    "snk": "JP",
    "falcom": "JP",
    "nippon ichi": "JP",
    "idea factory": "JP",
    "compile heart": "JP",
    "marvelous": "JP",
    "level 5": "JP",
    "gust": "JP",
    "omega force": "JP",
    "team ninja": "JP",
    "kojima productions": "JP",
    "spike chunsoft": "JP",
    "kadokawa": "JP",
    "aniplex": "JP",
    "toho": "JP",
    "taito": "JP",
    "capcom": "JP",
    "sony": "JP",
    "playstation studios": "JP",
    "mihoyo": "CN",
    "hoyoverse": "CN",
    "cognosphere": "CN",
    "tencent": "CN",
    "netease": "CN",
    "level infinite": "CN",
    "game science": "CN",
    "perfect world": "CN",
    "hypergryph": "CN",
    "kuro games": "CN",
    "papergames": "CN",
    "infold": "CN",
    "yostar": "CN",
    "bilibili": "CN",
    "funplus": "CN",
    "lilith": "CN",
    "netdragon": "CN",
    "sunborn": "CN",
    "morefun": "CN",
    "nexon": "KR",
    "ncsoft": "KR",
    "nc soft": "KR",
    "netmarble": "KR",
    "krafton": "KR",
    "smilegate": "KR",
    "pearl abyss": "KR",
    "shift up": "KR",
    "neowiz": "KR",
    "kakao": "KR",
    "round8": "KR",
    "devsisters": "KR",
    "com2us": "KR",
    "bluehole": "KR",
    "pubg studios": "KR",
    "ubisoft": "FR",
    "dontnod": "FR",
    "don't nod": "FR",
    "asobo": "FR",
    "focus entertainment": "FR",
    "amplitude": "FR",
    "arkane lyon": "FR",
    "crytek": "DE",
    "yager": "DE",
    "deck13": "DE",
    "daedalic": "DE",
    "innogames": "DE",
    "blue byte": "DE",
    "mimimi": "DE",
    "king art": "DE",
    "cd projekt": "PL",
    "techland": "PL",
    "11 bit": "PL",
    "io interactive": "DK",
    "thq nordic": "AT",
    "larian": "BE",
    "supergiant": "US",
    "xbox": "US",
    "bethesda": "US",
    "electronic arts": "US",
    "ea sports": "US",
    "activision": "US",
    "blizzard": "US",
    "take two": "US",
    "2k": "US",
    "rockstar": "US",
    "epic": "US",
    "valve": "US",
    "insomniac": "US",
    "naughty dog": "US",
    "sucker punch": "US",
    "santa monica": "US",
    "guerrilla": "NL",
    "cd projekt red": "PL",
}

TITLE_COUNTRY_NEEDLES: tuple[tuple[str, str], ...] = (
    ("genshin", "CN"),
    ("honkai", "CN"),
    ("zenless", "CN"),
    ("wuthering waves", "CN"),
    ("black myth", "CN"),
    ("honor of kings", "CN"),
    ("arena of valor", "CN"),
    ("identity v", "CN"),
    ("infinity nikki", "CN"),
    ("where winds meet", "CN"),
    ("punishing gray raven", "CN"),
    ("reverse 1999", "CN"),
    ("monster hunter", "JP"),
    ("resident evil", "JP"),
    ("street fighter", "JP"),
    ("devil may cry", "JP"),
    ("final fantasy", "JP"),
    ("dragon quest", "JP"),
    ("kingdom hearts", "JP"),
    ("persona", "JP"),
    ("yakuza", "JP"),
    ("like a dragon", "JP"),
    ("elden ring", "JP"),
    ("sekiro", "JP"),
    ("dark souls", "JP"),
    ("bayonetta", "JP"),
    ("nier", "JP"),
    ("okami", "JP"),
    ("onimusha", "JP"),
    ("mega man", "JP"),
    ("animal crossing", "JP"),
    ("xenoblade", "JP"),
    ("fire emblem", "JP"),
    ("splatoon", "JP"),
    ("super mario", "JP"),
    ("mario kart", "JP"),
    ("mario", "JP"),
    ("the legend of zelda", "JP"),
    ("zelda", "JP"),
    ("kirby", "JP"),
    ("pokemon", "JP"),
    ("pokémon", "JP"),
    ("lost ark", "KR"),
    ("black desert", "KR"),
    ("stellar blade", "KR"),
    ("lie of p", "KR"),
    ("nikke", "KR"),
    ("inzoi", "KR"),
    ("pubg", "KR"),
    ("battlegrounds", "KR"),
)

_SORTED_COMPANIES = tuple(sorted(COMPANY_COUNTRIES, key=len, reverse=True))


def geos_for_company(value: str | None) -> set[str]:
    key = company_key(value)
    if not key:
        return set()
    direct = COMPANY_COUNTRIES.get(key)
    if direct:
        return {direct}
    geos: set[str] = set()
    for needle in _SORTED_COMPANIES:
        if len(needle) < 4:
            continue
        if needle in key or key in needle:
            geos.add(COMPANY_COUNTRIES[needle])
            break
    return geos


def product_origin_geos(product: dict) -> set[str]:
    """Countries where this game's developer or publisher is based."""
    geos: set[str] = set()
    for field in ("developer", "publisher"):
        geos |= geos_for_company(product.get(field))
    keys = franchise_keys_for_text(product.get("canonical_title") or "") | franchise_keys_for_text(
        product.get("franchise") or ""
    )
    for company in franchise_companies_for_keys(keys):
        geos |= geos_for_company(company)
    title = normalize_franchise_text(
        f"{product.get('canonical_title') or ''} {product.get('product_title') or ''}"
    )
    for needle, geo in TITLE_COUNTRY_NEEDLES:
        if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", title):
            geos.add(geo)
    return geos
