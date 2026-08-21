from __future__ import annotations

import unittest

from src.coverage import cross_media_releases
from src.horizon import projected_events
from src.match import franchise_keys_for_text, franchises_overlap


class CoverageTests(unittest.TestCase):
    def test_spider_man_title_variants_share_franchise(self) -> None:
        self.assertEqual(franchise_keys_for_text("Spider Man 2"), {"spider-man", "marvel"})
        self.assertTrue(
            franchises_overlap("Marvel's Spider-Man 2", "Spider-Man: Brand New Day")
        )
        self.assertTrue(
            franchises_overlap(
                "Marvel's Spider-Man: Miles Morales",
                "Spider-Man: Across the Spider-Verse",
            )
        )
        self.assertTrue(
            franchises_overlap(
                "Marvel's Spider-Man: Miles Morales",
                "Spider-Man: Into the Spider-Verse",
            )
        )

    def test_studio_animation_is_on_the_calendar(self) -> None:
        from src.historical_calendar import historical_events

        titles = {row["event"] for row in historical_events()}
        self.assertIn("Spider-Man: Across the Spider-Verse", titles)
        self.assertIn("Spider-Man: Into the Spider-Verse", titles)
        self.assertIn("X-Men '97 season 1", titles)
        self.assertIn("What If...? season 2", titles)
        self.assertIn("Your Friendly Neighborhood Spider-Man season 1", titles)
        self.assertIn("DC League of Super-Pets", titles)
        self.assertIn("Creature Commandos season 1", titles)
        self.assertIn("Inside Out 2", titles)
        self.assertIn("Moana 2", titles)
        self.assertIn("Teenage Mutant Ninja Turtles: Mutant Mayhem", titles)
        self.assertIn("Transformers One", titles)
        self.assertIn("Despicable Me 4", titles)
        self.assertIn("The Super Mario Bros. Movie", titles)

    def test_beyond_the_spider_verse_is_registered(self) -> None:
        hits = [
            row
            for row in cross_media_releases()
            if row["ip_adaptation"] == "Spider-Man: Beyond the Spider-Verse"
        ]
        self.assertEqual(len(hits), 1)
        self.assertIn("Miles Morales", hits[0]["related_game"])

    def test_brand_new_day_is_registered(self) -> None:
        hits = [
            row
            for row in cross_media_releases()
            if row["ip_adaptation"] == "Spider-Man: Brand New Day"
        ]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["related_game"], "Marvel")

    def test_event_registry_has_all_attendance_modes(self) -> None:
        modes = {row.get("attendance_mode") for row in projected_events()}
        self.assertTrue({"physical", "digital", "hybrid"} <= modes)

    def test_projected_registry_spans_2026_to_2030(self) -> None:
        years = {(row.get("start_date") or "")[:4] for row in projected_events()}
        self.assertTrue({"2026", "2027", "2028", "2029", "2030"} <= years)

    def test_curated_announced_includes_unreleased_titles(self) -> None:
        from src.announced import curated_announced_games, release_window_events

        titles = {row["canonical_title"] for row in curated_announced_games()}
        self.assertIn("Grand Theft Auto VI", titles)
        self.assertIn("The Elder Scrolls VI", titles)
        windows = release_window_events(curated_announced_games())
        self.assertTrue(any("Grand Theft Auto VI" in row["event"] for row in windows))

    def test_historical_calendar_covers_2022_to_2026(self) -> None:
        from src.historical_calendar import historical_adaptations, historical_events

        events = historical_events()
        years = {(row.get("start_date") or "")[:4] for row in events}
        self.assertTrue({"2022", "2023", "2024", "2025", "2026"} <= years)
        types = {row["event_type"] for row in events}
        self.assertTrue({"Gaming Expo", "Digital Showcase", "Theatrical Film", "OTT Series", "Esports", "Football"} <= types)
        for row in events:
            self.assertTrue(row["start_date"])
            self.assertTrue(row["end_date"])
            self.assertGreaterEqual(row["end_date"], row["start_date"])
            self.assertEqual(row["date_precision"], "day")
        titles = {row["event"] for row in events}
        self.assertIn("The Super Mario Bros. Movie", titles)
        self.assertIn("Avengers: Doomsday", titles)
        self.assertIn("Superman", titles)
        self.assertIn("Gamescom 2023", titles)
        self.assertIn("The Game Awards 2024", titles)
        self.assertIn("2022 FIFA World Cup", titles)
        self.assertIn("Fallout season 1", titles)
        media = historical_adaptations()
        self.assertTrue(any(row["ip_adaptation"] == "A Minecraft Movie" for row in media))
        self.assertTrue(any(row["ip_adaptation"] == "The Last of Us season 1" for row in media))

    def test_event_correlation_attaches_announced_titles(self) -> None:
        from src.announced import correlate_events_with_announced, curated_announced_games

        events = [
            {
                "kind": "event",
                "event": "Summer Game Fest",
                "related_game": "Multi-platform",
                "event_type": "Showcase",
                "category": "Gaming",
                "start_date": "2026-06-06",
                "end_date": "2026-06-08",
            }
        ]
        enriched = correlate_events_with_announced(events, curated_announced_games())
        self.assertTrue(enriched[0].get("correlated_announced") or "Grand Theft Auto" in (enriched[0].get("related_game") or ""))


if __name__ == "__main__":
    unittest.main()
