"""Retrieve and store cover art / event logos for Floor Brief.

Primary source: Wikipedia REST page summaries (box art, posters, event logos).
Dataset: data/processed/live/artwork.json + local thumbs under live/artwork/.
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from src.http import http_get, http_get_json
from src.paths import DATA_PROCESSED

LIVE_DIR = DATA_PROCESSED / "live"
ARTWORK_JSON = LIVE_DIR / "artwork.json"
ARTWORK_DIR = LIVE_DIR / "artwork"
ARTWORK_META = LIVE_DIR / "artwork_meta.json"
ARTWORK_CSV = DATA_PROCESSED / "artwork.csv"
PLACEHOLDER_DIR = ARTWORK_DIR / "placeholders"


def _slug(value: str) -> str:
    text = re.sub(r"[^\w\s-]+", "", (value or "").lower(), flags=re.U)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:80] or "item"


def wiki_title_from_url(url: str | None) -> str:
    if not url:
        return ""
    path = urlparse(url).path
    if "/wiki/" not in path:
        return ""
    return unquote(path.split("/wiki/", 1)[1]).replace("_", " ")


def wikipedia_summary_image(title: str) -> dict | None:
    """Return thumbnail / original image URLs for a Wikipedia page title."""
    clean = (title or "").strip()
    if not clean:
        return None
    if clean.startswith("http"):
        clean = wiki_title_from_url(clean) or clean
    try:
        payload = http_get_json(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(clean.replace(' ', '_'))}",
            timeout=25,
        )
    except Exception:
        return None
    if payload.get("type") == "disambiguation":
        return None
    thumb = (payload.get("thumbnail") or {}).get("source") or ""
    original = (payload.get("originalimage") or {}).get("source") or ""
    image = thumb or original
    if not image:
        return None
    return {
        "title": payload.get("title") or clean,
        "image_url": image,
        "thumb_url": thumb or image,
        "original_url": original or image,
        "wikipedia_url": (payload.get("content_urls") or {}).get("desktop", {}).get("page")
        or f"https://en.wikipedia.org/wiki/{quote(clean.replace(' ', '_'))}",
        "description": (payload.get("description") or "")[:160],
        "source": "wikipedia_summary",
    }


def wikipedia_search_image(name: str, hint: str = "") -> dict | None:
    """Find a page via search when the exact title has no summary image.

    Many storefront titles differ from the article name ("Silksong" vs
    "Hollow Knight: Silksong"), which otherwise leaves a blank cover.
    """
    query = " ".join(part for part in ((name or "").strip(), hint) if part)
    if not query.strip():
        return None
    try:
        payload = http_get_json(
            "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch="
            + quote(query),
            timeout=25,
        )
    except Exception:
        return None
    for hit in ((payload.get("query") or {}).get("search") or [])[:3]:
        title = hit.get("title") or ""
        if not title:
            continue
        found = wikipedia_summary_image(title)
        if found:
            found["source"] = "wikipedia_search"
            return found
    return None


def _download_thumb(url: str, dest: Path) -> str:
    """Save a small local copy for offline / app use. Returns relative media path."""
    try:
        raw = http_get(url, timeout=30)
    except Exception:
        return ""
    if not raw or len(raw) < 200:
        return ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = ".jpg"
    lower = url.lower()
    if ".png" in lower:
        suffix = ".png"
    elif ".svg" in lower:
        suffix = ".svg"
    elif ".webp" in lower:
        suffix = ".webp"
    elif ".jpeg" in lower or ".jpg" in lower:
        suffix = ".jpg"
    path = dest.with_suffix(suffix)
    path.write_bytes(raw)
    return f"/media/artwork/{path.name}"


STATIC_FALLBACK = {
    "product": "/static/img/placeholder-product.svg",
    "event": "/static/img/placeholder-event.svg",
}


_PLACEHOLDER_CACHE: dict[tuple[str, str], str] = {}


def ensure_placeholder(name: str, kind: str) -> str:
    """Title-stamped placeholder, falling back to the bundled static art."""
    cached = _PLACEHOLDER_CACHE.get((kind, name))
    if cached:
        return cached
    try:
        PLACEHOLDER_DIR.mkdir(parents=True, exist_ok=True)
        path = PLACEHOLDER_DIR / f"{kind}-{_slug(name)}.svg"
        public = f"/media/artwork/placeholders/{path.name}"
        if path.exists():
            _PLACEHOLDER_CACHE[(kind, name)] = public
            return public
        label = (name or kind)[:42].replace("&", "&amp;").replace("<", "&lt;")
        path.write_text(
            f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="800" viewBox="0 0 640 800">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#12182a"/>
      <stop offset="100%" stop-color="#1c2744"/>
    </linearGradient>
  </defs>
  <rect width="640" height="800" fill="url(#g)"/>
  <rect x="36" y="36" width="568" height="728" rx="18" fill="none" stroke="#5ce1e6" stroke-opacity=".35" stroke-width="2"/>
  <text x="320" y="390" text-anchor="middle" font-family="IBM Plex Sans, Arial, sans-serif" font-size="28" fill="#f4f7ff">{label}</text>
  <text x="320" y="440" text-anchor="middle" font-family="IBM Plex Sans, Arial, sans-serif" font-size="16" fill="#9aa6c3">{kind} artwork</text>
</svg>
""",
            encoding="utf-8",
        )
        _PLACEHOLDER_CACHE[(kind, name)] = public
        return public
    except OSError:
        return STATIC_FALLBACK.get(kind, STATIC_FALLBACK["product"])


_ARTWORK_CACHE: dict | None = None
_ARTWORK_STAMP: float | None = None


def load_artwork() -> dict:
    """Read the artwork dataset, cached until the file changes.

    Briefs resolve hundreds of covers per request, so re-parsing the JSON each
    lookup dominated response time.
    """
    global _ARTWORK_CACHE, _ARTWORK_STAMP
    if not ARTWORK_JSON.exists():
        return {"products": {}, "events": {}, "updated": "", "counts": {}}
    stamp = ARTWORK_JSON.stat().st_mtime
    if _ARTWORK_CACHE is not None and _ARTWORK_STAMP == stamp:
        return _ARTWORK_CACHE
    payload = json.loads(ARTWORK_JSON.read_text(encoding="utf-8"))
    # Normalize legacy flat {items:[...]} / {key: row} shapes if present.
    if "products" in payload and "events" in payload:
        data = payload
    else:
        products: dict[str, dict] = {}
        events: dict[str, dict] = {}
        rows = payload.get("items") if isinstance(payload, dict) else None
        for row in rows or []:
            kind = row.get("kind") or "product"
            key = (row.get("name") or "").strip().lower()
            if key:
                (products if kind == "product" else events)[key] = row
        data = {"products": products, "events": events, "updated": "", "counts": {}}
    _ARTWORK_CACHE = data
    _ARTWORK_STAMP = stamp
    return data


def _public_url(row: dict) -> str:
    return row.get("image_url") or row.get("thumb_url") or row.get("local_path") or ""


def artwork_for(*args, kind: str = "product", name: str | None = None, dataset: dict | None = None) -> dict:
    """Lookup cover art.

    Supported forms:
      artwork_for("Hytale", kind="product")
      artwork_for("product", "Hytale")
      artwork_for(kind="event", name="Gamescom")
    """
    if len(args) == 2:
        kind, name = str(args[0]), str(args[1])
    elif len(args) == 1:
        name = str(args[0])
    display = (name or "").strip()
    data = dataset if isinstance(dataset, dict) else load_artwork()
    bucket = data.get("products" if kind == "product" else "events") or {}
    key = display.lower()
    row = dict(bucket.get(key) or {})
    if not row:
        needle = _slug(display)
        for candidate, item in bucket.items():
            if _slug(candidate) == needle or _slug(item.get("name") or "") == needle:
                row = dict(item)
                break
    if not row:
        # "<Title> release window" rows should wear the game's cover art.
        base = re.sub(r"\s+release window$", "", display, flags=re.I).strip()
        if base and base.lower() != display.lower():
            product = artwork_for(base, kind="product", dataset=data)
            if product and not product.get("placeholder"):
                return {**product, "name": display, "kind": kind}
    if not row:
        placeholder = ensure_placeholder(display or "item", kind)
        return {
            "name": display,
            "kind": kind,
            "image_url": placeholder,
            "source": "placeholder",
            "placeholder": True,
            "local_path": placeholder,
        }
    url = _public_url(row)
    if not url:
        url = ensure_placeholder(display or row.get("name") or "item", kind)
        row["placeholder"] = True
        row["source"] = row.get("source") or "placeholder"
    row["image_url"] = url
    row.setdefault("kind", kind)
    row.setdefault("name", display or row.get("name") or "")
    return row

def write_artwork_csv(payload: dict | None = None) -> Path:
    data = payload or load_artwork()
    rows = []
    for kind, bucket in (("product", data.get("products") or {}), ("event", data.get("events") or {})):
        for key, row in bucket.items():
            rows.append(
                {
                    "key": f"{kind}:{_slug(row.get('name') or key)}",
                    "name": row.get("name") or key,
                    "kind": kind,
                    "image_url": _public_url(row),
                    "page_url": row.get("wikipedia_url") or row.get("page_url") or "",
                    "source": row.get("source") or "",
                    "placeholder": bool(row.get("placeholder")),
                    "local_path": row.get("local_path") or "",
                }
            )
    rows.sort(key=lambda r: (r["kind"], r["name"].lower()))
    ARTWORK_CSV.parent.mkdir(parents=True, exist_ok=True)
    with ARTWORK_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["key", "name", "kind", "image_url", "page_url", "source", "placeholder", "local_path"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return ARTWORK_CSV


def refresh_artwork_dataset(
    products: list[dict] | None = None,
    events: list[dict] | None = None,
    *,
    adaptations: list[dict] | None = None,
    limit_products: int = 220,
    limit_events: int = 180,
    download: bool = True,
    fetch: bool | None = None,
) -> dict:
    """Build/overwrite the artwork dataset for products and events."""
    if fetch is not None:
        download = fetch
    products = products or []
    events = events or []
    existing = load_artwork()
    product_art: dict[str, dict] = dict(existing.get("products") or {})
    event_art: dict[str, dict] = dict(existing.get("events") or {})

    product_targets: list[tuple[str, str]] = []
    seen_p: set[str] = set()
    for row in products:
        title = (row.get("canonical_title") or row.get("product_title") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen_p:
            continue
        seen_p.add(key)
        wiki = wiki_title_from_url(row.get("wikipedia_url")) or title
        product_targets.append((title, wiki))
        if len(product_targets) >= limit_products:
            break

    event_targets: list[tuple[str, str]] = []
    seen_e: set[str] = set()
    for row in list(events) + list(adaptations or []):
        name = (row.get("event") or row.get("ip_adaptation") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_e:
            continue
        seen_e.add(key)
        wiki = wiki_title_from_url(row.get("wikipedia_url")) or name
        wiki = re.sub(r"\s+release window$", "", wiki, flags=re.I)
        event_targets.append((name, wiki))
        if len(event_targets) >= limit_events:
            break

    fetched = 0
    reused = 0
    ARTWORK_DIR.mkdir(parents=True, exist_ok=True)

    def upsert(bucket: dict[str, dict], display: str, wiki_title: str, kind: str) -> None:
        nonlocal fetched, reused
        key = display.lower()
        prior = bucket.get(key) or {}
        # Placeholders are retried on a fetching run so stand-ins get upgraded
        # to the real cover art as soon as a page picture becomes available.
        if prior.get("image_url") and not prior.get("placeholder") and (prior.get("local_path") or not download):
            reused += 1
            return
        if not download:
            if prior.get("image_url"):
                reused += 1
                return
            placeholder = ensure_placeholder(display, kind)
            bucket[key] = {
                "name": display,
                "kind": kind,
                "image_url": placeholder,
                "local_path": placeholder,
                "source": "placeholder",
                "placeholder": True,
            }
            return
        hit = wikipedia_summary_image(wiki_title)
        time.sleep(0.18)
        if not hit and wiki_title != display:
            hit = wikipedia_summary_image(display)
            time.sleep(0.18)
        if not hit:
            hit = wikipedia_search_image(wiki_title or display, "video game" if kind == "product" else "")
            time.sleep(0.18)
        if not hit:
            if prior.get("image_url"):
                reused += 1
                return
            placeholder = ensure_placeholder(display, kind)
            bucket[key] = {
                "name": display,
                "kind": kind,
                "image_url": placeholder,
                "local_path": placeholder,
                "source": "placeholder",
                "placeholder": True,
            }
            return
        record = {
            "name": display,
            "kind": kind,
            "image_url": hit["image_url"],
            "thumb_url": hit.get("thumb_url") or hit["image_url"],
            "original_url": hit.get("original_url") or hit["image_url"],
            "wikipedia_url": hit.get("wikipedia_url") or "",
            "description": hit.get("description") or "",
            "source": hit.get("source") or "wikipedia_summary",
            "placeholder": False,
        }
        local = _download_thumb(hit["image_url"], ARTWORK_DIR / f"{kind}-{_slug(display)}")
        if local:
            record["local_path"] = local
        elif prior.get("local_path"):
            record["local_path"] = prior["local_path"]
        bucket[key] = record
        fetched += 1

    for display, wiki in product_targets:
        upsert(product_art, display, wiki, "product")
    for display, wiki in event_targets:
        upsert(event_art, display, wiki, "event")

    payload = {
        "updated": time.strftime("%Y-%m-%d"),
        "products": product_art,
        "events": event_art,
        "counts": {
            "products": len(product_art),
            "events": len(event_art),
            "fetched_this_run": fetched,
            "reused": reused,
        },
    }
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARTWORK_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ARTWORK_META.write_text(
        json.dumps(
            {
                "updated": payload["updated"],
                "products": len(product_art),
                "events": len(event_art),
                "with_local": sum(
                    1
                    for row in list(product_art.values()) + list(event_art.values())
                    if row.get("local_path")
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_artwork_csv(payload)
    # Shape expected by database meta writers
    payload["count"] = len(product_art) + len(event_art)
    payload["remote"] = sum(
        1
        for row in list(product_art.values()) + list(event_art.values())
        if not row.get("placeholder")
    )
    payload["items"] = [
        {
            "key": f"{kind}:{_slug(row.get('name') or key)}",
            "name": row.get("name") or key,
            "kind": kind,
            "image_url": _public_url(row),
            "page_url": row.get("wikipedia_url") or "",
            "source": row.get("source") or "",
            "placeholder": bool(row.get("placeholder")),
        }
        for kind, bucket in (("product", product_art), ("event", event_art))
        for key, row in bucket.items()
    ]
    return payload


def main() -> None:
    from src.load_data import load_adaptations, load_catalog, load_events

    catalog = load_catalog(games_only=True, drop_placeholder_dates=True)
    catalog = sorted(
        catalog,
        key=lambda row: (
            0 if row.get("product_type") == "announced" else 1,
            row.get("release_date") or "9999",
        ),
    )
    payload = refresh_artwork_dataset(
        products=catalog,
        events=load_events(),
        adaptations=load_adaptations(),
        download=True,
    )
    print(json.dumps(payload.get("counts"), indent=2))


if __name__ == "__main__":
    main()
