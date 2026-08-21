from __future__ import annotations

import unittest

from src.priorities import filter_trend_bundle, match_google_trends


CATALOG = [
    {
        "canonical_title": "Fallout 4",
        "product_title": "Fallout 4",
        "product_type": "game",
        "release_date": "2015-11-10",
    },
    {
        "canonical_title": "Clair Obscur: Expedition 33",
        "product_title": "Clair Obscur: Expedition 33",
        "product_type": "game",
        "release_date": "2025-04-24",
    },
    {
        "canonical_title": "EA Sports FC 26",
        "product_title": "EA Sports FC 26",
        "product_type": "game",
        "release_date": "2025-09-26",
    },
]

EVENTS = [
    {
        "event": "Summer Game Fest",
        "related_game": "Multi-platform",
        "event_type": "Showcase",
    }
]


class TrendFilteringTests(unittest.TestCase):
    def test_news_blob_cannot_create_a_product_match(self) -> None:
        row = {
            "title": "Pep Guardiola",
            "blob": "Pep Guardiola fallout revealed in documentary",
            "news": ["Fallout revealed in documentary"],
        }
        self.assertEqual(match_google_trends(CATALOG, [row]), [])

    def test_only_product_and_event_terms_survive(self) -> None:
        bundle = {
            "google_trends": [
                {"title": "weather today", "traffic": 500_000},
                {"title": "Clair Obscur Expedition 33 soundtrack", "traffic": 20_000},
                {"title": "Summer Game Fest schedule", "traffic": 10_000},
                {"title": "FIFA update", "traffic": 5_000},
                {"title": "Alexandra Eala", "blob": "Alexandra Eala tennis news", "traffic": 50_000},
            ],
            "wikipedia": [
                {"article": "Fallout", "queries": ["fallout"]},
                {"article": "Weather", "queries": ["weather"]},
            ],
        }

        filtered = filter_trend_bundle(CATALOG, EVENTS, bundle)

        self.assertEqual(
            [row["title"] for row in filtered["google_trends"]],
            [
                "Clair Obscur Expedition 33 soundtrack",
                "Summer Game Fest schedule",
                "FIFA update",
            ],
        )
        self.assertEqual(
            [row["article"] for row in filtered["wikipedia"]],
            ["Fallout"],
        )
        self.assertEqual(filtered["filter"]["google_removed"], 2)


if __name__ == "__main__":
    unittest.main()
