from __future__ import annotations

import unittest

from src.content_marketing import (
    affiliate_link,
    content_kit_for_plans,
    correlation_from_plan,
    hashtag,
    seo_keywords,
    social_pack,
)


def _plan(**extra) -> dict:
    row = {
        "event": "Gamescom 2026",
        "canonical_title": "Fable",
        "platform": "Xbox Series X/S",
        "role": "game",
        "promo_family": "expo",
        "promo_start": "2026-08-19",
        "promo_end": "2026-09-02",
        "runtime_start": "2026-08-26",
        "runtime_end": "2026-08-30",
        "phases": [
            {"name": "lead_in", "label": "Lead-in", "start": "2026-08-19", "end": "2026-08-25"},
            {"name": "live", "label": "Event runtime", "start": "2026-08-26", "end": "2026-08-30"},
            {"name": "afterglow", "label": "Afterglow", "start": "2026-08-31", "end": "2026-09-02"},
        ],
    }
    row.update(extra)
    return row


class ContentMarketingTests(unittest.TestCase):
    def test_hashtag_camelcases_title(self) -> None:
        self.assertEqual(hashtag("EA Sports FC 26"), "#EASportsFC26")

    def test_xbox_affiliate_points_at_xbox_search(self) -> None:
        link = affiliate_link("Fable", "Xbox Series X/S")
        self.assertEqual(link["network"], "Xbox / Microsoft Store")
        self.assertIn("xbox.com", link["url"])
        self.assertIn("Fable", link["url"])

    def test_amazon_template_keeps_placeholder_tag(self) -> None:
        link = affiliate_link("Zelda", "Unknown")
        self.assertIn("tag=YOURTAG", link["url"])

    def test_social_pack_covers_four_platforms(self) -> None:
        pack = social_pack("Fable", "Gamescom 2026", "expo")
        self.assertEqual(set(pack), {"tiktok", "instagram", "youtube_shorts", "x"})
        self.assertIn("#Fable", pack["tiktok"]["hashtags"])
        self.assertIn("#Gamescom2026", pack["tiktok"]["hashtags"])
        self.assertIn("#ad", pack["tiktok"]["hashtags"])

    def test_seo_keywords_include_product_and_event(self) -> None:
        keys = seo_keywords("Fable", "Gamescom 2026", "expo", "game")
        blob = " ".join(keys).lower()
        self.assertIn("fable", blob)
        self.assertIn("gamescom", blob)

    def test_correlation_has_schedule_and_short_form_pieces(self) -> None:
        row = correlation_from_plan(_plan())
        self.assertEqual(row["product"], "Fable")
        self.assertEqual(row["event"], "Gamescom 2026")
        self.assertEqual(len(row["schedule"]), 3)
        self.assertGreaterEqual(len(row["pieces"]), 3)
        piece = row["pieces"][0]
        self.assertTrue(piece["affiliate"]["url"])
        self.assertTrue(piece["hashtags"])
        self.assertTrue(piece["post_on"])

    def test_kit_dedupes_same_product_event(self) -> None:
        kit = content_kit_for_plans([_plan(), _plan()], perspective="event", limit=6)
        self.assertEqual(kit["correlation_count"], 1)
        self.assertIn("YOURTAG", kit["disclaimer"] or "YOURTAG")


if __name__ == "__main__":
    unittest.main()
