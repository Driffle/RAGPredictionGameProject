from __future__ import annotations

import re
import unittest

from src.orders import parse_week_ranges


class OrderWeekParseTests(unittest.TestCase):
    def test_parses_pipe_separated_best_weeks(self) -> None:
        blob = (
            "2025-11-07 to 2025-11-13 (GMV: 121757.74) | "
            "2025-11-14 to 2025-11-20 (GMV: 72498.20)"
        )
        weeks = parse_week_ranges(blob, "best")
        self.assertEqual(len(weeks), 2)
        self.assertEqual(weeks[0]["week_start"], "2025-11-07")
        self.assertEqual(weeks[0]["week_end"], "2025-11-13")
        self.assertEqual(weeks[0]["week_gmv"], 121757.74)
        self.assertEqual(weeks[0]["week_rank"], 1)
        self.assertEqual(weeks[1]["week_rank"], 2)

    def test_order_dashboard_kpis_from_processed_files(self) -> None:
        from src.orders import load_order_dashboard

        payload = load_order_dashboard()
        kpis = payload.get("kpis") or {}
        self.assertGreater(kpis.get("sku_count") or 0, 10000)
        self.assertGreater(kpis.get("lifetime_gmv") or 0, 10_000_000)
        self.assertGreater(kpis.get("pct_2026_best_week_hit_event") or 0, kpis.get("pct_2024_best_week_hit_event") or 0)
        self.assertTrue(payload.get("top_events"))
        self.assertTrue(payload.get("missed_skus"))
        self.assertEqual(len(payload.get("period_top_products") or []), 5)
        self.assertEqual(len(payload.get("period_top_events") or []), 5)
        self.assertGreater(payload["kpis"].get("top5_product_gmv") or 0, 0)
        years = {row["year"]: row for row in payload.get("years") or []}
        self.assertEqual(set(years), {"2022", "2023", "2024", "2025", "2026"})
        for row in payload.get("period_top_products") or []:
            self.assertTrue(row.get("canonical_title"))
            self.assertIn("max_gmv_event", row)
            self.assertEqual([item.get("year") for item in row.get("year_max_events") or []], ["2022", "2023", "2024", "2025", "2026"])
        for row in payload.get("period_top_events") or []:
            self.assertTrue(row.get("event"))
            self.assertNotIn("q1", (row.get("event") or "").lower())
            for rec in row.get("recommended_products") or []:
                self.assertTrue(rec.get("canonical_title"))
                self.assertFalse(re.search(r"random 1 key|try to get", rec.get("canonical_title") or "", re.I))
        for year in ("2022", "2023", "2024", "2025", "2026"):
            self.assertLessEqual(len(years[year].get("top_products") or []), 5)
            self.assertLessEqual(len(years[year].get("top_events") or []), 5)
            self.assertIn("top5_product_share", years[year].get("kpis") or {})
            for row in years[year].get("top_products") or []:
                self.assertTrue(row.get("canonical_title"))
                self.assertIn("max_gmv_event", row)
            for row in years[year].get("top_events") or []:
                self.assertTrue(row.get("event"))
                self.assertIn("recommended_products", row)

    def test_empty_blob_is_empty_list(self) -> None:
        self.assertEqual(parse_week_ranges("", "worst"), [])

    def test_period_and_year_leaderboards_top5(self) -> None:
        from src.orders import period_and_year_leaderboards

        orders = []
        links = []
        for i in range(1, 7):
            title = f"Title {i}"
            orders.append(
                {
                    "product_id": str(i),
                    "canonical_title": title,
                    "product_title": title,
                    "total_gmv_2022_2026": 1000 * i,
                    "best_weeks": [
                        {
                            "week_kind": "best",
                            "week_rank": 1,
                            "week_start": f"2024-0{i}-01",
                            "week_end": f"2024-0{i}-07",
                            "week_gmv": 10 * i,
                        },
                        {
                            "week_kind": "best",
                            "week_rank": 2,
                            "week_start": f"2025-0{i}-01",
                            "week_end": f"2025-0{i}-07",
                            "week_gmv": 5 * i,
                        },
                    ],
                }
            )
            links.append(
                {
                    "product_id": str(i),
                    "event": f"Event {i}",
                    "event_type": "Trade Show",
                    "week_start": f"2024-0{i}-01",
                    "runtime_start": f"2024-0{i}-01",
                    "runtime_end": f"2024-0{i}-03",
                    "week_gmv": 8 * i,
                }
            )
        payload = period_and_year_leaderboards(orders, links)
        products = payload["top_products"]
        events = payload["top_events"]
        self.assertEqual(len(products), 5)
        self.assertEqual(len(events), 5)
        self.assertEqual(products[0]["canonical_title"], "Title 6")
        self.assertEqual(events[0]["event"], "Event 6")
        self.assertGreaterEqual(products[0]["lifetime_gmv"], products[-1]["lifetime_gmv"])
        years = {row["year"]: row for row in payload["years"]}
        self.assertEqual(set(years), {"2022", "2023", "2024", "2025", "2026"})
        self.assertEqual(years["2024"]["top_products"][0]["canonical_title"], "Title 6")
        self.assertEqual(years["2024"]["top_events"][0]["event"], "Event 6")
        self.assertEqual(years["2022"]["top_products"], [])
        self.assertEqual(products[0]["max_gmv_event"], "Event 6")
        self.assertEqual(products[0]["max_gmv_event_gmv"], 48.0)
        years_for_title = {row["year"]: row["max_gmv_event"] for row in products[0]["year_max_events"]}
        self.assertEqual(years_for_title["2024"], "Event 6")
        self.assertEqual(years_for_title["2022"], "")
        recs = events[0]["recommended_products"]
        self.assertEqual(recs[0]["canonical_title"], "Title 6")
        self.assertEqual(years["2024"]["top_products"][0]["max_gmv_event"], "Event 6")
        self.assertEqual(years["2024"]["top_events"][0]["recommended_products"][0]["canonical_title"], "Title 6")


if __name__ == "__main__":
    unittest.main()
