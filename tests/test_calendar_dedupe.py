from __future__ import annotations

import unittest

from src.calendar_dedupe import dedupe_calendar_rows, split_deduped_calendar
from src.dates import annotate_event


def _row(name: str, start: str, end: str, **extra) -> dict:
    row = {
        "event": name,
        "start_date": start,
        "end_date": end,
        "kind": extra.pop("kind", "event"),
        "confirmation": extra.pop("confirmation", "planning"),
        "date_precision": extra.pop("date_precision", "day"),
        "source": extra.pop("source", "test"),
    }
    row.update(extra)
    return annotate_event(row)


class CalendarDedupeTests(unittest.TestCase):
    def test_collapses_year_suffix_duplicate(self) -> None:
        rows = [
            _row("Gamescom", "2026-08-26", "2026-08-30", confirmation="confirmed"),
            _row("Gamescom 2026", "2026-08-26", "2026-08-30", confirmation="confirmed", wikipedia_url="https://en.wikipedia.org/wiki/Gamescom"),
        ]
        kept = dedupe_calendar_rows(rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["event"], "Gamescom 2026")
        self.assertTrue(kept[0].get("wikipedia_url"))

    def test_collapses_event_and_adaptation_copy(self) -> None:
        rows = [
            _row("Uncharted", "2022-02-18", "2022-03-03", kind="event", confirmation="confirmed"),
            _row("Uncharted", "2022-02-18", "2022-03-03", kind="adaptation", confirmation="confirmed", event=""),
        ]
        rows[1]["ip_adaptation"] = "Uncharted"
        rows[1]["event"] = ""
        rows[1] = annotate_event(rows[1])
        events, adaptations = split_deduped_calendar(rows[:1], rows[1:])
        self.assertEqual(len(events) + len(adaptations), 1)
        self.assertEqual(adaptations[0]["kind"], "adaptation")

    def test_keeps_distinct_editions_in_the_same_year(self) -> None:
        rows = [
            _row("Steam Next Fest", "2027-02-01", "2027-02-28", date_precision="month"),
            _row("Steam Next Fest", "2027-06-01", "2027-06-30", date_precision="month"),
        ]
        kept = dedupe_calendar_rows(rows)
        self.assertEqual(len(kept), 2)

    def test_merges_overlapping_planning_stubs(self) -> None:
        rows = [
            _row("League of Legends Worlds", "2026-09-25", "2026-11-09", confirmation="planning"),
            _row("League of Legends Worlds 2026", "2026-10-15", "2026-11-14", confirmation="confirmed"),
            _row("League of Legends Worlds", "2026-11-01", "2026-11-30", confirmation="planning", date_precision="month"),
        ]
        kept = dedupe_calendar_rows(rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["event"], "League of Legends Worlds 2026")

    def test_merges_nearby_alternate_dates(self) -> None:
        rows = [
            _row("PAX West", "2026-08-28", "2026-08-31", confirmation="planning"),
            _row("PAX West", "2026-09-04", "2026-09-07", confirmation="confirmed"),
        ]
        kept = dedupe_calendar_rows(rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["start_date"], "2026-09-04")

    def test_merges_same_year_entertainment_windows(self) -> None:
        rows = [
            _row(
                "The Super Mario Galaxy Movie",
                "2026-04-01",
                "2026-04-14",
                confirmation="confirmed",
                event_type="Theatrical Film",
                category="Movies",
            ),
            _row(
                "The Super Mario Galaxy Movie",
                "2026-05-14",
                "2026-05-14",
                kind="adaptation",
                confirmation="announced",
                format="Live-action theatrical film",
            ),
        ]
        kept = dedupe_calendar_rows(rows)
        self.assertEqual(len(kept), 1)


    def test_drops_quarter_timeframe_stubs(self) -> None:
        rows = [
            _row("Q3 release window", "2026-07-01", "2026-09-30", date_precision="quarter"),
            _row("Q3/Q4 release window", "2026-07-01", "2026-09-30", date_precision="quarter"),
            _row("Q4 window", "2026-10-01", "2026-12-31", date_precision="quarter"),
            _row("Q1", "2026-01-01", "2026-03-31", date_precision="quarter"),
            _row("Gamescom", "2026-08-26", "2026-08-30", confirmation="confirmed"),
            _row("Fable release window", "2026-10-01", "2026-12-31", date_precision="quarter"),
        ]
        kept = dedupe_calendar_rows(rows)
        self.assertEqual({row["event"] for row in kept}, {"Gamescom", "Fable release window"})

    def test_quarter_timeframe_helper(self) -> None:
        from src.calendar_dedupe import is_quarter_timeframe

        self.assertTrue(is_quarter_timeframe("Q3"))
        self.assertTrue(is_quarter_timeframe("Q3/Q4"))
        self.assertTrue(is_quarter_timeframe("Q4 2026"))
        self.assertTrue(is_quarter_timeframe("2026 Q1 window"))
        self.assertTrue(is_quarter_timeframe("Q3 release window"))
        self.assertTrue(is_quarter_timeframe({"event": "Q3/Q4 release window"}))
        self.assertFalse(is_quarter_timeframe("Gamescom"))
        self.assertFalse(is_quarter_timeframe("Fable Q4 release window"))
        self.assertFalse(is_quarter_timeframe("Nintendo Direct"))

    def test_announced_skips_quarter_titled_windows(self) -> None:
        from src.announced import release_window_events

        rows = release_window_events(
            [
                {"canonical_title": "Q3", "release_date": "2026-07-01", "date_precision": "quarter"},
                {"canonical_title": "Q3/Q4", "release_date": "2026-07-01", "date_precision": "month"},
                {"canonical_title": "Fable", "release_date": "2026-10-01", "date_precision": "quarter"},
            ]
        )
        self.assertEqual([row["event"] for row in rows], ["Fable release window"])


class GamingWorldArchiveTests(unittest.TestCase):
    def test_keeps_industry_events_and_drops_sports_films_windows(self) -> None:
        from src.calendar_dedupe import is_gaming_world_event
        from src.historical_calendar import historical_events

        rows = [row for row in historical_events() if is_gaming_world_event(row)]
        names = {row["event"] for row in rows}
        self.assertTrue(any("Gamescom" in name for name in names))
        self.assertTrue(any(name.startswith("GDC") for name in names))
        self.assertTrue(any("Tokyo Game Show" in name for name in names))
        self.assertTrue(any("Esports World Cup" in name for name in names))
        self.assertFalse(any("FIFA World Cup" in name for name in names))
        self.assertFalse(any("The Batman" in name for name in names))
        years = {(row.get("start_date") or "")[:4] for row in rows}
        self.assertTrue({"2022", "2023", "2024", "2025", "2026"} <= years)
        for row in rows:
            self.assertTrue(row.get("start_date"))
            self.assertTrue(row.get("end_date"))

    def test_rejects_quarter_and_product_windows(self) -> None:
        from src.calendar_dedupe import is_gaming_world_event

        self.assertFalse(is_gaming_world_event(_row("Q3", "2026-07-01", "2026-09-30")))
        self.assertFalse(
            is_gaming_world_event(
                _row(
                    "Fable release window",
                    "2026-09-01",
                    "2026-09-14",
                    source="announced_product_window",
                    event_type="Product Release",
                    category="Announced Product",
                )
            )
        )
        self.assertTrue(
            is_gaming_world_event(
                _row(
                    "Gamescom 2023",
                    "2023-08-23",
                    "2023-08-27",
                    category="Gaming",
                    event_type="Gaming Expo",
                    location="Cologne",
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
