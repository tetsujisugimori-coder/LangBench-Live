from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.verify_direct_function_call_public_data import verify_public_data


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "artifacts" / "direct-function-call-comparison"
MANIFEST = ROOT / "artifacts" / "function-call-analysis" / "manifest.json"
PUBLIC_FILES = ("public-data.json", "public-data.csv", "public-samples.csv", "summary.md")


class PublicDirectFunctionCallDataTests(unittest.TestCase):
    def test_published_samples_recalculate_all_aggregates(self):
        verify_public_data(PUBLIC_DIR, MANIFEST)

    def test_duplicate_sample_order_fails_verification(self):
        with tempfile.TemporaryDirectory(prefix="function-call-public-data-") as temp:
            copied = Path(temp)
            for name in PUBLIC_FILES:
                shutil.copy2(PUBLIC_DIR / name, copied / name)
            sample_path = copied / "public-samples.csv"
            with sample_path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                fieldnames = reader.fieldnames
                rows = list(reader)
            rows[0]["sample_order"] = "2"
            with sample_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "sample order must be exactly 1..50"):
                verify_public_data(copied, MANIFEST)


if __name__ == "__main__":
    unittest.main()
