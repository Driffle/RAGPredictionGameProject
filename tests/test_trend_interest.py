from __future__ import annotations

import unittest
from datetime import date

from src.trend_interest import (
    build_lookup_interest,
    lookup_targets,
    wiki_article_from_url,
)
from src.trends import _pageview_range


WOLVERINE = {
    "canonical_title": "Marvel's Wolverine",
    "product_title": "Marvel's Wolverine",
    "product_type": "announced",
    "release_date": "2026-09-15",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Marvel%27s_Wolverine",
}

FABLE = {
    "canonical_title": "Fable",
    "product_title": "Fable",
    "product_type": "announced",
    "release_date": "2027-02-23",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Fable_(2027_video_game)",
}

TGS = {
    "event": "Tokyo Game Show 2026",
    "start_date": "2026-09-24",
    "end_date": "2026-09-27",
    "event_type": "Expo",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Tokyo_Game_Show",
}

SKU_WINDOW = {
    "event": "Marvel's Wolverine release window",
    "start_date": "2026-09-01",
    "end_date": "2026-09-29",
    "event_type": "product release",
    "source": "announced_product_window",
}


class TrendInterestTests(unittest.TestCase):
    def test_wiki_article_from_encoded_url(self) -> None:
        self.assertEqual(
            wiki_article_from_url("https://en.wikipedia.org/wiki/Marvel%27s_Wolverine"),
            "Marvel's Wolverine",
        )
        self.assertEqual(
            wiki_article_from_url("https://en.wikipedia.org/wiki/2026_in_video_games"),
            "",
        )

    def test_announced_titles_are_not_crowded_out_by_sku_editions(self) -> None:
        clutter = [
            {
                "canonical_title": f"Filler Game {i} - Deluxe Edition",
                "product_title": f"Filler Game {i} - Deluxe Edition",
                "product_type": "game",
                "release_date": "2026-09-03",
            }
            for i in range(30)
        ]
        targets = lookup_targets(
            clutter + [WOLVERINE],
            [],
            as_of=date(2026, 9, 3),
        )
        queries = {row["query"] for row in targets}
        self.assertIn("Marvel's Wolverine", queries)
        targets = lookup_targets(
            [WOLVERINE, FABLE],
            [TGS, SKU_WINDOW],
            as_of=date(2026, 9, 3),
        )
        queries = {row["query"] for row in targets}
        self.assertIn("Marvel's Wolverine", queries)
        self.assertIn("Tokyo Game Show 2026", queries)
        self.assertNotIn("Fable", queries)
        self.assertNotIn("Marvel's Wolverine release window", queries)
        wolf = next(row for row in targets if row["query"] == "Marvel's Wolverine")
        self.assertEqual(wolf["kind"], "product")
        self.assertEqual(wolf["window_start"], "2026-09-01")
        self.assertEqual(wolf["window_end"], "2026-09-29")
        self.assertEqual(wolf["wiki_article"], "Marvel's Wolverine")

    def test_google_and_wiki_counts_join_onto_wolverine(self) -> None:
        rows = build_lookup_interest(
            google=[
                {
                    "title": "Marvel's Wolverine",
                    "traffic": 50_000,
                    "traffic_label": "50,000+",
                    "geo": "US",
                },
                {"title": "weather today", "traffic": 500_000, "geo": "US"},
            ],
            wiki=[
                {
                    "article": "Marvel's Wolverine",
                    "views": 4_200,
                    "baseline": 2_100,
                    "spike_ratio": 2.0,
                    "as_of": "2026-09-02",
                    "series": [
                        ("20260820", 1_900),
                        ("20260901", 3_800),
                        ("20260902", 4_200),
                    ],
                    "window_views": 9_900,
                }
            ],
            catalog=[WOLVERINE, FABLE],
            events=[TGS],
            as_of=date(2026, 9, 3),
        )
        wolf = next(row for row in rows if row["query"] == "Marvel's Wolverine")
        self.assertEqual(wolf["google_searches"], 50_000)
        self.assertEqual(wolf["searches"], 50_000)
        self.assertEqual(wolf["search_source"], "google_trends")
        self.assertEqual(wolf["google_label"], "50,000+")
        self.assertEqual(wolf["wiki_views"], 4_200)
        self.assertEqual(wolf["wiki_window_views"], 8_000)
        self.assertEqual(wolf["spike_ratio"], 2.0)
        tgs = next(row for row in rows if "Tokyo Game Show" in row["query"])
        self.assertEqual(tgs["kind"], "event")
        self.assertEqual(tgs["google_searches"], 0)

    def test_event_google_searches_match_the_event_name(self) -> None:
        rows = build_lookup_interest(
            google=[{"title": "Tokyo Game Show schedule", "traffic": 12_000, "geo": "JP"}],
            wiki=[],
            catalog=[WOLVERINE],
            events=[TGS],
            as_of=date(2026, 9, 3),
        )
        tgs = next(row for row in rows if "Tokyo Game Show" in row["query"])
        self.assertEqual(tgs["google_searches"], 12_000)
        self.assertEqual(tgs["searches"], 12_000)

    def test_featured_product_pins_even_outside_the_near_window(self) -> None:
        targets = lookup_targets(
            [WOLVERINE, FABLE],
            [],
            as_of=date(2026, 9, 3),
            pin_products=[FABLE],
        )
        queries = {row["query"] for row in targets}
        self.assertIn("Fable", queries)

    def test_wiki_views_fill_in_search_count_when_google_is_quiet(self) -> None:
        rows = build_lookup_interest(
            google=[],
            wiki=[
                {
                    "article": "Marvel's Wolverine",
                    "views": 4_200,
                    "series": [("20260901", 3_800), ("20260902", 4_200)],
                }
            ],
            catalog=[WOLVERINE],
            events=[],
            as_of=date(2026, 9, 3),
        )
        wolf = next(row for row in rows if row["query"] == "Marvel's Wolverine")
        self.assertEqual(wolf["searches"], 8_000)
        self.assertEqual(wolf["search_source"], "wikipedia")

    def test_pageview_range_uses_recent_days_before_a_future_launch(self) -> None:
        start, end = _pageview_range(
            date(2026, 9, 3),
            14,
            (date(2026, 9, 1), date(2026, 9, 29)),
        )
        self.assertEqual(end, date(2026, 9, 2))
        self.assertEqual(start, date(2026, 8, 19))


if __name__ == "__main__":
    unittest.main()
