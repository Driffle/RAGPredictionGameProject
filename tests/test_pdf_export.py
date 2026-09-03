from __future__ import annotations

import unittest

from apps.pdf_export import (
    peek_pdf_export,
    safe_pdf_filename,
    store_pdf_export,
    take_pdf_export,
)


class PdfExportTests(unittest.TestCase):
    def test_safe_pdf_filename(self) -> None:
        self.assertEqual(safe_pdf_filename("floor-brief-trends.pdf"), "floor-brief-trends.pdf")
        self.assertEqual(safe_pdf_filename("../secret.txt"), "secret.txt.pdf")
        self.assertTrue(safe_pdf_filename("hi").endswith(".pdf"))

    def test_store_and_take(self) -> None:
        payload = b"%PDF-1.4\n%%EOF\n"
        token = store_pdf_export("Floor Brief Trends.pdf", payload)
        peeked = peek_pdf_export(token)
        self.assertIsNotNone(peeked)
        self.assertEqual(peeked[0], "Floor_Brief_Trends.pdf")
        self.assertEqual(peeked[1], payload)
        taken = take_pdf_export(token)
        self.assertEqual(taken, ("Floor_Brief_Trends.pdf", payload))
        self.assertIsNone(take_pdf_export(token))

    def test_rejects_non_pdf(self) -> None:
        with self.assertRaises(ValueError):
            store_pdf_export("x.pdf", b"<html>nope</html>")


if __name__ == "__main__":
    unittest.main()
