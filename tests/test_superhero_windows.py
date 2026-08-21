from __future__ import annotations

import unittest
from datetime import date

from src.content_marketing import seo_keywords, social_pack
from src.coverage import cross_media_releases
from src.match import queries_for_calendar_row, superhero_universe_for_row
from src.promote import build_plans, products_for_event


def _film(name: str, related: str, start: str = "2026-12-18") -> dict:
    return {
        "kind": "adaptation",
        "ip_adaptation": name,
        "event": name,
        "start_date": start,
        "end_date": start,
        "start_date_parsed": date.fromisoformat(start),
        "end_date_parsed": date.fromisoformat(start),
        "event_type": "Theatrical Film",
        "medium": "Live-action theatrical film",
        "related_game": related,
        "category": "Movies",
    }


def _product(title: str, **extra) -> dict:
    release = extra.get("release_date", "2023-01-01")
    return {
        "canonical_title": title,
        "product_title": title,
        "product_type": extra.get("product_type", "game"),
        "platform": extra.get("platform", "Steam"),
        "release_date": release,
        "release_date_parsed": date.fromisoformat(release),
        "product_id": title.lower().replace(" ", "-"),
        "confirmation": extra.get("confirmation", "released / catalog"),
    }


class SuperheroWindowTests(unittest.TestCase):
    def test_doomsday_is_in_cross_media_registry(self) -> None:
        names = {row.get("ip_adaptation") for row in cross_media_releases()}
        self.assertIn("Avengers: Doomsday", names)
        self.assertIn("Supergirl: Woman of Tomorrow", names)
        self.assertIn("Clayface", names)
        self.assertIn("Avengers: Secret Wars", names)
        self.assertIn("The Batman Part II", names)

    def test_doomsday_is_marvel_universe(self) -> None:
        row = _film("Avengers: Doomsday", "Marvel")
        self.assertEqual(superhero_universe_for_row(row), "marvel")
        queries = queries_for_calendar_row(row)
        self.assertIn("marvel", queries)
        self.assertIn("wolverine", queries)
        self.assertIn("spider-man", queries)

    def test_wondercon_is_not_a_marvel_universe_film(self) -> None:
        row = {
            "kind": "event",
            "event": "WonderCon",
            "event_type": "Fan Convention",
            "related_game": "Marvel, DC, anime, gaming adaptations",
        }
        self.assertIsNone(superhero_universe_for_row(row))

    def test_doomsday_cross_promotes_marvel_catalog(self) -> None:
        row = _film("Avengers: Doomsday", "Marvel")
        catalog = [
            _product("Marvel's Spider-Man 2", release_date="2023-10-20"),
            _product("Marvel's Wolverine", release_date="2026-09-15", product_type="announced"),
            _product("Marvel's Midnight Suns", release_date="2022-12-02"),
            _product("LEGO Marvel's Avengers", release_date="2016-01-26"),
            _product("ULTIMATE MARVEL VS. CAPCOM 3", release_date="2011-11-15"),
            _product("Batman: Arkham Knight", release_date="2015-06-23"),
            _product("Fable", release_date="2027-02-23"),
        ]
        titles = {item["canonical_title"] for item in products_for_event(row, catalog)}
        self.assertIn("Marvel's Spider-Man 2", titles)
        self.assertIn("Marvel's Wolverine", titles)
        self.assertIn("Marvel's Midnight Suns", titles)
        self.assertIn("LEGO Marvel's Avengers", titles)
        self.assertNotIn("Batman: Arkham Knight", titles)
        self.assertNotIn("Fable", titles)

    def test_supergirl_cross_promotes_dc_catalog(self) -> None:
        row = _film("Supergirl: Woman of Tomorrow", "DC", start="2026-06-26")
        catalog = [
            _product("Batman: Arkham Knight", release_date="2015-06-23"),
            _product("Injustice 2", release_date="2017-05-16"),
            _product("Gotham Knights", release_date="2022-10-21"),
            _product("Marvel's Spider-Man 2", release_date="2023-10-20"),
        ]
        titles = {item["canonical_title"] for item in products_for_event(row, catalog)}
        self.assertIn("Batman: Arkham Knight", titles)
        self.assertIn("Injustice 2", titles)
        self.assertIn("Gotham Knights", titles)
        self.assertNotIn("Marvel's Spider-Man 2", titles)

    def test_plans_map_marvel_games_to_doomsday(self) -> None:
        events = [_film("Avengers: Doomsday", "Marvel")]
        catalog = [
            _product("Marvel's Spider-Man 2"),
            _product("Marvel's Wolverine", product_type="announced", release_date="2026-09-15"),
        ]
        plans = build_plans([], events, catalog)
        mapped = {(plan["event"], plan["canonical_title"]) for plan in plans}
        self.assertIn(("Avengers: Doomsday", "Marvel's Spider-Man 2"), mapped)
        self.assertIn(("Avengers: Doomsday", "Marvel's Wolverine"), mapped)

    def test_marvel_seo_and_hashtags(self) -> None:
        keys = " ".join(seo_keywords("Marvel's Wolverine", "Avengers: Doomsday", "adaptation", "game")).lower()
        self.assertIn("marvel games", keys)
        self.assertIn("avengers", keys)
        self.assertIn("doomsday", keys)
        pack = social_pack("Marvel's Wolverine", "Avengers: Doomsday", "adaptation")
        tags = pack["tiktok"]["hashtags"]
        self.assertTrue(any(tag in tags for tag in ("#Marvel", "#MCU", "#MarvelGames", "#Avengers")))


if __name__ == "__main__":
    unittest.main()
