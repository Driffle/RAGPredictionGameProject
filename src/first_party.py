"""First-party publisher matching for console showcase events.

State of Play → Sony Interactive Entertainment / PlayStation Studios.
Nintendo Direct (not Partner Showcase) → Nintendo.
Xbox Games Showcase / Developer Direct / E-Day Direct → Xbox Game Studios
and Microsoft-owned Bethesda.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShowcaseOwner:
    family: str
    publisher_label: str
    event_needles: tuple[str, ...]
    event_exclude: tuple[str, ...]
    publisher_needles: tuple[str, ...]
    developer_needles: tuple[str, ...]
    title_needles: tuple[str, ...]


SHOWCASES: tuple[ShowcaseOwner, ...] = (
    ShowcaseOwner(
        family="sony",
        publisher_label="Sony Interactive Entertainment",
        event_needles=("state of play", "playstation showcase"),
        event_exclude=(),
        publisher_needles=(
            "sony interactive",
            "sony computer entertainment",
            "playstation studios",
            "playstation pc",
        ),
        developer_needles=(
            "naughty dog",
            "insomniac",
            "santa monica studio",
            "guerrilla games",
            "sucker punch",
            "polyphony digital",
            "team asobi",
            "housemarque",
            "nixxes",
            "bluepoint",
            "haven studios",
            "bend studio",
            "media molecule",
            "japan studio",
            "team icarus",
            "firesprite",
            "san diego studio",
            "london studio",
            "malaysia studio",
        ),
        title_needles=(
            "god of war",
            "spider-man",
            "spiderman",
            "miles morales",
            "the last of us",
            "uncharted",
            "horizon zero dawn",
            "horizon forbidden west",
            "ghost of tsushima",
            "ghost of yotei",
            "gran turismo",
            "ratchet & clank",
            "ratchet and clank",
            "returnal",
            "astro bot",
            "astro's playroom",
            "days gone",
            "bloodborne",
            "helldivers",
            "mlb the show",
            "knack",
            "concrete genie",
            "sackboy",
            "until dawn",
            "death stranding",
            "infamous",
            "killzone",
            "marvel's wolverine",
            "intergalactic",
        ),
    ),
    ShowcaseOwner(
        family="nintendo",
        publisher_label="Nintendo",
        event_needles=("nintendo direct",),
        event_exclude=("partner",),
        publisher_needles=("nintendo",),
        developer_needles=(
            "nintendo",
            "retro studios",
            "intelligent systems",
            "monolith soft",
            "next level games",
            "hal laboratory",
            "game freak",
            "sora ltd",
            "grezzo",
        ),
        title_needles=(
            "mario",
            "zelda",
            "pokemon",
            "pokémon",
            "metroid",
            "animal crossing",
            "splatoon",
            "kirby",
            "smash bros",
            "fire emblem",
            "xenoblade",
            "pikmin",
            "star fox",
            "donkey kong",
            "luigi's mansion",
            "yoshi",
            "wario",
            "nintendo switch sports",
            "arms",
        ),
    ),
    ShowcaseOwner(
        family="xbox",
        publisher_label="Xbox Game Studios",
        event_needles=(
            "xbox games showcase",
            "xbox developer direct",
            "xbox & bethesda",
            "xbox and bethesda",
            "e-day direct",
            "gears of war: e-day direct",
        ),
        event_exclude=(),
        publisher_needles=(
            "xbox game studios",
            "microsoft studios",
            "microsoft game studios",
            "bethesda softworks",
        ),
        developer_needles=(
            "playground games",
            "turn 10",
            "the coalition",
            "343 industries",
            "compulsion games",
            "double fine",
            "obsidian",
            "inxile",
            "world's edge",
            "mojang",
            "rare ltd",
            "rare ",
            "ninja theory",
            "undead labs",
            "bethesda game studios",
            "id software",
            "machinegames",
            "arkane",
            "the initiative",
        ),
        title_needles=(
            "halo",
            "forza",
            "gears of war",
            "fable",
            "sea of thieves",
            "minecraft",
            "doom",
            "elder scrolls",
            "fallout",
            "starfield",
            "perfect dark",
            "state of decay",
            "age of empires",
            "hi-fi rush",
            "grounded",
            "psychonauts",
            "avowed",
            "south of midnight",
        ),
    ),
)


def showcase_owner(event_name: str | None) -> ShowcaseOwner | None:
    blob = (event_name or "").strip().lower()
    if not blob:
        return None
    for spec in SHOWCASES:
        if spec.event_exclude and any(token in blob for token in spec.event_exclude):
            continue
        if any(token in blob for token in spec.event_needles):
            return spec
    return None


def _blob(product: dict) -> str:
    return " ".join(
        str(product.get(key) or "")
        for key in ("publisher", "developer", "canonical_title", "product_title", "franchise")
    ).lower()


def is_owned_product(product: dict, spec: ShowcaseOwner) -> bool:
    """True when the SKU is published or made by the console owner's studios."""
    publisher = (product.get("publisher") or "").lower()
    developer = (product.get("developer") or "").lower()
    title = f"{product.get('canonical_title') or ''} {product.get('product_title') or ''}".lower()
    if any(token in publisher for token in spec.publisher_needles):
        return True
    if any(token in developer for token in spec.developer_needles):
        return True
    return any(token in title for token in spec.title_needles)


def is_owned_title(title: str, spec: ShowcaseOwner) -> bool:
    return is_owned_product({"canonical_title": title}, spec)


def owned_search_queries(spec: ShowcaseOwner) -> list[str]:
    return list(spec.title_needles)


def prioritize_owned(event_name: str | None, products: list[dict], *, owned_only: bool = True) -> list[dict]:
    spec = showcase_owner(event_name)
    if not spec:
        return products
    owned = [row for row in products if is_owned_product(row, spec)]
    if owned_only:
        return owned or products
    other = [row for row in products if row not in owned]
    return owned + other
