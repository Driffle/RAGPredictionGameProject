"""Daily refresh: datasets, audits, RAG retrain, and trend brief.

Usage (from the project root):

    python3 -m src.daily_brief
    python3 -m src.daily_brief --refresh
"""

from __future__ import annotations

import argparse
from datetime import date

from src.audit_changes import load_changes
from src.database import refresh_live_database
from src.documents import load_rag_meta
from src.load_data import load_adaptations, load_catalog, load_events
from src.priorities import (
    cache_is_fresh,
    filter_trend_bundle,
    load_cached_brief,
    rank_daily_priorities,
    save_daily_brief,
)
from src.promote import build_plans
from src.trends import collect_trend_bundle


def run(*, refresh: bool = False, on: date | None = None, fetch: bool = True) -> dict:
    """Full daily pipeline.

    When refresh=True (the launchd path): rebuild product/event datasets, run
    date-change audits, retrain the RAG index, then refresh trends.
    """
    day = on or date.today()
    db_meta: dict = {}
    if refresh:
        try:
            db_meta = refresh_live_database(fetch=fetch)
            print(
                "datasets refreshed · "
                f"events={db_meta.get('events')} announced={db_meta.get('announced_games')} "
                f"plans={db_meta.get('promotion_plans')} "
                f"changes={((db_meta.get('audit') or {}).get('change_count') or 0)} "
                f"rag={((db_meta.get('rag') or {}).get('document_count') or 0)}"
            )
        except Exception as exc:
            print(f"live database refresh skipped: {exc}")

    catalog = load_catalog(games_only=True, drop_placeholder_dates=True)
    events = load_events()
    adaptations = load_adaptations()
    plans = build_plans(events, adaptations, catalog)

    order_meta: dict = {}
    if refresh:
        try:
            from src.orders import write_order_datasets

            order_meta = write_order_datasets(events=events)
            print(
                "orders · "
                f"skus={order_meta.get('orders')} matched={order_meta.get('matched_skus')} "
                f"events={order_meta.get('events_with_peak_gmv')}"
            )
        except FileNotFoundError as exc:
            print(f"orders skipped: {exc}")

    if not refresh and cache_is_fresh(day):
        cached = load_cached_brief(day)
        if cached:
            bundle, _ = cached
            bundle = filter_trend_bundle(catalog, events + adaptations, bundle)
            priorities = rank_daily_priorities(catalog, plans, bundle, on=day)
            folder = save_daily_brief(bundle, priorities, day)
            return {
                "bundle": bundle,
                "priorities": priorities,
                "cached": True,
                "folder": str(folder),
                "database": db_meta,
                "changes": load_changes(day),
                "rag": load_rag_meta(),
                "orders": order_meta,
            }

    bundle = collect_trend_bundle(as_of=day)
    bundle = filter_trend_bundle(catalog, events + adaptations, bundle)
    priorities = rank_daily_priorities(catalog, plans, bundle, on=day)
    folder = save_daily_brief(bundle, priorities, day)
    return {
        "bundle": bundle,
        "priorities": priorities,
        "cached": False,
        "folder": str(folder),
        "database": db_meta,
        "changes": load_changes(day),
        "rag": load_rag_meta(),
        "orders": order_meta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily dataset refresh, audits, RAG retrain, and marketing brief"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild product/event datasets, run audits, retrain RAG, refetch trends",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Rebuild from local seeds without live Wikipedia/Wikidata fetches",
    )
    args = parser.parse_args()
    result = run(refresh=args.refresh, fetch=not args.offline)
    print(f"{'cached' if result['cached'] else 'fetched'} → {result['folder']}")
    rag = result.get("rag") or {}
    if rag:
        print(f"RAG index · docs={rag.get('document_count')} trained={rag.get('trained')} as_of={rag.get('as_of')}")
    changes = result.get("changes") or []
    if changes:
        print(f"Daily changes · {len(changes)}")
        for row in changes[:8]:
            print(f"  [{row.get('change_type')}] {row.get('title')}: {row.get('detail')}")
    for item in result["priorities"][:10]:
        print(f"{item['rank']:2}. {item['canonical_title'][:48]:48}  {','.join(item['sources'])}")


if __name__ == "__main__":
    main()
