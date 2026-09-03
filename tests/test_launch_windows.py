from __future__ import annotations

import unittest
from datetime import date

from src.promote import launch_window_games, recommended_games_for_event


def _window(name: str, related: str, **extra) -> dict:
    start = extra.get("start_date", "2026-09-04")
    end = extra.get("end_date", "2026-09-18")
    row = {
        "kind": "event",
        "event": name,
        "start_date": start,
        "end_date": end,
        "start_date_parsed": date.fromisoformat(start),
        "end_date_parsed": date.fromisoformat(end),
        "event_type": extra.get("event_type", "Product Release"),
        "related_game": related,
        "correlated_announced": extra.get("correlated_announced", related),
        "category": extra.get("category", "Announced Product"),
        "source": extra.get("source", "announced_product_window"),
        "organizer": extra.get("organizer", "Capcom"),
    }
    row.update(extra)
    return row


def _product(title: str, **extra) -> dict:
    release = extra.get("release_date", "2023-01-01")
    row = {
        "canonical_title": title,
        "product_title": title,
        "product_type": extra.get("product_type", "game"),
        "platform": extra.get("platform", "Steam"),
        "release_date": release,
        "release_date_parsed": date.fromisoformat(release),
        "product_id": title.lower().replace(" ", "-"),
        "developer": extra.get("developer", ""),
        "publisher": extra.get("publisher", ""),
        "franchise": extra.get("franchise", ""),
    }
    row.update(extra)
    row["release_date_parsed"] = date.fromisoformat(row["release_date"]) if row.get("release_date") else None
    return row


class LaunchWindowRecommendTests(unittest.TestCase):
    def test_onimusha_cross_promotes_franchise_and_capcom(self) -> None:
        row = _window("Onimusha: Way of the Sword release window", "Onimusha: Way of the Sword")
        catalog = [
            _product("Onimusha: Way of the Sword", developer="Capcom", release_date="2026-09-04", product_type="announced"),
            _product("Onimusha 2 Samurai's Destiny", release_date="2002-03-07"),
            _product("Onimusha 1+2 Pack", release_date="2022-01-01"),
            _product("Dead by Daylight - Resident Evil Chapter DLC", product_type="dlc", release_date="2021-06-15"),
            _product("Resident Evil Requiem", developer="Capcom", release_date="2026-02-27"),
            _product("Monster Hunter Wilds", publisher="Capcom", release_date="2025-02-28"),
            _product("Street Fighter 6", release_date="2023-06-02"),
            _product("Devil May Cry 5", release_date="2019-03-08"),
            _product("Fable", publisher="Xbox Game Studios", release_date="2027-02-23"),
            _product("Hades II", developer="Supergiant Games", release_date="2026-10-15"),
        ]
        titles = [item["canonical_title"] for item in recommended_games_for_event(row, catalog, limit=10)]
        self.assertEqual(titles[0], "Onimusha: Way of the Sword")
        for name in (
            "Onimusha 2 Samurai's Destiny",
            "Onimusha 1+2 Pack",
            "Resident Evil Requiem",
            "Monster Hunter Wilds",
            "Street Fighter 6",
            "Devil May Cry 5",
        ):
            self.assertIn(name, titles)
        self.assertNotIn("Fable", titles)
        self.assertNotIn("Hades II", titles)
        self.assertNotIn("Dead by Daylight - Resident Evil Chapter DLC", titles)

    def test_same_developer_is_enough_without_franchise_alias(self) -> None:
        row = _window(
            "Pragmata release window",
            "Pragmata",
            organizer="Capcom",
        )
        catalog = [
            _product("Pragmata", developer="Capcom", release_date="2026-04-01", product_type="announced"),
            _product("Resident Evil Requiem", developer="Capcom", release_date="2026-02-27"),
            _product("Hades II", developer="Supergiant Games", release_date="2026-10-15"),
        ]
        titles = {item["canonical_title"] for item in launch_window_games(row, catalog)}
        self.assertIn("Pragmata", titles)
        self.assertIn("Resident Evil Requiem", titles)
        self.assertNotIn("Hades II", titles)

    def test_generic_expo_is_not_treated_as_a_studio_launch(self) -> None:
        row = {
            "kind": "event",
            "event": "Gamescom",
            "start_date": "2026-08-26",
            "end_date": "2026-08-30",
            "event_type": "Gaming Expo",
            "related_game": "Multi-platform",
            "category": "Gaming",
        }
        catalog = [
            _product("Fable", publisher="Xbox Game Studios", release_date="2027-02-23"),
            _product("Hades II", developer="Supergiant Games", release_date="2026-10-15"),
        ]
        self.assertEqual(launch_window_games(row, catalog), [])


class HostCountryRecommendTests(unittest.TestCase):
    def test_tokyo_game_show_promotes_japanese_studios(self) -> None:
        row = {
            "kind": "event",
            "event": "Tokyo Game Show",
            "start_date": "2026-09-24",
            "end_date": "2026-09-27",
            "event_type": "Gaming Expo",
            "related_game": "Multi-platform",
            "category": "Gaming",
            "location": "Makuhari Messe, Chiba",
        }
        catalog = [
            _product("Super Mario Bros. Wonder", publisher="Nintendo", release_date="2023-10-20"),
            _product("Resident Evil Requiem", developer="Capcom", release_date="2026-02-27"),
            _product("Final Fantasy VII Rebirth", publisher="Square Enix", release_date="2024-02-29"),
            _product("Genshin Impact", publisher="HoYoverse", release_date="2020-09-28"),
            _product("Fable", publisher="Xbox Game Studios", release_date="2027-02-23"),
            _product("Hades II", developer="Supergiant Games", release_date="2026-10-15"),
        ]
        titles = [item["canonical_title"] for item in recommended_games_for_event(row, catalog, limit=10)]
        self.assertIn("Super Mario Bros. Wonder", titles)
        self.assertIn("Resident Evil Requiem", titles)
        self.assertIn("Final Fantasy VII Rebirth", titles)
        self.assertNotIn("Genshin Impact", titles)
        self.assertNotIn("Fable", titles)
        self.assertNotIn("Hades II", titles)

    def test_chinajoy_promotes_chinese_studios(self) -> None:
        row = {
            "kind": "event",
            "event": "ChinaJoy",
            "start_date": "2026-07-31",
            "end_date": "2026-08-03",
            "event_type": "Gaming Expo",
            "related_game": "Multi-platform",
            "category": "Gaming",
            "location": "Shanghai",
        }
        catalog = [
            _product("Genshin Impact", publisher="HoYoverse", release_date="2020-09-28"),
            _product("Black Myth: Wukong", developer="Game Science", release_date="2024-08-20"),
            _product("Wuthering Waves", publisher="Kuro Games", release_date="2024-05-22"),
            _product("Super Mario Bros. Wonder", publisher="Nintendo", release_date="2023-10-20"),
            _product("Fable", publisher="Xbox Game Studios", release_date="2027-02-23"),
        ]
        titles = [item["canonical_title"] for item in recommended_games_for_event(row, catalog, limit=10)]
        self.assertIn("Genshin Impact", titles)
        self.assertIn("Black Myth: Wukong", titles)
        self.assertIn("Wuthering Waves", titles)
        self.assertNotIn("Super Mario Bros. Wonder", titles)
        self.assertNotIn("Fable", titles)

    def test_nintendo_direct_is_not_every_japanese_studio(self) -> None:
        row = {
            "kind": "event",
            "event": "Nintendo Direct",
            "start_date": "2026-06-18",
            "end_date": "2026-06-18",
            "event_type": "Showcase",
            "related_game": "Nintendo franchises",
            "category": "Gaming",
        }
        catalog = [
            _product("Super Mario Bros. Wonder", publisher="Nintendo", release_date="2023-10-20"),
            _product("Resident Evil Requiem", developer="Capcom", release_date="2026-02-27"),
        ]
        titles = [item["canonical_title"] for item in recommended_games_for_event(row, catalog, limit=10)]
        self.assertIn("Super Mario Bros. Wonder", titles)
        self.assertNotIn("Resident Evil Requiem", titles)


if __name__ == "__main__":
    unittest.main()
