from __future__ import annotations

import unittest
from datetime import date

from src.date_range import is_current_or_in_range, range_span


class PromoWindowFilterTests(unittest.TestCase):
    def test_keeps_future_event_without_calendar_range(self) -> None:
        row = {"event": "Avengers: Doomsday", "runtime_start": "2026-12-18", "runtime_end": "2026-12-18"}
        self.assertTrue(is_current_or_in_range(row, today=date(2026, 8, 20)))

    def test_keeps_live_event(self) -> None:
        row = {"event": "Gamescom", "event_start": "2026-08-19", "event_end": "2026-08-23"}
        self.assertTrue(is_current_or_in_range(row, today=date(2026, 8, 20)))

    def test_drops_past_event_without_calendar_range(self) -> None:
        row = {"event": "The Batman", "start": "2022-03-04", "end": "2022-03-04"}
        self.assertFalse(is_current_or_in_range(row, today=date(2026, 8, 20)))

    def test_keeps_past_event_inside_calendar_range(self) -> None:
        row = {
            "event": "Summer Game Fest",
            "runtime_start": "2026-06-06",
            "runtime_end": "2026-06-08",
        }
        start, end = range_span(2026, 6, 2026, 8)
        self.assertTrue(
            is_current_or_in_range(
                row,
                today=date(2026, 8, 20),
                range_start=start,
                range_end=end,
            )
        )

    def test_drops_past_event_outside_calendar_range(self) -> None:
        row = {"name": "Deadpool & Wolverine", "start": "2024-07-26", "end": "2024-07-26"}
        start, end = range_span(2026, 6, 2026, 8)
        self.assertFalse(
            is_current_or_in_range(
                row,
                today=date(2026, 8, 20),
                range_start=start,
                range_end=end,
            )
        )

    def test_plan_promo_fields_are_read(self) -> None:
        row = {
            "canonical_title": "Marvel's Spider-Man 2",
            "event": "Avengers: Secret Wars",
            "promo_start": "2027-11-01",
            "promo_end": "2028-01-15",
            "event_start": "2027-12-17",
            "event_end": "2027-12-17",
        }
        self.assertTrue(is_current_or_in_range(row, today=date(2026, 8, 20)))


class CalendarRangeListingTests(unittest.TestCase):
    def test_drops_product_release_windows_outside_true_event_dates(self) -> None:
        from src.date_range import calendar_range_payload

        events = [
            {
                "kind": "event",
                "event": "Gamescom 2026",
                "start_date": "2026-08-26",
                "end_date": "2026-08-30",
                "date_precision": "day",
                "event_type": "Gaming Expo",
            },
            {
                "kind": "event",
                "event": "Nostalgic Train release window",
                "start_date": "2026-08-26",
                "end_date": "2026-09-09",
                "date_precision": "day",
                "event_type": "Product Release",
                "source": "announced_product_window",
            },
            {
                "kind": "event",
                "event": "PlayStation State of Play September 2026",
                "start_date": "2026-09-03",
                "end_date": "2026-09-03",
                "date_precision": "day",
                "event_type": "Digital Showcase",
            },
            {
                "kind": "event",
                "event": "Tokyo Game Show 2026",
                "start_date": "2026-09-17",
                "end_date": "2026-09-21",
                "date_precision": "day",
                "event_type": "Gaming Expo",
            },
        ]
        payload = calendar_range_payload(
            start_year=2026,
            start_month=9,
            end_year=2026,
            end_month=9,
            events=events,
            adaptations=[],
            plans=[],
            precision="dated",
        )
        names = {row["name"] for row in payload["events"]}
        self.assertIn("PlayStation State of Play September 2026", names)
        self.assertIn("Tokyo Game Show 2026", names)
        self.assertNotIn("Nostalgic Train release window", names)
        self.assertNotIn("Gamescom 2026", names)

    def test_june_august_keeps_gamescom_not_september_showcase(self) -> None:
        from src.date_range import calendar_range_payload

        events = [
            {
                "kind": "event",
                "event": "Gamescom 2026",
                "start_date": "2026-08-26",
                "end_date": "2026-08-30",
                "date_precision": "day",
                "event_type": "Gaming Expo",
            },
            {
                "kind": "event",
                "event": "PlayStation State of Play September 2026",
                "start_date": "2026-09-03",
                "end_date": "2026-09-03",
                "date_precision": "day",
                "event_type": "Digital Showcase",
            },
        ]
        payload = calendar_range_payload(
            start_year=2026,
            start_month=6,
            end_year=2026,
            end_month=8,
            events=events,
            adaptations=[],
            plans=[],
            precision="dated",
        )
        names = {row["name"] for row in payload["events"]}
        self.assertIn("Gamescom 2026", names)
        self.assertNotIn("PlayStation State of Play September 2026", names)


class LiveEventHorizonTests(unittest.TestCase):
    def test_drops_pre_2026_events(self) -> None:
        from src.date_range import event_on_or_after_horizon

        self.assertFalse(
            event_on_or_after_horizon(
                {"event": "Gamescom 2025", "start_date": "2025-08-20", "end_date": "2025-08-24"}
            )
        )
        self.assertTrue(
            event_on_or_after_horizon(
                {
                    "event": "PlayStation State of Play September 2026",
                    "start_date": "2026-09-03",
                    "end_date": "2026-09-03",
                }
            )
        )
        self.assertTrue(
            event_on_or_after_horizon(
                {"event": "The Game Awards 2027", "start_date": "2027-12-09", "end_date": "2027-12-09"}
            )
        )
