from __future__ import annotations

import unittest

from src.audit_changes import classify_event_change, classify_product_change, diff_datasets
from src.provenance import preserve_entry_date, stamp_provenance


class ProvenanceTests(unittest.TestCase):
    def test_entry_date_is_preserved_on_merge(self) -> None:
        existing = {"canonical_title": "Fable", "entry_date": "2024-01-10", "source": "announced_registry"}
        incoming = {"canonical_title": "Fable", "release_date": "2027-02-23", "source": "wikipedia"}
        merged = preserve_entry_date(existing, incoming, dict(incoming))
        self.assertEqual(merged["entry_date"], "2024-01-10")

    def test_stamp_adds_source_and_entry_date(self) -> None:
        row = stamp_provenance({"canonical_title": "Demo"}, default_source="catalog", on=__import__("datetime").date(2026, 8, 18))
        self.assertEqual(row["source"], "catalog")
        self.assertTrue(row["entry_date"])


class AuditChangeTests(unittest.TestCase):
    def test_delay_and_confirmation_flip(self) -> None:
        before = {
            "canonical_title": "Fable",
            "release_date": "2026-10-01",
            "confirmation": "announced TBA",
            "source": "announced_registry",
        }
        after = {
            "canonical_title": "Fable",
            "release_date": "2027-02-23",
            "confirmation": "confirmed",
            "source": "Xbox / Playground Games — Feb 23, 2027",
        }
        changes = classify_product_change(before, after)
        types = {row["change_type"] for row in changes}
        self.assertIn("delayed", types)
        self.assertIn("confirmed", types)

    def test_event_window_move(self) -> None:
        before = {"event": "The Game Awards", "start_date": "2026-09-01", "end_date": "2026-09-01", "status": "TBA"}
        after = {
            "event": "The Game Awards",
            "start_date": "2026-12-10",
            "end_date": "2026-12-10",
            "confirmation": "confirmed",
            "official_source": "thegameawards.com",
        }
        changes = classify_event_change(before, after)
        self.assertTrue(any(row["change_type"] == "delayed" for row in changes))
        self.assertTrue(any(row["change_type"] == "confirmed" for row in changes))

    def test_diff_datasets_flags_new_product(self) -> None:
        changes = diff_datasets(
            prev_products=[],
            next_products=[{"canonical_title": "Marvel's Wolverine", "release_date": "2026-09-15"}],
            prev_events=[],
            next_events=[],
        )
        self.assertEqual(changes[0]["change_type"], "added")


if __name__ == "__main__":
    unittest.main()
