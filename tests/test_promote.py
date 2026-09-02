from __future__ import annotations

import unittest
from datetime import date

from src.date_range import range_span
from src.promote import (
    build_plans,
    correlate_calendar_event,
    products_for_event,
    recommended_games_for_event,
)
from src.store import FloorStore


def _event(name: str, start: str, end: str, **extra) -> dict:
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    row = {
        "kind": extra.get("kind", "event"),
        "event": name,
        "start_date": start,
        "end_date": end,
        "start_date_parsed": start_d,
        "end_date_parsed": end_d,
        "event_type": extra.get("event_type", "Gaming Expo"),
        "related_game": extra.get("related_game", "Multi-platform"),
        "category": extra.get("category", "Gaming"),
    }
    row.update(extra)
    return row


def _product(title: str, **extra) -> dict:
    release = extra.get("release_date", "2026-09-01")
    parsed = date.fromisoformat(release) if release else None
    row = {
        "canonical_title": title,
        "product_title": title,
        "product_type": extra.get("product_type", "game"),
        "platform": extra.get("platform", "Steam"),
        "release_date": release,
        "release_date_parsed": parsed,
        "product_id": title.lower().replace(" ", "-"),
    }
    row.update(extra)
    row["release_date_parsed"] = parsed
    return row


class PromoteCoverageTests(unittest.TestCase):
    def test_generic_expo_gets_at_least_ten_games(self) -> None:
        events = [_event("Gamescom", "2026-08-26", "2026-08-30")]
        catalog = [
            _product(f"Expo Game {index:02d}", platform="Steam", release_date=f"2026-0{(index % 8) + 1}-{(index % 27) + 1:02d}")
            for index in range(1, 16)
        ]
        titles = [row["canonical_title"] for row in recommended_games_for_event(events[0], catalog, limit=10)]
        self.assertGreaterEqual(len(titles), 10)

    def test_generic_expo_gets_a_catalog_product(self) -> None:
        events = [_event("Gamescom", "2026-08-26", "2026-08-30")]
        catalog = [_product("Fable", platform="Xbox Series X/S", release_date="2026-09-01")]
        products = products_for_event(events[0], catalog)
        self.assertTrue(products)
        self.assertEqual(products[0]["canonical_title"], "Fable")

    def test_every_event_and_product_is_mapped(self) -> None:
        events = [
            _event("Gamescom", "2026-08-26", "2026-08-30"),
            _event("Steam Next Fest", "2026-10-13", "2026-10-20", event_type="Digital Festival"),
            _event("Nintendo Direct", "2026-06-18", "2026-06-18", related_game="Nintendo franchises"),
        ]
        catalog = [
            _product("Fable", platform="Xbox Series X/S", release_date="2026-09-01"),
            _product("Hades II", platform="Steam", release_date="2026-10-15"),
            _product("Super Mario Bros. Wonder", platform="Nintendo Switch", release_date="2023-10-20"),
        ]
        plans = build_plans(events, [], catalog)
        event_names = {plan["event"] for plan in plans}
        titles = {plan["canonical_title"] for plan in plans}
        self.assertIn("Gamescom", event_names)
        self.assertIn("Steam Next Fest", event_names)
        self.assertIn("Nintendo Direct", event_names)
        self.assertIn("Fable", titles)
        self.assertIn("Hades II", titles)
        self.assertIn("Super Mario Bros. Wonder", titles)

    def test_state_of_play_recommends_sie_not_third_party(self) -> None:
        events = [_event("PlayStation State of Play September 2026", "2026-09-03", "2026-09-03", related_game="Final Fantasy VII Revelation")]
        catalog = [
            _product("Final Fantasy VII Rebirth", publisher="Square Enix", platform="PSN", release_date="2024-02-29"),
            _product("God of War Ragnarök", publisher="Sony Interactive Entertainment", platform="PSN", release_date="2022-11-09"),
            _product("Marvel's Spider-Man 2", publisher="Sony Interactive Entertainment", platform="PSN", release_date="2023-10-20"),
            _product("Fable", publisher="Xbox Game Studios", platform="Xbox Series X/S", release_date="2026-09-01"),
        ]
        products = products_for_event(events[0], catalog)
        titles = {row["canonical_title"] for row in products}
        self.assertIn("God of War Ragnarök", titles)
        self.assertIn("Marvel's Spider-Man 2", titles)
        self.assertNotIn("Final Fantasy VII Rebirth", titles)
        self.assertNotIn("Fable", titles)

    def test_state_of_play_keeps_every_sie_game_not_just_one_franchise(self) -> None:
        events = [_event("PlayStation State of Play September 2026", "2026-09-03", "2026-09-03")]
        catalog = [
            _product("God of War Ragnarök", publisher="Sony Interactive Entertainment", release_date="2022-11-09"),
            _product("God of War Ragnarok - Digital Deluxe Edition Upgrade DLC", publisher="Sony Interactive Entertainment", product_type="dlc", release_date="2024-09-19"),
            _product("Marvel's Wolverine", publisher="Sony Interactive Entertainment", product_type="announced", release_date="2026-09-15"),
            _product("Ghost of Yōtei", publisher="Sony Interactive Entertainment", release_date="2025-10-02"),
            _product("Death Stranding 2: On the Beach", publisher="Sony Interactive Entertainment", release_date="2025-06-26"),
            _product("Intergalactic: The Heretic Prophet", publisher="Sony Interactive Entertainment", product_type="announced", release_date="2028-01-01"),
        ]
        titles = [row["canonical_title"] for row in recommended_games_for_event(events[0], catalog, limit=10)]
        self.assertEqual(len(titles), 5)
        self.assertIn("Marvel's Wolverine", titles)
        self.assertIn("Ghost of Yōtei", titles)
        self.assertIn("Death Stranding 2: On the Beach", titles)
        self.assertIn("Intergalactic: The Heretic Prophet", titles)
        self.assertNotIn("God of War Ragnarok - Digital Deluxe Edition Upgrade DLC", titles)

    def test_nintendo_direct_recommends_nintendo_published(self) -> None:
        events = [_event("Nintendo Direct June 2026", "2026-06-09", "2026-06-09")]
        catalog = [
            _product("Super Mario Bros. Wonder", publisher="Nintendo", platform="Nintendo Switch", release_date="2023-10-20"),
            _product("Fortnite", publisher="Epic Games", platform="Nintendo Switch", release_date="2017-07-25"),
        ]
        titles = {row["canonical_title"] for row in products_for_event(events[0], catalog)}
        self.assertIn("Super Mario Bros. Wonder", titles)
        self.assertNotIn("Fortnite", titles)

    def test_partner_showcase_is_not_forced_first_party(self) -> None:
        events = [_event("Nintendo Direct: Partner Showcase July 2025", "2025-07-31", "2025-07-31")]
        catalog = [
            _product("Just Dance 2026 Edition", publisher="Ubisoft", platform="Nintendo Switch", release_date="2025-10-14"),
            _product("Super Mario Bros. Wonder", publisher="Nintendo", platform="Nintendo Switch", release_date="2023-10-20"),
        ]
        titles = {row["canonical_title"] for row in products_for_event(events[0], catalog)}
        self.assertTrue(titles)

    def test_xbox_showcase_recommends_xbox_game_studios(self) -> None:
        events = [_event("Xbox Games Showcase 2026", "2026-06-07", "2026-06-07")]
        catalog = [
            _product("Forza Horizon 6", publisher="Xbox Game Studios", platform="Xbox Series X/S", release_date="2026-05-19"),
            _product("Call of Duty: Modern Warfare 4", publisher="Activision", platform="Xbox Series X/S", release_date="2026-10-23"),
        ]
        titles = {row["canonical_title"] for row in products_for_event(events[0], catalog)}
        self.assertIn("Forza Horizon 6", titles)
        self.assertNotIn("Call of Duty: Modern Warfare 4", titles)

    def test_correlate_keeps_year_and_prefers_franchise(self) -> None:
        events = [
            _event("Gamescom 2022", "2022-08-24", "2022-08-28"),
            _event(
                "FIFA World Cup",
                "2022-11-20",
                "2022-12-18",
                event_type="Football",
                category="Sports",
                related_game="FIFA",
            ),
            _event("Gamescom 2024", "2024-08-21", "2024-08-25"),
            _event("Steam Next Fest", "2026-10-13", "2026-10-20", event_type="Digital Festival"),
        ]
        world_cup = correlate_calendar_event("FIFA 22", events, year="2022", around="2022-11-25")
        self.assertIsNotNone(world_cup)
        self.assertEqual(world_cup["event"], "FIFA World Cup")
        year_2024 = correlate_calendar_event("Minecraft", events, year="2024")
        self.assertIsNotNone(year_2024)
        self.assertEqual(year_2024["event"], "Gamescom 2024")
        period = correlate_calendar_event("Minecraft", events, around="2024-08-22", span=True)
        self.assertIsNotNone(period)
        self.assertEqual(period["event"], "Gamescom 2024")
        self.assertTrue((period["start_date"] or "")[:4] >= "2022")
        self.assertTrue((period["start_date"] or "")[:4] <= "2026")

    def test_unrelated_series_is_not_used_as_fallback(self) -> None:
        events = [
            _event("Gamescom 2024", "2024-08-21", "2024-08-25"),
            _event(
                "Pokémon Horizons: The Series",
                "2023-04-14",
                "2024-03-29",
                kind="adaptation",
                event_type="Anime Series",
                category="OTT / Anime",
                related_game="Pokémon",
            ),
            _event(
                "The Super Mario Galaxy Movie Direct",
                "2025-11-12",
                "2025-11-12",
                event_type="Digital Showcase",
                category="Gaming / Movies",
                related_game="Mario",
            ),
        ]
        hit = correlate_calendar_event("Helldivers 2", events, year="2024", around="2024-02-08")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["event"], "Gamescom 2024")
        period = correlate_calendar_event("ARC Raiders", events, around="2025-10-30", span=True)
        self.assertIsNotNone(period)
        self.assertEqual(period["event"], "Gamescom 2024")

    def test_orphan_catalog_title_still_gets_a_plan(self) -> None:
        events = [_event("Tokyo Game Show", "2026-09-24", "2026-09-27")]
        catalog = [_product("Obscure Indie Title", platform="Steam", release_date="2025-01-01")]
        plans = build_plans(events, [], catalog)
        self.assertTrue(any(plan["canonical_title"] == "Obscure Indie Title" for plan in plans))
        self.assertTrue(any(plan["event"] == "Tokyo Game Show" for plan in plans))

    def test_sports_event_still_prefers_franchise_sku(self) -> None:
        events = [
            _event(
                "Roland-Garros",
                "2026-05-24",
                "2026-06-07",
                event_type="Tennis",
                category="Sports",
                related_game="Tennis games",
            )
        ]
        catalog = [
            _product("TopSpin 2K25", platform="PlayStation 5", release_date="2024-04-26"),
            _product("Random Shooter", platform="Steam", release_date="2026-05-20"),
        ]
        plans = build_plans(events, [], catalog)
        tennis = [plan for plan in plans if plan["event"] == "Roland-Garros"]
        self.assertTrue(any(plan["canonical_title"] == "TopSpin 2K25" for plan in tennis))

    def test_plan_stamps_confirmed_or_tentative_dates(self) -> None:
        events = [
            _event(
                "Gamescom",
                "2026-08-26",
                "2026-08-30",
                confirmation="confirmed",
                date_precision="day",
                date_label="26 Aug 2026 → 30 Aug 2026",
                official_source="https://www.gamescom.global/",
            ),
            _event(
                "Mystery Showcase",
                "2026-09-01",
                "2026-09-01",
                confirmation="tentative",
                date_precision="month",
                date_label="September 2026",
            ),
        ]
        catalog = [
            _product("Fable", platform="Xbox Series X/S", release_date="2026-09-01"),
            _product("Hades II", platform="Steam", release_date="2026-10-15"),
        ]
        plans = build_plans(events, [], catalog)
        by_event = {plan["event"]: plan for plan in plans}
        self.assertEqual(by_event["Gamescom"]["confirmation"], "confirmed")
        self.assertTrue(by_event["Gamescom"]["exact_date"])
        self.assertEqual(by_event["Gamescom"]["date_label"], "26 Aug 2026 → 30 Aug 2026")
        self.assertEqual(by_event["Mystery Showcase"]["confirmation"], "tentative")
        self.assertFalse(by_event["Mystery Showcase"]["exact_date"])


class ProductEventFallbackTests(unittest.TestCase):
    def test_product_keeps_at_least_one_event_outside_range(self) -> None:
        store = FloorStore()
        store.events = [_event("Gamescom 2023", "2023-08-23", "2023-08-27")]
        store.adaptations = []
        store.plans = [
            {
                "canonical_title": "Hades II",
                "event": "Gamescom 2023",
                "event_start": "2023-08-23",
                "event_end": "2023-08-27",
                "runtime_start": "2023-08-23",
                "runtime_end": "2023-08-27",
                "promo_start": "2023-08-16",
                "promo_end": "2023-08-30",
                "phases": [],
            }
        ]
        start, end = range_span(2026, 6, 2026, 8)
        plans = store._plans_for_product("Hades II", _product("Hades II"), [], range_start=start, range_end=end)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["event"], "Gamescom 2023")

    def test_dashboard_top_product_gets_period_and_yearly_events(self) -> None:
        store = FloorStore()
        store.events = [
            _event("Gamescom 2022", "2022-08-24", "2022-08-28"),
            _event("Gamescom 2023", "2023-08-23", "2023-08-27"),
            _event("Gamescom 2024", "2024-08-21", "2024-08-25"),
            _event("Gamescom 2025", "2025-08-20", "2025-08-24"),
            _event("Gamescom 2026", "2026-08-26", "2026-08-30"),
        ]
        store.adaptations = []
        filled = store._with_correlated_event(
            {"canonical_title": "Minecraft", "best_week_start": "2024-08-22", "max_gmv_event": ""},
            span=True,
            with_years=True,
        )
        self.assertEqual(filled["max_gmv_event"], "Gamescom 2024")
        by_year = {row["year"]: row["max_gmv_event"] for row in filled["year_max_events"]}
        self.assertEqual(by_year["2022"], "Gamescom 2022")
        self.assertEqual(by_year["2023"], "Gamescom 2023")
        self.assertEqual(by_year["2024"], "Gamescom 2024")
        self.assertEqual(by_year["2025"], "Gamescom 2025")
        self.assertEqual(by_year["2026"], "Gamescom 2026")


if __name__ == "__main__":
    unittest.main()
