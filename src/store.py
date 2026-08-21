"""In-memory store for the Floor Brief web and desktop apps."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache

from src.artwork import artwork_for, load_artwork
from src.audit_changes import load_changes
from src.calendar_dedupe import is_gaming_world_event, is_quarter_timeframe, split_deduped_calendar, unique_event_listings
from src.content_marketing import content_kit_for_plans, correlation_from_plan
from src.coverage import cross_media_releases
from src.cross_sell import cross_sell_payload, unique_events
from src.daily_brief import run as run_daily_brief
from src.database import live_meta, refresh_live_database
from src.date_range import calendar_range_payload, is_current_or_in_range, range_span
from src.dates import annotate_event, annotate_product, confirmation_kind
from src.documents import load_rag_meta
from src.geo_placement import apply_event_geo, market_sections, placement_payload
from src.official_dates import apply_event_overrides, apply_product_overrides
from src.historical_calendar import historical_adaptations
from src.load_data import load_adaptations, load_catalog, load_events
from src.match import franchise_keys_for_text, superhero_universe_for_row
from src.orders import ORDER_YEARS, load_order_dashboard
from src.promote import (
    build_plans,
    correlate_calendar_event,
    correlation_indexes,
    make_promotion_plan,
    plans_active_on,
    product_role,
)
from src.priorities import (
    filter_trend_bundle,
    load_cached_brief,
    rank_daily_priorities,
    save_daily_brief,
)
from src.provenance import display_source, stamp_provenance

_JUNK = re.compile(r"random 1 key|try to get", re.I)


def _calendar_listing_key(row: dict) -> tuple[str, str]:
    name = (row.get("event") or row.get("ip_adaptation") or "").strip().lower()
    return name, (row.get("start_date") or "")[:10]


def _append_missing_calendar(base: list[dict], extra: list[dict]) -> list[dict]:
    seen = {_calendar_listing_key(row) for row in base if _calendar_listing_key(row)[0]}
    out = list(base)
    for row in extra:
        key = _calendar_listing_key(row)
        if key[0] and key not in seen:
            out.append(row)
            seen.add(key)
    return out


def _search_text(value: str | None) -> str:
    text = (value or "").lower().replace("’", "'")
    text = re.sub(r"[\s\-':.]+", " ", text)
    return text.strip()


def _cover(name: str | None, kind: str) -> dict:
    """Artwork for a row, always resolving to a usable image (never blank)."""
    return artwork_for(name or f"Untitled {kind}", kind=kind)


def _public_social(product: dict, event_name: str = "") -> dict:
    plan = dict(product)
    if event_name and not plan.get("event"):
        plan["event"] = event_name
    corr = correlation_from_plan(plan)
    if not corr:
        return product
    return {
        **product,
        "event": plan.get("event") or event_name,
        "top_hashtags": corr.get("top_hashtags") or [],
        "post_times": corr.get("post_times") or {},
        "seo_keywords": (corr.get("seo_keywords") or [])[:4],
        "affiliate": corr.get("affiliate") or {},
    }


def _public_product(row: dict) -> dict:
    title = row.get("canonical_title") or ""
    art = _cover(title, "product")
    dated = annotate_product(row)
    return {
        "date_precision": dated.get("date_precision") or "day",
        "release_label": dated.get("release_label") or "",
        "release_start": dated.get("release_start") or "",
        "release_end": dated.get("release_end") or "",
        "product_id": row.get("product_id") or "",
        "product_sku": row.get("product_sku") or "",
        "canonical_title": title,
        "product_title": row.get("product_title") or "",
        "product_type": row.get("product_type") or "",
        "platform": row.get("platform") or "",
        "release_date": row.get("release_date") or "",
        "status": row.get("status") or "",
        "role": product_role(row),
        "wikipedia_url": row.get("wikipedia_url") or "",
        "genre": row.get("genre") or "",
        "developer": row.get("developer") or "",
        "publisher": row.get("publisher") or "",
        "confirmation": row.get("confirmation") or row.get("status") or "",
        "official_source": row.get("official_source") or "",
        "source": display_source(row) if row else "catalog",
        "entry_date": row.get("entry_date") or "",
        "last_checked": row.get("last_checked") or "",
        "image_url": art.get("image_url") or "",
        "image_source": art.get("source") or "",
    }


def _nice_date(value: str) -> str:
    if not value or len(value) < 10:
        return value or "an unconfirmed date"
    year, month, day = value[:10].split("-")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{int(day)} {months[int(month) - 1]} {year}"


class FloorStore:
    def __init__(self) -> None:
        self.catalog: list[dict] = []
        self.events: list[dict] = []
        self.adaptations: list[dict] = []
        self.plans: list[dict] = []
        self.by_title: dict[str, list[dict]] = defaultdict(list)
        self.titles: list[str] = []
        self.featured: list[str] = []
        self.bundle: dict = {"google_trends": [], "wikipedia": []}
        self.priorities: list[dict] = []
        self.meta: dict = {}
        self.loaded = False

    def load(self) -> None:
        # Publisher/organizer confirmed dates win over raw catalog + scrapes at
        # load time too, so the UI always shows verified timing.
        self.catalog = [
            stamp_provenance(row, default_source="catalog")
            for row in apply_product_overrides(
                [
                    row
                    for row in load_catalog(games_only=True, drop_placeholder_dates=True)
                    if not _JUNK.search(row.get("canonical_title") or "")
                    and not is_quarter_timeframe(row.get("canonical_title") or "")
                ]
            )
        ]
        self.events = [
            stamp_provenance(apply_event_geo(annotate_event(row)), default_source="calendar")
            for row in apply_event_overrides(load_events())
        ]
        self.adaptations = [
            stamp_provenance(apply_event_geo(annotate_event(row)), default_source="calendar")
            for row in apply_event_overrides(
                _append_missing_calendar(load_adaptations(), cross_media_releases() + historical_adaptations())
            )
        ]
        self.events, self.adaptations = split_deduped_calendar(self.events, self.adaptations)
        self.plans = build_plans(self.events, self.adaptations, self.catalog)
        self.by_title = defaultdict(list)
        for row in self.catalog:
            title = (row.get("canonical_title") or "").strip()
            if title:
                self.by_title[title.lower()].append(row)
        self.titles = sorted(self.by_title, key=lambda key: key)
        self._refresh_trends(refresh=False)
        self._build_featured()
        self.meta = live_meta()
        self.loaded = True

    def refresh_database(self) -> dict:
        self.meta = refresh_live_database(fetch=True)
        self.load()
        return self.meta

    def refresh_trends(self) -> None:
        self._refresh_trends(refresh=True)
        self._build_featured()

    def _refresh_trends(self, *, refresh: bool) -> None:
        cached = None if refresh else load_cached_brief()
        if cached and not refresh:
            bundle, _ = cached
            self.bundle = filter_trend_bundle(
                self.catalog,
                self.events + self.adaptations,
                bundle,
            )
            self.priorities = rank_daily_priorities(
                self.catalog,
                self.plans,
                self.bundle,
            )
            save_daily_brief(self.bundle, self.priorities)
            return
        result = run_daily_brief(refresh=refresh)
        self.bundle = result["bundle"]
        self.priorities = result["priorities"]

    def _build_featured(self) -> None:
        ordered: list[str] = []
        seen: set[str] = set()
        for item in self.priorities:
            title = item.get("canonical_title") or ""
            if title and not is_quarter_timeframe(title) and title.lower() not in seen:
                seen.add(title.lower())
                ordered.append(title)
        for row in sorted(
            (
                row
                for row in self.catalog
                if row.get("product_type") == "announced"
                and (row.get("release_date") or "") >= date.today().isoformat()
            ),
            key=lambda row: row.get("release_date") or "9999",
        ):
            title = row.get("canonical_title") or ""
            if title and not is_quarter_timeframe(title) and title.lower() not in seen:
                seen.add(title.lower())
                ordered.append(title)
            if len(ordered) >= 40:
                break
        for plan in self.plans:
            if plan.get("role") != "game":
                continue
            title = plan.get("canonical_title") or ""
            if title and not is_quarter_timeframe(title) and title.lower() not in seen:
                seen.add(title.lower())
                ordered.append(title)
            if len(ordered) >= 80:
                break
        self.featured = ordered[:80]

    def search_products(self, query: str, *, limit: int = 30) -> list[dict]:
        needle = (query or "").strip().lower()
        if not needle:
            return [self._title_card(title) for title in self.featured[:limit]]
        compact = re.sub(r"[\s\-':.]+", " ", needle).strip()
        featured = {title.lower() for title in self.featured}
        priorities = {
            (item.get("canonical_title") or "").lower()
            for item in self.priorities
            if item.get("canonical_title")
        }
        scored: list[tuple[int, str]] = []
        for title in self.titles:
            compact_title = re.sub(r"[\s\-':.]+", " ", title).strip()
            if compact not in compact_title:
                continue
            score = 0
            if compact_title == compact:
                score += 1000
            elif compact_title.startswith(compact + " "):
                rest = compact_title[len(compact) :].strip()
                if re.match(r"^(\d+|ii|iii|iv|v|vi|remastered|edition|deluxe)\b", rest):
                    score += 520
                else:
                    score += 90
            elif re.search(rf"\b{re.escape(compact)}\b", compact_title):
                score += 320
            else:
                score += 40
            score += min(len(self.by_title.get(title, [])), 24) * 6
            if title in featured or title in priorities:
                score += 90
            hero_rows = self.by_title.get(title) or []
            if hero_rows and hero_rows[0].get("product_type") == "announced":
                score += 70
            score -= min(len(title), 70)
            scored.append((score, title))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [self._title_card(title) for _, title in scored[:limit]]

    def _title_card(self, title_key: str) -> dict:
        rows = self.by_title.get(title_key) or self.by_title.get(title_key.lower()) or []
        if not rows and title_key:
            rows = self.by_title.get(title_key.lower(), [])
        display = rows[0]["canonical_title"] if rows else title_key
        platforms = sorted({row.get("platform") or "" for row in rows if row.get("platform")})
        types = sorted({row.get("product_type") or "" for row in rows if row.get("product_type")})
        releases = [row.get("release_date") or "" for row in rows if row.get("release_date")]
        art = _cover(display, "product")
        earliest = min(releases) if releases else ""
        dated = annotate_product({**(rows[0] if rows else {}), "release_date": earliest})
        return {
            "canonical_title": display,
            "sku_count": len(rows),
            "platforms": platforms[:8],
            "product_types": types,
            "release_date": earliest,
            "release_label": dated.get("release_label") or "",
            "date_precision": dated.get("date_precision") or "day",
            "official_source": (rows[0].get("official_source") if rows else "") or "",
            "source": display_source(rows[0]) if rows else "catalog",
            "entry_date": (rows[0].get("entry_date") if rows else "") or "",
            "last_checked": (rows[0].get("last_checked") if rows else "") or "",
            "wikipedia_url": (rows[0].get("wikipedia_url") if rows else "") or "",
            "confirmation": (rows[0].get("confirmation") if rows else "") or "",
            "genre": (rows[0].get("genre") if rows else "") or "",
            "image_url": art.get("image_url") or "",
            "image_source": art.get("source") or "",
        }

    def resolve_title(self, raw: str) -> str | None:
        text = (raw or "").strip()
        if not text:
            return None
        key = text.lower()
        if key in self.by_title:
            return self.by_title[key][0]["canonical_title"]
        hits = self.search_products(text, limit=1)
        return hits[0]["canonical_title"] if hits else None

    def _calendar_bounds(
        self,
        start_year: int | None = None,
        start_month: int | None = None,
        end_year: int | None = None,
        end_month: int | None = None,
    ) -> tuple[date | None, date | None]:
        if start_year is None or start_month is None or end_year is None or end_month is None:
            return None, None
        try:
            return range_span(int(start_year), int(start_month), int(end_year), int(end_month))
        except (TypeError, ValueError):
            return None, None

    def _filter_promo_windows(
        self,
        rows: list[dict],
        *,
        range_start: date | None = None,
        range_end: date | None = None,
    ) -> list[dict]:
        today = date.today()
        return [
            row
            for row in rows
            if is_current_or_in_range(
                row,
                today=today,
                range_start=range_start,
                range_end=range_end,
            )
        ]

    def _best_fallback_window(self, rows: list[dict]) -> dict:
        today = date.today().isoformat()
        future = [
            row
            for row in rows
            if (row.get("runtime_end") or row.get("event_end") or row.get("end") or row.get("promo_end") or "") >= today
        ]
        pool = future or list(rows)
        pool.sort(
            key=lambda row: row.get("runtime_start")
            or row.get("event_start")
            or row.get("start")
            or row.get("promo_start")
            or "9999"
        )
        return pool[0]

    def _plans_for_product(
        self,
        title: str,
        hero: dict,
        cross_media: list[dict],
        *,
        range_start: date | None,
        range_end: date | None,
    ) -> list[dict]:
        synced = [
            self._sync_promo_window(plan, cross_media)
            for plan in self.plans
            if plan.get("canonical_title", "").lower() == title.lower()
        ]
        kept = self._filter_promo_windows(synced, range_start=range_start, range_end=range_end)
        if kept:
            return kept
        row = correlate_calendar_event(
            title,
            self.events + self.adaptations,
            around=hero.get("release_date"),
            platform=hero.get("platform") or "",
        )
        if row:
            plan = make_promotion_plan(row, hero)
            if plan:
                return [self._sync_promo_window(plan, cross_media)]
        if synced:
            return [self._best_fallback_window(synced)]
        return []

    def _events_for_product(
        self,
        title: str,
        related_plans: list[dict],
        *,
        range_start: date | None,
        range_end: date | None,
    ) -> list[dict]:
        related = self._filter_promo_windows(
            self._related_events(title),
            range_start=range_start,
            range_end=range_end,
        )
        if related:
            return related
        unfiltered = self._related_events(title)
        if unfiltered:
            return [self._best_fallback_window(unfiltered)]
        if related_plans:
            name = related_plans[0].get("event") or ""
            cal = next(
                (
                    row
                    for row in self.events + self.adaptations
                    if (row.get("event") or row.get("ip_adaptation") or "") == name
                ),
                None,
            )
            if cal:
                return [self._event_card(cal)]
            plan = related_plans[0]
            return [
                {
                    "name": name,
                    "start": plan.get("runtime_start") or plan.get("event_start") or "",
                    "end": plan.get("runtime_end") or plan.get("event_end") or "",
                    "type": plan.get("event_type") or "",
                    "related": plan.get("related_game") or title,
                }
            ]
        row = correlate_calendar_event(title, self.events + self.adaptations)
        return [self._event_card(row)] if row else []

    def product_brief(
        self,
        raw: str,
        *,
        start_year: int | None = None,
        start_month: int | None = None,
        end_year: int | None = None,
        end_month: int | None = None,
    ) -> dict:
        title = self.resolve_title(raw)
        if not title:
            return {"found": False, "query": raw}
        rows = self.by_title[title.lower()]
        hero = rows[0]
        today = date.today().isoformat()
        range_start, range_end = self._calendar_bounds(start_year, start_month, end_year, end_month)
        cross_media = self._related_adaptations(title)
        related_plans = self._plans_for_product(
            title,
            hero,
            cross_media,
            range_start=range_start,
            range_end=range_end,
        )
        active = [
            plan
            for plan in related_plans
            if plan.get("promo_start", "") <= today <= plan.get("promo_end", "")
        ]
        trend = next(
            (item for item in self.priorities if (item.get("canonical_title") or "").lower() == title.lower()),
            None,
        )
        cross_media = self._filter_promo_windows(
            [self._sync_cross_media(card, related_plans) for card in cross_media],
            range_start=range_start,
            range_end=range_end,
        )
        related_events = self._events_for_product(
            title,
            related_plans,
            range_start=range_start,
            range_end=range_end,
        )
        siblings = [_public_product(row) for row in rows[:12]]
        is_announced = (hero.get("product_type") or "").lower() == "announced" or "announc" in (
            hero.get("confirmation") or hero.get("status") or ""
        ).lower()
        release_status = self._release_status(hero)
        synced_windows = related_plans[:8]
        synced_media = cross_media[:16]
        art = artwork_for(title, kind="product")
        return {
            "found": True,
            "canonical_title": title,
            "in_short": self._in_short(hero, related_plans, active, trend),
            "in_short_i18n": self._in_short_i18n(hero, related_plans, active, trend),
            "do_this_today": self._do_this_today(active, trend),
            "meta": {
                "wikipedia_url": hero.get("wikipedia_url") or "",
                "genre": hero.get("genre") or "",
                "developer": hero.get("developer") or "",
                "publisher": hero.get("publisher") or "",
                "confirmation": hero.get("confirmation") or hero.get("status") or "",
                "official_source": hero.get("official_source") or "",
                "release_label": annotate_product(hero).get("release_label") or "",
                "source": display_source(hero),
                "entry_date": hero.get("entry_date") or "",
                "last_checked": hero.get("last_checked") or (self.meta.get("last_checked") if self.meta else ""),
                "is_announced": is_announced,
                "franchise": hero.get("franchise") or "",
                "image_url": art.get("image_url") or "",
                "image_source": art.get("source") or "",
            },
            "catalog": {
                "sku_count": len(rows),
                "platforms": sorted({row.get("platform") or "Unknown" for row in rows}),
                "product_types": sorted({row.get("product_type") or "" for row in rows}),
                "earliest_release": min((row["release_date"] for row in rows if row.get("release_date")), default=""),
                "latest_release": max((row["release_date"] for row in rows if row.get("release_date")), default=""),
                "listings": siblings,
                "release_status": release_status,
            },
            "promotion": {
                "windows": synced_windows,
                "active_now": [self._sync_promo_window(plan, cross_media) for plan in active[:4]],
            },
            "cross_media": synced_media,
            "related_events": related_events[:16],
            "trends": trend,
            "content_marketing": content_kit_for_plans(related_plans[:10], perspective="product", limit=6),
        }

    def _sync_promo_window(self, plan: dict, cross_media: list[dict]) -> dict:
        """Align promote payload with matching cross-media/event runtime dates."""
        out = dict(plan)
        runtime_start = plan.get("runtime_start") or plan.get("event_start") or ""
        runtime_end = plan.get("runtime_end") or plan.get("event_end") or runtime_start
        match = next(
            (
                row
                for row in cross_media
                if (row.get("name") or "").lower() == (plan.get("event") or "").lower()
            ),
            None,
        )
        if match:
            runtime_start = match.get("start") or runtime_start
            runtime_end = match.get("end") or runtime_end
        live = next((phase for phase in plan.get("phases") or [] if phase.get("name") == "live"), None)
        if live:
            live = dict(live)
            live["start"] = runtime_start or live.get("start")
            live["end"] = runtime_end or live.get("end")
            phases = []
            for phase in plan.get("phases") or []:
                if phase.get("name") == "live":
                    phases.append(live)
                else:
                    phases.append(phase)
            out["phases"] = phases
        out["runtime_start"] = runtime_start
        out["runtime_end"] = runtime_end
        out["event_start"] = runtime_start
        out["event_end"] = runtime_end
        out["synced_with_cross_media"] = bool(match)
        if match:
            out["date_label"] = match.get("date_label") or out.get("date_label") or ""
            out["date_precision"] = match.get("date_precision") or out.get("date_precision") or ""
            if "exact_date" in match:
                out["exact_date"] = bool(match.get("exact_date"))
            out["confirmation"] = confirmation_kind(match)
            out["official_source"] = match.get("official_source") or out.get("official_source") or ""
        return out

    def _sync_cross_media(self, card: dict, plans: list[dict]) -> dict:
        out = dict(card)
        match = next(
            (
                plan
                for plan in plans
                if (plan.get("event") or "").lower() == (card.get("name") or "").lower()
            ),
            None,
        )
        if match:
            out["runtime_start"] = match.get("runtime_start") or match.get("event_start") or card.get("start")
            out["runtime_end"] = match.get("runtime_end") or match.get("event_end") or card.get("end")
            out["promo_start"] = match.get("promo_start") or ""
            out["promo_end"] = match.get("promo_end") or ""
            out["synced_with_promote"] = True
            # Prefer calendar runtime on the card itself.
            out["start"] = out["runtime_start"] or out.get("start")
            out["end"] = out["runtime_end"] or out.get("end")
        else:
            out["runtime_start"] = card.get("start") or ""
            out["runtime_end"] = card.get("end") or card.get("start") or ""
            out["promo_start"] = ""
            out["promo_end"] = ""
            out["synced_with_promote"] = False
        return out

    def _release_status(self, hero: dict) -> dict:
        release = hero.get("release_date") or ""
        today = date.today()
        is_announced = (hero.get("product_type") or "").lower() == "announced"
        confirmation = hero.get("confirmation") or hero.get("status") or ""
        tba = "tba" in confirmation.lower()
        days_until = None
        if len(release) >= 10:
            try:
                days_until = (date.fromisoformat(release[:10]) - today).days
            except ValueError:
                days_until = None
        announced = is_announced or "announc" in confirmation.lower()
        if tba:
            code = "announced_tba"
            label = "Announced · TBA planning window"
        elif days_until is not None and days_until >= 0:
            code = "announced_days"
            label = f"Announced · releases in {days_until} days"
        elif announced:
            code = "announced_not_catalog"
            label = "Announced · not yet in catalog"
        else:
            code = "in_catalog"
            label = "In catalog"
        return {
            "release_date": release,
            "days_until": days_until,
            "is_upcoming": bool(days_until is not None and days_until >= 0),
            "is_announced": announced,
            "is_tba": tba,
            "code": code,
            "label": label,
        }

    def _related_adaptations(self, title: str) -> list[dict]:
        keys = franchise_keys_for_text(title)
        if not keys:
            return []
        rows = []
        for row in self.adaptations:
            related = row.get("related_game") or ""
            name = row.get("ip_adaptation") or ""
            if keys & (franchise_keys_for_text(related) | franchise_keys_for_text(name)):
                rows.append(self._event_card(row))
        rows.sort(
            key=lambda row: (
                row.get("start", "") < date.today().isoformat(),
                row.get("start") or "9999",
            )
        )
        return unique_event_listings(rows)

    def _related_events(self, title: str) -> list[dict]:
        keys = franchise_keys_for_text(title)
        needle = _search_text(title)
        rows = []
        for row in self.events:
            related = row.get("related_game") or ""
            correlated = row.get("correlated_announced") or ""
            event_name = row.get("event") or ""
            if keys and keys & (
                franchise_keys_for_text(related)
                | franchise_keys_for_text(correlated)
                | franchise_keys_for_text(event_name)
            ):
                rows.append(self._event_card(row))
                continue
            if needle and (
                needle in _search_text(related)
                or needle in _search_text(correlated)
                or needle in _search_text(event_name)
            ):
                rows.append(self._event_card(row))
        rows.sort(
            key=lambda row: (
                row.get("start", "") < date.today().isoformat(),
                row.get("start") or "9999",
            )
        )
        return unique_event_listings(rows)

    def search_events(
        self,
        query: str,
        *,
        limit: int = 30,
        year: int | None = None,
        kind: str = "",
        mode: str = "",
    ) -> list[dict]:
        needle = _search_text(query)
        rows = self.events + self.adaptations
        scored: list[tuple[int, dict]] = []
        for row in rows:
            if year and not (row.get("start_date") or "").startswith(str(year)):
                continue
            if kind and (row.get("kind") or "event").lower() != kind.lower():
                continue
            if mode and (row.get("attendance_mode") or "").lower() != mode.lower():
                continue
            name = _search_text(row.get("event") or row.get("ip_adaptation") or "")
            related = _search_text(row.get("related_game") or "")
            blob = _search_text(
                f"{name} {related} {row.get('event_type') or ''} "
                f"{row.get('category') or ''} {row.get('medium') or ''} "
                f"{row.get('location') or ''} {row.get('attendance_mode') or ''} "
                f"{row.get('correlated_announced') or ''}"
            )
            if needle and needle not in blob:
                continue
            score = 50
            if needle and name.startswith(needle):
                score += 200
            elif needle and needle in name:
                score += 120
            start = row.get("start_date") or ""
            if "2026-07-01" <= start <= "2030-12-31":
                score += 40
            if "confirm" in (row.get("status") or row.get("confirmation") or "").lower():
                score += 20
            scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1].get("start_date") or ""))
        if needle:
            picked = [row for _, row in scored[:limit]]
        else:
            filtered = [row for _, row in scored]
            filtered.sort(key=lambda row: row.get("start_date") or "9999")
            if not year:
                filtered = [
                    row
                    for row in filtered
                    if (row.get("start_date") or "") >= date.today().isoformat()
                ]
            picked = filtered[:limit]
        return unique_event_listings([self._event_card(row) for row in picked])

    def archive_events(self, *, year: str = "") -> dict:
        """Worldwide gaming events with runtimes in 2022–2026."""
        years = ("2022", "2023", "2024", "2025", "2026")
        year_key = str(year or "").strip()[:4]
        rows: list[dict] = []
        for row in self.events:
            if not is_gaming_world_event(row):
                continue
            card = self._event_card(row)
            start = (card.get("start") or "")[:10]
            y = start[:4]
            if y not in years:
                continue
            if year_key in years and y != year_key:
                continue
            place = card.get("location") or card.get("country") or ""
            if card.get("country") and card.get("location") and card["country"] not in card["location"]:
                place = f"{card['location']} · {card['country']}"
            rows.append(
                {
                    "name": card.get("name") or "",
                    "year": y,
                    "runtime_start": start,
                    "runtime_end": (card.get("end") or start)[:10],
                    "date_label": card.get("date_label") or "",
                    "location": place,
                    "country": card.get("country") or "",
                    "type": card.get("type") or "",
                    "category": card.get("category") or "",
                    "attendance_mode": card.get("attendance_mode") or "",
                }
            )
        rows = unique_event_listings(rows)
        rows.sort(key=lambda item: (item.get("runtime_start") or "", item.get("name") or ""))
        grouped = []
        for y in years:
            if year_key in years and y != year_key:
                continue
            grouped.append({"year": y, "count": sum(1 for row in rows if row["year"] == y), "events": [row for row in rows if row["year"] == y]})
        return {
            "start_year": 2022,
            "end_year": 2026,
            "count": len(rows),
            "events": rows,
            "years": grouped,
        }

    def _event_card(self, row: dict) -> dict:
        name = row.get("event") or row.get("ip_adaptation") or ""
        art = _cover(name, "event")
        dated = annotate_event(row)
        return {
            "name": name,
            "kind": row.get("kind") or "event",
            "start": dated.get("runtime_start") or row.get("start_date") or "",
            "end": dated.get("runtime_end") or row.get("end_date") or "",
            "date_precision": dated.get("date_precision") or "day",
            "date_label": dated.get("date_label") or "",
            "exact_date": (dated.get("date_precision") or "day") == "day",
            "official_source": row.get("official_source") or "",
            "type": row.get("event_type") or row.get("medium") or "",
            "category": row.get("category") or "",
            "related": row.get("related_game") or "",
            "status": row.get("status") or row.get("date_status") or "",
            "confirmation": row.get("confirmation") or row.get("status") or row.get("date_status") or "",
            "wikipedia_url": row.get("wikipedia_url") or "",
            "source": display_source(row),
            "entry_date": row.get("entry_date") or "",
            "last_checked": row.get("last_checked") or "",
            "summary": row.get("summary") or "",
            "format": row.get("format") or row.get("medium") or "",
            "attendance_mode": row.get("attendance_mode") or "",
            "scope": row.get("scope") or "",
            "location": row.get("location") or "",
            "country": row.get("country") or "",
            "country_code": row.get("country_code") or "",
            "language": row.get("language") or "",
            "locale": row.get("locale") or "",
            "geos": [item for item in (row.get("geos") or "").split(",") if item],
            "organizer": row.get("organizer") or "",
            "release_channel": row.get("release_channel") or "",
            "correlated_announced": row.get("correlated_announced") or "",
            "image_url": art.get("image_url") or "",
            "image_source": art.get("source") or "",
        }

    def resolve_event(self, raw: str) -> dict | None:
        text = _search_text(raw)
        if not text:
            return None
        for row in self.events + self.adaptations:
            name = _search_text(row.get("event") or row.get("ip_adaptation") or "")
            if name == text:
                return row
        hits = self.search_events(raw, limit=1)
        if not hits:
            return None
        name = _search_text(hits[0]["name"])
        return next(
            (
                row
                for row in self.events + self.adaptations
                if _search_text(row.get("event") or row.get("ip_adaptation") or "") == name
            ),
            None,
        )

    def event_brief(
        self,
        raw: str,
        *,
        start_year: int | None = None,
        start_month: int | None = None,
        end_year: int | None = None,
        end_month: int | None = None,
    ) -> dict:
        row = self.resolve_event(raw)
        if not row:
            return {"found": False, "query": raw}
        name = row.get("event") or row.get("ip_adaptation") or ""
        today = date.today().isoformat()
        range_start, range_end = self._calendar_bounds(start_year, start_month, end_year, end_month)
        related_plans = [plan for plan in self.plans if (plan.get("event") or "").lower() == name.lower()]
        products = []
        seen: set[str] = set()
        exact_titles: list[str] = []
        for field in (row.get("correlated_announced"), row.get("related_game")):
            for title in re.split(r",|;", field or ""):
                title = title.strip()
                if title and title.lower() not in {t.lower() for t in exact_titles}:
                    exact_titles.append(title)
        for title in exact_titles:
            if title.lower() in seen:
                continue
            if title.lower() in self.by_title:
                seen.add(title.lower())
                products.append(self._title_card(title))
                continue
            hits = self.search_products(title, limit=1)
            if hits and (
                _search_text(hits[0]["canonical_title"]) == _search_text(title)
                or _search_text(title) in _search_text(hits[0]["canonical_title"])
            ):
                hit_title = hits[0]["canonical_title"]
                if hit_title.lower() not in seen:
                    seen.add(hit_title.lower())
                    products.append(hits[0])
        if row.get("source") != "announced_product_window":
            for plan in related_plans:
                title = plan.get("canonical_title") or ""
                if title and title.lower() not in seen:
                    seen.add(title.lower())
                    products.append(self._title_card(title))
        start = row.get("start_date") or ""
        end = row.get("end_date") or start
        live = bool(start and start <= today <= (end or start))
        status = row.get("status") or row.get("date_status") or row.get("confirmation") or ""
        kind_label = row.get("event_type") or row.get("medium") or "calendar"
        related = row.get("related_game") or ""
        start_nice = _nice_date(start)
        end_nice = _nice_date(end)
        status_display = status or "planning window"
        in_short_i18n = [
            {
                "key": "short.eventWindow",
                "params": {"name": name, "kind": kind_label, "start": start_nice, "end": end_nice},
                "text": f"{name} is a {kind_label} window from {start_nice} to {end_nice}.",
            },
            {
                "key": "short.relatedFranchises",
                "params": {"related": related or "not specified"},
                "text": f"Related franchises: {related or 'not specified'}.",
            },
            {
                "key": "short.eventConfirmation",
                "params": {"status": status_display},
                "text": f"Confirmation: {status_display}.",
            },
        ]
        geo_location = row.get("location") or ""
        geo_country = row.get("country") or ""
        geo_language = row.get("language") or ""
        if geo_country or geo_location:
            in_short_i18n.append(
                {
                    "key": "short.eventCountry",
                    "params": {
                        "location": geo_location or geo_country,
                        "country": geo_country or geo_location,
                        "language": geo_language or "Multiple",
                    },
                    "text": (
                        f"Host market: {geo_location or geo_country}"
                        + (f" · {geo_language}" if geo_language else "")
                        + "."
                    ),
                }
            )
        if row.get("correlated_announced"):
            in_short_i18n.append(
                {
                    "key": "short.correlatedAnnounced",
                    "params": {"titles": row["correlated_announced"]},
                    "text": f"Correlated announced products: {row['correlated_announced']}.",
                }
            )
        if live:
            in_short_i18n.append(
                {
                    "key": "short.windowLive",
                    "params": {},
                    "text": "This window is live today — merchandise the mapped catalog titles now.",
                }
            )
        elif start >= today:
            in_short_i18n.append(
                {
                    "key": "short.windowUpcoming",
                    "params": {},
                    "text": "The window is upcoming. Build the lead-in kit before the start date.",
                }
            )
        else:
            in_short_i18n.append(
                {
                    "key": "short.windowPast",
                    "params": {},
                    "text": "This window has passed; keep evergreen only if a sequel date is confirmed.",
                }
            )
        lines = [item["text"] for item in in_short_i18n]
        tactics = []
        if related_plans:
            tactics = (related_plans[0].get("phases") or [{}])[0].get("tactics") or []
        tactic_keys = None
        if not tactics:
            tactics = [
                "Feature the equivalent catalog SKUs for the full event runtime",
                "Do not treat this as a year-round homepage default",
            ]
            tactic_keys = ["action.tacticFeatureRuntime", "action.tacticNotYearRound"]
        announced_products = [
            product
            for product in products
            if "announc" in (product.get("confirmation") or "").lower()
            or "announced" in (product.get("product_types") or [])
        ][:12]
        related_releases = self._related_adaptations(row.get("related_game") or name)
        related_plans = self._filter_promo_windows(
            [self._sync_promo_window(plan, related_releases) for plan in related_plans],
            range_start=range_start,
            range_end=range_end,
        )
        related_releases = self._filter_promo_windows(
            [self._sync_cross_media(card, related_plans) for card in related_releases],
            range_start=range_start,
            range_end=range_end,
        )[:12]
        universe = superhero_universe_for_row(row)
        product_cap = 36 if universe else 12
        window_cap = 16 if universe else 8
        kit_limit = 16 if universe else 8
        synced_windows = related_plans[:window_cap]
        synced_releases = related_releases
        return {
            "found": True,
            "name": name,
            "kind": row.get("kind") or "event",
            "in_short": lines,
            "in_short_i18n": in_short_i18n,
            "do_this_today": {
                "headline": "Run mapped titles through this window." if live else f"{name} is dated {_nice_date(start)}.",
                "detail": row.get("summary") or row.get("related_game") or "",
                "tactics": tactics[:4],
                "i18n": (
                    {
                        "headline_key": "action.runMapped",
                        "headline_params": {},
                        "detail_key": None,
                        "tactic_keys": tactic_keys,
                    }
                    if live
                    else {
                        "headline_key": "action.eventDated",
                        "headline_params": {"name": name, "date": _nice_date(start)},
                        "detail_key": None,
                        "tactic_keys": tactic_keys,
                    }
                ),
            },
            "event": self._event_card(row),
            "markets": market_sections(row, products[:product_cap]),
            "products": products[:product_cap],
            "windows": synced_windows,
            "related_releases": synced_releases if row.get("kind") != "adaptation" else [],
            "announced_products": announced_products,
            "content_marketing": content_kit_for_plans(
                related_plans[: max(12, product_cap)],
                perspective="event",
                limit=kit_limit,
            ),
        }

    def featured_cross_sell_events(self, *, limit: int = 40) -> list[str]:
        return unique_events(self.plans, limit=limit)

    def cross_sell_brief(self, raw: str) -> dict:
        """Event name → catalog games and attach products to merchandise in that window."""
        row = self.resolve_event(raw)
        label = raw
        if row:
            label = row.get("event") or row.get("ip_adaptation") or raw
        payload = cross_sell_payload(label, plans=self.plans, calendar_row=row)
        if not payload.get("found"):
            # Still try fuzzy plan match with the raw query
            payload = cross_sell_payload(raw, plans=self.plans, calendar_row=row)
        if not payload.get("found"):
            return {"found": False, "query": raw}

        def enrich(plan: dict) -> dict:
            title = plan.get("canonical_title") or ""
            art = _cover(title, "product")
            out = {
                "canonical_title": title,
                "platform": plan.get("platform") or "",
                "product_type": plan.get("product_type") or "",
                "role": plan.get("role") or "",
                "offer": plan.get("offer") or "",
                "edition_year": plan.get("edition_year") or 0,
                "strategy_summary": plan.get("strategy_summary") or "",
                "promo_start": plan.get("promo_start") or "",
                "promo_end": plan.get("promo_end") or "",
                "runtime_start": plan.get("runtime_start") or plan.get("event_start") or payload.get("runtime_start") or "",
                "runtime_end": plan.get("runtime_end") or plan.get("event_end") or payload.get("runtime_end") or "",
                "phases": plan.get("phases") or [],
                "image_url": art.get("image_url") or "",
                "image_source": art.get("source") or "",
            }
            return out

        products = [enrich(plan) for plan in payload.get("products") or []]
        by_role = {
            role: [enrich(plan) for plan in rows]
            for role, rows in (payload.get("by_role") or {}).items()
        }
        hero = enrich(payload["hero"]) if payload.get("hero") else None
        event_card = self._event_card(row) if row else {
            "name": payload.get("name") or raw,
            "kind": payload.get("kind") or "event",
            "start": payload.get("runtime_start") or "",
            "end": payload.get("runtime_end") or "",
            "related": payload.get("related_game") or "",
            "image_url": _cover(payload.get("name") or raw, "event").get("image_url") or "",
        }
        # Sync runtime onto event card from payload
        event_card = dict(event_card)
        event_card["runtime_start"] = payload.get("runtime_start") or event_card.get("start") or ""
        event_card["runtime_end"] = payload.get("runtime_end") or event_card.get("end") or event_card["runtime_start"]
        event_card["promo_start"] = payload.get("promo_start") or ""
        event_card["promo_end"] = payload.get("promo_end") or ""

        return {
            "found": True,
            "query": raw,
            "name": payload.get("name") or raw,
            "kind": payload.get("kind") or "event",
            "in_short": payload.get("in_short") or [],
            "do_this_today": payload.get("do_this_today") or {},
            "event": event_card,
            "runtime_start": payload.get("runtime_start") or "",
            "runtime_end": payload.get("runtime_end") or "",
            "promo_start": payload.get("promo_start") or "",
            "promo_end": payload.get("promo_end") or "",
            "live_runtime": payload.get("live_runtime"),
            "live_promo": payload.get("live_promo"),
            "product_count": len(products),
            "game_count": sum(1 for row in products if row.get("role") == "game"),
            "attach_count": sum(1 for row in products if row.get("role") in {"currency", "dlc", "edition"}),
            "related_game": payload.get("related_game") or "",
            "hero": hero,
            "products": products,
            "markets": market_sections(row, products) if row else [],
            "by_role": by_role,
            "source": "cross_sell",
            "content_marketing": content_kit_for_plans(payload.get("products") or [], perspective="event", limit=8),
        }

    def calendar_range_brief(
        self,
        *,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        kind: str = "",
        precision: str = "",
        limit: int = 60,
    ) -> dict:
        """Month/year range → overlapping events plus promote and cross-sell products."""
        payload = calendar_range_payload(
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            events=self.events,
            adaptations=self.adaptations,
            plans=self.plans,
            kind=kind,
            precision=precision,
            limit=limit,
            products_per_event=8,
        )
        enriched_events = []
        range_plans: list[dict] = []
        for card in payload.get("events") or []:
            art = _cover(card.get("name"), "event")
            products = []
            event_name = card.get("name") or ""
            for product in card.get("products") or []:
                title = product.get("canonical_title") or ""
                part = _cover(title, "product")
                row = _public_social(
                    {**product, "image_url": part.get("image_url") or "", "image_source": part.get("source") or ""},
                    event_name,
                )
                products.append(row)
                range_plans.append(row)
            kit = content_kit_for_plans(products, perspective="event", limit=3)
            enriched_events.append(
                {
                    **card,
                    "image_url": art.get("image_url") or "",
                    "image_source": art.get("source") or "",
                    "products": products,
                    "content_marketing": kit,
                    "top_hashtags": ((kit.get("correlations") or [{}])[0].get("top_hashtags") or [])[:4],
                }
            )
        products_all = []
        seen: set[str] = set()
        for card in enriched_events:
            for product in card.get("products") or []:
                key = (product.get("canonical_title") or "").lower()
                if key and key not in seen:
                    seen.add(key)
                    products_all.append(product)
        return {
            **payload,
            "events": enriched_events,
            "products": products_all,
            "content_marketing": content_kit_for_plans(range_plans, perspective="event", limit=10),
            "source": "calendar_range",
        }

    def _in_short(self, hero: dict, plans: list[dict], active: list[dict], trend: dict | None) -> list[str]:
        return [row["text"] for row in self._in_short_i18n(hero, plans, active, trend)]

    def _in_short_i18n(self, hero: dict, plans: list[dict], active: list[dict], trend: dict | None) -> list[dict]:
        title = hero.get("canonical_title") or "This product"
        kind = hero.get("product_type") or "game"
        platform = hero.get("platform") or "its storefront"
        release = hero.get("release_date") or ""
        rows: list[dict] = [
            {
                "key": "short.listedAs",
                "params": {"title": title, "kind": kind, "platform": platform},
                "text": f"{title} is listed as a {kind} on {platform}.",
            }
        ]
        if release:
            nice = _nice_date(release)
            if release >= date.today().isoformat():
                rows.append(
                    {
                        "key": "short.releaseUpcoming",
                        "params": {"date": nice},
                        "text": f"The catalog release date is {nice}.",
                    }
                )
            else:
                rows.append(
                    {
                        "key": "short.releasePast",
                        "params": {"date": nice},
                        "text": f"It has been in the catalog since {nice}.",
                    }
                )
        else:
            rows.append(
                {
                    "key": "short.noRelease",
                    "params": {},
                    "text": "The catalog does not have a reliable release date for this listing.",
                }
            )
        if active:
            plan = active[0]
            start = _nice_date(plan["promo_start"])
            end = _nice_date(plan["promo_end"])
            rows.append(
                {
                    "key": "short.livePromo",
                    "params": {"event": plan["event"], "start": start, "end": end},
                    "text": (
                        f"It is inside a live promotion window for {plan['event']} "
                        f"({start} to {end})."
                    ),
                }
            )
        elif plans:
            future = [
                plan for plan in plans if (plan.get("promo_end") or "") >= date.today().isoformat()
            ]
            if future:
                nxt = min(future, key=lambda plan: plan.get("promo_start") or "9999")
                start = _nice_date(nxt["promo_start"])
                end = _nice_date(nxt["promo_end"])
                rows.append(
                    {
                        "key": "short.nextPromo",
                        "params": {"event": nxt["event"], "start": start, "end": end},
                        "text": f"The next planned window is {nxt['event']}, {start} to {end}.",
                    }
                )
            else:
                recent = max(plans, key=lambda plan: plan.get("promo_end") or "")
                start = _nice_date(recent["promo_start"])
                end = _nice_date(recent["promo_end"])
                rows.append(
                    {
                        "key": "short.recentPromo",
                        "params": {"event": recent["event"], "start": start, "end": end},
                        "text": (
                            f"The most recent mapped window was {recent['event']}, "
                            f"{start} to {end}."
                        ),
                    }
                )
        else:
            rows.append(
                {
                    "key": "short.noPromo",
                    "params": {},
                    "text": "There is no equivalent-event campaign on the calendar for this title.",
                }
            )
        if hero.get("wikipedia_url"):
            checked = hero.get("last_checked") or (self.meta or {}).get("last_checked") or "today"
            rows.append(
                {
                    "key": "short.wikiChecked",
                    "params": {"date": checked},
                    "text": f"Wikipedia/product page last checked {checked}.",
                }
            )
        if hero.get("confirmation"):
            rows.append(
                {
                    "key": "short.confirmation",
                    "params": {"status": hero["confirmation"]},
                    "text": f"Release confirmation: {hero['confirmation']}.",
                }
            )
        if trend:
            source = ", ".join(trend.get("sources") or [])
            rows.append(
                {
                    "key": "short.onPriority",
                    "params": {"sources": source},
                    "text": f"It is on today's merchandising priority list ({source}).",
                }
            )
        else:
            rows.append(
                {
                    "key": "short.offPriority",
                    "params": {},
                    "text": "It is not among today's trend-driven priorities.",
                }
            )
        return rows

    def _do_this_today(self, active: list[dict], trend: dict | None) -> dict:
        if trend and active:
            headline = "Feature it today — search interest and an event window overlap."
            detail = (trend.get("reasons") or [""])[0]
            tactics = trend.get("tactics") or (active[0].get("phases") or [{}])[0].get("tactics") or []
            i18n = {"headline_key": "action.featureOverlap", "headline_params": {}, "detail_key": None}
        elif trend:
            headline = "Feature it today while search interest is elevated."
            detail = (trend.get("reasons") or [""])[0]
            tactics = trend.get("tactics") or []
            i18n = {"headline_key": "action.featureTrend", "headline_params": {}, "detail_key": None}
        elif active:
            plan = active[0]
            headline = f"Run the {plan['event']} campaign — you are inside the promotion window."
            detail = plan.get("strategy_summary") or ""
            live = next((phase for phase in plan.get("phases") or [] if phase.get("name") == "live"), None)
            tactics = (live or (plan.get("phases") or [{}])[0]).get("tactics") or []
            i18n = {
                "headline_key": "action.runCampaign",
                "headline_params": {"event": plan["event"]},
                "detail_key": None,
            }
        else:
            headline = "No timed campaign today."
            detail = "Keep it on evergreen category rails unless a related headline appears."
            tactics = [
                "Do not homepage this SKU unless a matching trend or event appears",
                "If a related movie, match, or showcase breaks, re-run this lookup",
            ]
            i18n = {
                "headline_key": "action.noCampaign",
                "headline_params": {},
                "detail_key": "action.noCampaignDetail",
                "tactic_keys": ["action.tacticNoHomepage", "action.tacticRerun"],
            }
        return {"headline": headline, "detail": detail, "tactics": tactics[:4], "i18n": i18n}

    def _correlation_fields(self, row: dict) -> dict:
        dated = annotate_event(row)
        name = row.get("event") or row.get("ip_adaptation") or ""
        start = dated.get("runtime_start") or row.get("start_date") or row.get("runtime_start") or ""
        end = dated.get("runtime_end") or row.get("end_date") or row.get("runtime_end") or start
        return {
            "max_gmv_event": name,
            "max_gmv_event_gmv": 0.0,
            "max_gmv_event_type": row.get("event_type") or row.get("medium") or "",
            "max_gmv_event_start": (start or "")[:10],
            "max_gmv_event_end": (end or start or "")[:10],
        }

    def _with_correlated_event(
        self,
        product: dict,
        *,
        year: str | None = None,
        span: bool = False,
        with_years: bool = False,
        calendar: list[dict] | None = None,
        span_subset: list[dict] | None = None,
        span_keys: dict[str, list[dict]] | None = None,
        year_indexes: dict[str, tuple[list[dict], dict[str, list[dict]]]] | None = None,
    ) -> dict:
        calendar = calendar if calendar is not None else self.events + self.adaptations
        title = product.get("canonical_title") or ""
        around = product.get("best_week_start") or ""
        hero = (self.by_title.get(title.lower()) or [{}])[0]
        platform = hero.get("platform") or product.get("platform") or ""

        def _lookup(*, around_date: str, year_key: str | None, use_span: bool) -> dict | None:
            extra: dict = {}
            if use_span and span_subset is not None:
                extra = {"subset": span_subset, "events_by_key": span_keys}
            elif year_key and year_indexes and year_key in year_indexes:
                subset, keys = year_indexes[year_key]
                extra = {"subset": subset, "events_by_key": keys}
            return correlate_calendar_event(
                title,
                calendar,
                around=around_date,
                year=year_key,
                span=use_span,
                platform=platform,
                **extra,
            )

        if title and not product.get("max_gmv_event"):
            row = _lookup(around_date=around, year_key=year, use_span=span)
            if row:
                product.update(self._correlation_fields(row))
        if with_years:
            by_year = {str(item.get("year") or ""): dict(item) for item in product.get("year_max_events") or []}
            filled: list[dict] = []
            for year_key in ORDER_YEARS:
                item = by_year.get(year_key) or {
                    "year": year_key,
                    "max_gmv_event": "",
                    "max_gmv_event_gmv": 0.0,
                    "max_gmv_event_type": "",
                    "max_gmv_event_start": "",
                    "max_gmv_event_end": "",
                }
                if not item.get("max_gmv_event"):
                    row = _lookup(
                        around_date=around if around.startswith(year_key) else f"{year_key}-06-15",
                        year_key=year_key,
                        use_span=False,
                    )
                    if row:
                        item.update(self._correlation_fields(row))
                item["year"] = year_key
                filled.append(item)
            product["year_max_events"] = filled
        return product

    def _ensure_leader_event_names(self, orders: dict) -> dict:
        calendar = self.events + self.adaptations
        span_subset, span_keys = correlation_indexes(calendar, "2022-01-01", "2026-12-31")
        year_indexes = {
            year: correlation_indexes(calendar, f"{year}-01-01", f"{year}-12-31")
            for year in ORDER_YEARS
        }
        payload = dict(orders)
        payload["period_top_products"] = [
            self._with_correlated_event(
                dict(row),
                span=True,
                with_years=True,
                calendar=calendar,
                span_subset=span_subset,
                span_keys=span_keys,
                year_indexes=year_indexes,
            )
            for row in orders.get("period_top_products") or []
        ]
        years = []
        for block in orders.get("years") or []:
            year_block = dict(block)
            year = str(year_block.get("year") or "")
            year_block["top_products"] = [
                self._with_correlated_event(
                    dict(row),
                    year=year,
                    calendar=calendar,
                    year_indexes=year_indexes,
                )
                for row in block.get("top_products") or []
            ]
            years.append(year_block)
        payload["years"] = years
        return payload

    def dashboard(self) -> dict:
        today = date.today()
        dated = [row for row in self.catalog if row.get("release_date")]
        types = Counter(row.get("product_type") or "unknown" for row in self.catalog)
        platforms = Counter(row.get("platform") or "Unknown" for row in self.catalog)
        years = Counter((row.get("release_date") or "")[:4] for row in dated if row.get("release_date"))
        upcoming_months: Counter[str] = Counter()
        for row in dated:
            stamp = row["release_date"]
            if stamp >= today.isoformat():
                upcoming_months[stamp[:7]] += 1
        event_types = Counter(
            (row.get("event_type") or row.get("medium") or "other") for row in (self.events + self.adaptations)
        )
        event_modes = Counter(row.get("attendance_mode") or "unspecified" for row in self.events)
        event_scopes = Counter(row.get("scope") or "unspecified" for row in self.events)
        adaptation_formats = Counter(
            row.get("format") or row.get("medium") or "other" for row in self.adaptations
        )
        event_years = Counter(
            (row.get("start_date") or "")[:4]
            for row in self.events
            if "2026" <= (row.get("start_date") or "")[:4] <= "2030"
        )
        adaptation_years = Counter(
            (row.get("start_date") or "")[:4]
            for row in self.adaptations
            if "2026" <= (row.get("start_date") or "")[:4] <= "2030"
        )
        families = Counter(plan.get("promo_family") or "other" for plan in self.plans)
        active = plans_active_on(self.plans, today)
        horizon = today + timedelta(days=60)
        timeline = []
        for row in self.events + self.adaptations:
            start = row.get("start_date") or ""
            if start and today.isoformat() <= start <= horizon.isoformat():
                timeline.append(
                    {
                        "start": start,
                        "end": row.get("end_date") or start,
                        "name": row.get("event") or row.get("ip_adaptation") or "",
                        "kind": row.get("kind") or "event",
                        "type": row.get("event_type") or row.get("medium") or "",
                        "related": row.get("related_game") or "",
                    }
                )
        timeline.sort(key=lambda item: item["start"])
        timeline = unique_event_listings(timeline)[:18]
        google = [
            {
                "geo": row.get("geo"),
                "title": row.get("title"),
                "traffic_label": row.get("traffic_label"),
                "news": (row.get("news") or [None])[0],
            }
            for row in (self.bundle.get("google_trends") or [])[:20]
        ]
        wiki = [
            {
                "article": row.get("article"),
                "spike_ratio": row.get("spike_ratio"),
                "views": row.get("views"),
                "as_of": row.get("as_of"),
            }
            for row in (self.bundle.get("wikipedia") or [])[:12]
        ]
        live_windows = []
        seen_events: set[str] = set()
        calendar_by_name: dict[str, dict] = {}
        for row in self.events + self.adaptations:
            name = (row.get("event") or row.get("ip_adaptation") or "").strip().lower()
            if name and name not in calendar_by_name:
                calendar_by_name[name] = row
        for plan in active:
            event = plan.get("event") or ""
            if not event or is_quarter_timeframe(event) or event in seen_events:
                continue
            seen_events.add(event)
            cal = calendar_by_name.get(event.strip().lower()) or {}
            dated = annotate_event(cal) if cal else {}
            start = (
                dated.get("runtime_start")
                or plan.get("runtime_start")
                or plan.get("event_start")
                or ""
            )
            end = (
                dated.get("runtime_end")
                or plan.get("runtime_end")
                or plan.get("event_end")
                or start
            )
            precision = dated.get("date_precision") or plan.get("date_precision") or "day"
            live_windows.append(
                {
                    "event": event,
                    "family": plan.get("promo_family") or "",
                    "promo_start": plan.get("promo_start") or "",
                    "promo_end": plan.get("promo_end") or "",
                    "title": plan.get("canonical_title") or "",
                    "start": start,
                    "end": end,
                    "date_label": dated.get("date_label") or plan.get("date_label") or "",
                    "date_precision": precision,
                    "exact_date": precision == "day",
                    "confirmation": confirmation_kind(cal or plan),
                    "official_source": cal.get("official_source") or plan.get("official_source") or "",
                }
            )
        return {
            "as_of": today.isoformat(),
            "kpis": {
                "catalog_skus": len(self.catalog),
                "unique_titles": len(self.by_title),
                "events": len(self.events),
                "adaptations": len(self.adaptations),
                "promotion_plans": len(self.plans),
                "active_windows_today": len(seen_events),
                "trend_priorities": len(self.priorities),
                "announced_games": sum(1 for row in self.catalog if row.get("product_type") == "announced"),
                "last_checked": (self.meta or {}).get("last_checked") or today.isoformat(),
                "horizon": "2026–2030",
                "correlated_events": (self.meta or {}).get("correlated_events") or sum(
                    1 for row in self.events if row.get("correlated_announced")
                ),
                "announced_tba": (self.meta or {}).get("announced_tba")
                or sum(1 for row in self.catalog if "tba" in (row.get("confirmation") or "").lower()),
                "artwork_products": (self.meta or {}).get("artwork_products")
                or len((load_artwork().get("products") or {})),
                "artwork_events": (self.meta or {}).get("artwork_events")
                or len((load_artwork().get("events") or {})),
                "daily_changes": len(load_changes()),
                "rag_documents": (load_rag_meta() or {}).get("document_count") or 0,
            },
            "meta": self.meta or {},
            "recent_changes": [
                change
                for change in load_changes()
                if not is_quarter_timeframe(change.get("title") or "")
            ][:12],
            "rag": load_rag_meta(),
            "live_windows": live_windows[:12],
            "product_types": types.most_common(8),
            "platforms": platforms.most_common(10),
            "release_years": sorted((year, count) for year, count in years.items() if year >= "2018"),
            "upcoming_months": sorted(upcoming_months.items())[:14],
            "event_types": event_types.most_common(12),
            "event_modes": event_modes.most_common(),
            "event_scopes": event_scopes.most_common(),
            "adaptation_formats": adaptation_formats.most_common(14),
            "event_years": sorted(event_years.items()),
            "adaptation_years": sorted(adaptation_years.items()),
            "promo_families": families.most_common(),
            "timeline": timeline,
            "upcoming_adaptations": unique_event_listings(
                [
                    self._event_card(row)
                    for row in sorted(
                        (
                            row
                            for row in self.adaptations
                            if (row.get("end_date") or row.get("start_date") or "")
                            >= today.isoformat()
                        ),
                        key=lambda row: row.get("start_date") or "9999",
                    )
                ]
            )[:18],
            "upcoming_announced": [
                self._title_card(title)
                for title in [
                    row.get("canonical_title") or ""
                    for row in sorted(
                        (
                            row
                            for row in self.catalog
                            if (row.get("release_date") or "") >= today.isoformat()
                            and (
                                row.get("product_type") == "announced"
                                or "announc" in (row.get("confirmation") or "").lower()
                                or row.get("source") == "announced_registry"
                            )
                        ),
                        key=lambda row: row.get("release_date") or "9999",
                    )
                ]
                if title
            ][:24],
            "correlated_event_sample": unique_event_listings(
                [
                    self._event_card(row)
                    for row in sorted(
                        (row for row in self.events if row.get("correlated_announced")),
                        key=lambda row: row.get("start_date") or "9999",
                    )
                ]
            )[:16],
            "priorities": [
                {
                    "rank": item.get("rank"),
                    "canonical_title": item.get("canonical_title"),
                    "score": item.get("score"),
                    "sources": item.get("sources"),
                    "reasons": (item.get("reasons") or [])[:1],
                }
                for item in self.priorities[:12]
            ],
            "google_trends": google,
            "wikipedia": wiki,
            "orders": self._ensure_leader_event_names(load_order_dashboard()),
        }

    def trends_analysis(self) -> dict:
        """Series payloads for the Trends and Traffic analysis pages."""
        google = list(self.bundle.get("google_trends") or [])
        wiki = list(self.bundle.get("wikipedia") or [])
        placement = placement_payload(self.events, self.adaptations, self.plans)
        by_geo: Counter[str] = Counter()
        traffic_rows = []
        for row in google:
            geo = row.get("geo") or "??"
            traffic = int(row.get("traffic") or 0)
            by_geo[geo] += traffic
            traffic_rows.append(
                {
                    "label": row.get("title") or "",
                    "geo": geo,
                    "traffic": traffic,
                    "traffic_label": row.get("traffic_label") or "",
                    "news": (row.get("news") or [None])[0] or "",
                }
            )
        traffic_rows.sort(key=lambda row: row["traffic"], reverse=True)
        wiki_rows = [
            {
                "label": row.get("article") or "",
                "views": int(row.get("views") or 0),
                "spike_ratio": float(row.get("spike_ratio") or 0),
                "as_of": row.get("as_of") or "",
            }
            for row in wiki
        ]
        wiki_rows.sort(key=lambda row: row["views"], reverse=True)
        priority_rows = []
        for item in self.priorities[:20]:
            title = item.get("canonical_title") or ""
            art = _cover(title, "product")
            priority_rows.append(
                {
                    "rank": item.get("rank"),
                    "canonical_title": title,
                    "score": item.get("score") or 0,
                    "sources": item.get("sources") or [],
                    "reasons": (item.get("reasons") or [])[:2],
                    "image_url": art.get("image_url") or "",
                }
            )
        return {
            "as_of": date.today().isoformat(),
            "kpis": {
                "google_topics": len(google),
                "wikipedia_spikes": len(wiki),
                "priority_titles": len(self.priorities),
                "total_google_traffic": sum(row["traffic"] for row in traffic_rows),
                "total_wiki_views": sum(row["views"] for row in wiki_rows),
                "geographies": len(placement["tracked_geos"]),
                "placement_events": sum(
                    row["event_count"] for row in placement["placements"].values()
                ),
                "placement_products": sum(
                    row["product_count"] for row in placement["placements"].values()
                ),
            },
            "has_google": bool(google),
            "filter": self.bundle.get("filter") or {},
            "google_by_geo": sorted(by_geo.items(), key=lambda item: -item[1]),
            "google_top": traffic_rows[:18],
            "wikipedia_top": wiki_rows[:18],
            "priority_scores": priority_rows,
            "geo_placement": placement,
            "source_mix": [
                ("Google Trends", len(google)),
                ("Wikipedia pageviews", len(wiki)),
                ("Merchandising priorities", len(self.priorities)),
            ],
        }


@lru_cache(maxsize=1)
def get_store() -> FloorStore:
    store = FloorStore()
    store.load()
    return store
