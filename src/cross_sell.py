"""Event → cross-sell products for the event timeframe.

Notebook 04 and the Floor Brief Cross-sell page share this module:
enter an event / entertainment release name and return the catalog games
and attach products that should be merchandised during that window.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from src.calendar_dedupe import canonical_event_name, is_quarter_timeframe


ROLE_ORDER = ("game", "currency", "dlc", "edition", "other")


ROLE_ORDER = ("game", "currency", "dlc", "edition", "other")


def _norm(value: str) -> str:
    return " ".join((value or "").lower().split())


def plans_for_event(plans: list[dict], event_name: str) -> list[dict]:
    """Exact and fuzzy match of promotion plans to an event label."""
    needle = _norm(event_name)
    if not needle:
        return []
    exact = [plan for plan in plans if _norm(plan.get("event") or "") == needle]
    if exact:
        return exact
    # Substring / containment (e.g. "World Cup" → FIFA Women's World Cup)
    fuzzy = [
        plan
        for plan in plans
        if needle in _norm(plan.get("event") or "") or _norm(plan.get("event") or "") in needle
    ]
    if fuzzy:
        return fuzzy
    # Also match related_game field when the user types a franchise near the event
    related = [
        plan
        for plan in plans
        if needle in _norm(plan.get("related_game") or "")
        or any(needle in _norm(q) for q in (plan.get("queries") or []))
    ]
    return related


def unique_events(plans: list[dict], *, limit: int = 40) -> list[str]:
    """Distinct event labels that already have cross-sell plans, soonest first."""
    today = date.today().isoformat()
    seen: set[tuple[str, str]] = set()
    upcoming: list[tuple[str, str]] = []
    past: list[tuple[str, str]] = []
    for plan in plans:
        event = plan.get("event") or ""
        start = plan.get("runtime_start") or plan.get("event_start") or plan.get("promo_start") or ""
        key = (canonical_event_name(event), (start or "")[:4])
        if not event or is_quarter_timeframe(event) or key in seen or not key[0]:
            continue
        if (start or "")[:10] < "2026-01-01":
            continue
        seen.add(key)
        bucket = upcoming if start >= today else past
        bucket.append((start or "9999", event))
    upcoming.sort()
    past.sort(reverse=True)
    ordered = [name for _, name in upcoming] + [name for _, name in past]
    return ordered[:limit]


def cross_sell_payload(
    event_name: str,
    *,
    plans: list[dict],
    calendar_row: dict | None = None,
) -> dict:
    """Build the notebook / API payload for one event lookup."""
    matched = plans_for_event(plans, event_name)
    if not matched and not calendar_row:
        return {"found": False, "query": event_name, "products": [], "by_role": {}}

    label = (
        (calendar_row.get("event") or calendar_row.get("ip_adaptation") if calendar_row else None)
        or (matched[0].get("event") if matched else event_name)
        or event_name
    )
    # Prefer plans that exactly match the resolved calendar label
    if calendar_row and matched:
        exact = [plan for plan in matched if _norm(plan.get("event") or "") == _norm(label)]
        if exact:
            matched = exact

    runtime_start = ""
    runtime_end = ""
    promo_start = ""
    promo_end = ""
    if calendar_row:
        runtime_start = calendar_row.get("start_date") or ""
        runtime_end = calendar_row.get("end_date") or runtime_start
    if matched:
        runtime_start = runtime_start or matched[0].get("runtime_start") or matched[0].get("event_start") or ""
        runtime_end = runtime_end or matched[0].get("runtime_end") or matched[0].get("event_end") or runtime_start
        promo_start = min((plan.get("promo_start") or "9999" for plan in matched), default="")
        promo_end = max((plan.get("promo_end") or "" for plan in matched), default="")
        if promo_start == "9999":
            promo_start = ""

    today = date.today().isoformat()
    live = bool(runtime_start and runtime_start <= today <= (runtime_end or runtime_start))
    in_promo = bool(promo_start and promo_start <= today <= (promo_end or promo_start))

    # Deduplicate products: keep richest plan per title (prefer game role, then newest edition)
    by_title: dict[str, dict] = {}
    for plan in matched:
        title = plan.get("canonical_title") or plan.get("product_title") or ""
        if not title:
            continue
        key = title.lower()
        prior = by_title.get(key)
        score = (
            ROLE_ORDER.index(plan.get("role") or "other")
            if (plan.get("role") or "other") in ROLE_ORDER
            else 99,
            -(plan.get("edition_year") or 0),
        )
        if prior is None:
            by_title[key] = plan
            continue
        prior_score = (
            ROLE_ORDER.index(prior.get("role") or "other")
            if (prior.get("role") or "other") in ROLE_ORDER
            else 99,
            -(prior.get("edition_year") or 0),
        )
        if score < prior_score:
            by_title[key] = plan

    products = sorted(
        by_title.values(),
        key=lambda plan: (
            ROLE_ORDER.index(plan.get("role") or "other")
            if (plan.get("role") or "other") in ROLE_ORDER
            else 99,
            -(plan.get("edition_year") or 0),
            plan.get("canonical_title") or "",
        ),
    )

    by_role: dict[str, list[dict]] = defaultdict(list)
    for plan in products:
        by_role[plan.get("role") or "other"].append(plan)

    hero = next((plan for plan in products if plan.get("role") == "game"), products[0] if products else None)
    attach = [plan for plan in products if plan.get("role") in {"currency", "dlc", "edition"}]
    related_game = (
        (calendar_row or {}).get("related_game")
        or (matched[0].get("related_game") if matched else "")
        or ""
    )
    display_products = products[:36]

    lines = [
        f"{label} runs {runtime_start or 'TBA'} → {runtime_end or runtime_start or 'TBA'}.",
        f"Cross-sell clock (lead-in through afterglow): {promo_start or '—'} → {promo_end or '—'}.",
        f"Mapped catalog titles: {len(products)} ({sum(1 for p in products if p.get('role') == 'game')} games, {len(attach)} attach).",
    ]
    if related_game:
        lines.append(f"Franchise / related IP: {related_game}.")
    if live:
        lines.append("Event runtime is live today — feature hero SKUs on the homepage.")
    elif in_promo:
        lines.append("Inside the promo window (lead-in or afterglow) — stage kits now.")
    elif promo_start and promo_start > today:
        lines.append("Window is upcoming — prepare cross-sell kits before lead-in.")
    else:
        lines.append("Window has passed — keep evergreen only if a sequel date is confirmed.")

    return {
        "found": True,
        "query": event_name,
        "name": label,
        "kind": (calendar_row or {}).get("kind") or (matched[0].get("event_kind") if matched else "event"),
        "related_game": related_game,
        "runtime_start": runtime_start,
        "runtime_end": runtime_end or runtime_start,
        "promo_start": promo_start,
        "promo_end": promo_end,
        "live_runtime": live,
        "live_promo": in_promo,
        "product_count": len(products),
        "game_count": sum(1 for plan in products if plan.get("role") == "game"),
        "attach_count": len(attach),
        "in_short": lines,
        "do_this_today": {
            "headline": (
                f"Cross-sell {hero['canonical_title']} through {label}."
                if hero
                else f"No catalog match yet for {label}."
            ),
            "detail": (hero or {}).get("strategy_summary") or related_game or "",
            "tactics": (
                ((hero or {}).get("phases") or [{}])[0].get("tactics")
                or [
                    "Feature equivalent catalog games for the full event runtime",
                    "Attach currency / DLC under the hero SKU",
                    "Do not leave this as a year-round homepage default",
                ]
            )[:4],
        },
        "hero": hero,
        "products": display_products,
        "by_role": {
            role: (by_role.get(role, [])[:24])
            for role in ROLE_ORDER
            if by_role.get(role)
        },
        "plans": matched[:40],
    }


def format_cross_sell_table(payload: dict) -> str:
    """Plain-text table for notebook display."""
    if not payload.get("found"):
        return f"No cross-sell match for “{payload.get('query') or ''}”."
    lines = [
        f"Event: {payload['name']}",
        f"Runtime: {payload.get('runtime_start')} → {payload.get('runtime_end')}",
        f"Promo window: {payload.get('promo_start')} → {payload.get('promo_end')}",
        "",
        f"{'role':10} {'product':42} {'platform':12} {'offer'}",
        "-" * 100,
    ]
    for plan in payload.get("products") or []:
        lines.append(
            f"{(plan.get('role') or '')[:10]:10} "
            f"{(plan.get('canonical_title') or '')[:42]:42} "
            f"{(plan.get('platform') or '')[:12]:12} "
            f"{plan.get('offer') or ''}"
        )
    return "\n".join(lines)
