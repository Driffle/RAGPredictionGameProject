from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from src.load_data import gzip_sidecar, open_tabular, parse_date
from src.paths import catalog_path


class TabularLoaderTests(unittest.TestCase):
    def test_parse_date_iso_is_fast_path(self) -> None:
        self.assertEqual(parse_date("2026-08-26").isoformat(), "2026-08-26")
        self.assertIsNone(parse_date("0017-01-01"))

    def test_open_tabular_prefers_gzip_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.csv"
            gz = gzip_sidecar(path)
            path.write_text("name\nold\n", encoding="utf-8")
            with gzip.open(gz, "wt", encoding="utf-8") as handle:
                handle.write("name\nnew\n")
            with open_tabular(path) as handle:
                self.assertEqual(handle.read(), "name\nnew\n")

    def test_catalog_path_prefers_gzip(self) -> None:
        chosen = catalog_path()
        self.assertTrue(chosen.exists())
        self.assertTrue(str(chosen).endswith(".csv.gz") or chosen.suffix == ".csv")


class CorpusPersistTests(unittest.TestCase):
    def test_persist_corpus_writes_gzip_and_drops_plain(self) -> None:
        from src.documents import persist_corpus

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corpus.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            written = persist_corpus([{"id": "a", "text": "hello"}], path=path)
            self.assertTrue(str(written).endswith(".jsonl.gz"))
            self.assertTrue(written.exists())
            self.assertFalse(path.exists())
            with gzip.open(written, "rt", encoding="utf-8") as handle:
                self.assertIn("hello", handle.read())
