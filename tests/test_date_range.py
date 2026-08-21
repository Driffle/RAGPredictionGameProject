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
