from __future__ import annotations

import unittest
from datetime import date

from src.geo_placement import geos_for_event, placement_payload


class GeoPlacementTests(unittest.TestCase):
    def test_regional_event_maps_to_country(self) -> None:
        self.assertEqual(
            geos_for_event({"location": "Cologne, Germany", "scope": "regional"}),
            ("DE",),
        )

    def test_busan_is_korea_not_united_states(self) -> None:
        self.assertEqual(
            geos_for_event(
                {
                    "event": "Busan Indie Connect Festival",
                    "location": "Busan",
                    "scope": "regional",
                    "attendance_mode": "hybrid",
                    "related_game": "Indie / Korea",
                }
            ),
            ("KR",),
        )
        self.assertNotIn(
            "US",
            geos_for_event({"location": "Busan", "attendance_mode": "hybrid"}),
        )

    def test_digital_event_maps_to_worldwide_bucket(self) -> None:
        self.assertEqual(
            geos_for_event({"location": "Online", "attendance_mode": "digital"}),
            ("WW",),
        )

    def test_multi_city_runtime_maps_each_country(self) -> None:
        geos = set(
            geos_for_event({"location": "Berlin / Paris / London", "scope": "regional"})
        )
        self.assertEqual(geos, {"DE", "FR", "GB"})

    def test_unknown_city_is_not_dumped_into_us(self) -> None:
        self.assertEqual(
            geos_for_event({"location": "Unknownville", "scope": "regional", "attendance_mode": "physical"}),
            (),
        )

    def test_products_inherit_event_geography(self) -> None:
        events = [
            {
                "event": "Gamescom",
                "start_date": "2026-08-26",
                "end_date": "2026-08-30",
                "location": "Cologne, Germany",
                "scope": "regional",
            },
            {
                "event": "Busan Indie Connect Festival",
                "start_date": "2026-08-21",
                "end_date": "2026-08-23",
                "location": "Busan",
                "scope": "regional",
                "attendance_mode": "hybrid",
            },
        ]
        plans = [
            {
                "event": "Gamescom",
                "canonical_title": "Fable",
                "platform": "Xbox Series X/S",
                "role": "game",
            },
            {
                "event": "Busan Indie Connect Festival",
                "canonical_title": "BOKURA",
                "platform": "Steam",
                "role": "game",
            },
        ]
        payload = placement_payload(
            events,
            [],
            plans,
            on=date(2026, 8, 18),
            horizon_days=30,
        )
        self.assertEqual(payload["placements"]["DE"]["products"][0]["canonical_title"], "Fable")
        self.assertEqual(payload["placements"]["KR"]["products"][0]["canonical_title"], "BOKURA")
        self.assertEqual(payload["placements"]["US"]["products"], [])
        self.assertIn("KR", payload["tracked_geos"])
        self.assertNotIn("US", [row["name"] for row in payload["placements"]["US"]["events"]])

    def test_named_events_fill_blank_locations(self) -> None:
        self.assertEqual(
            set(geos_for_event({"event": "GDC", "location": "", "attendance_mode": "hybrid"})),
            {"US"},
        )
        self.assertEqual(
            set(geos_for_event({"event": "Nintendo Direct", "location": "", "attendance_mode": "hybrid"})),
            {"JP", "WW"},
        )
        self.assertEqual(
            set(geos_for_event({"event": "Roland-Garros", "location": ""})),
            {"FR"},
        )
        self.assertEqual(
            set(geos_for_event({"event": "Steam Next Fest", "location": ""})),
            {"US", "WW"},
        )
        self.assertIn("DE", geos_for_event({"event": "Gamescom", "location": ""}))
        self.assertEqual(
            set(geos_for_event({"event": "Gamescom Latam", "location": "São Paulo"})),
            {"BR"},
        )
        self.assertNotIn(
            "US",
            geos_for_event({"event": "Nintendo Direct", "location": "", "attendance_mode": "hybrid"}),
        )

    def test_location_display_includes_country(self) -> None:
        from src.geo_placement import location_display_for

        self.assertIn(
            "South Korea",
            location_display_for({"event": "Busan Indie Connect Festival", "location": "Busan"}),
        )
        self.assertIn(
            "United States",
            location_display_for({"event": "GDC", "location": ""}),
        )
        self.assertIn(
            "Japan",
            location_display_for({"event": "Nintendo Direct", "location": ""}),
        )


if __name__ == "__main__":
    unittest.main()
