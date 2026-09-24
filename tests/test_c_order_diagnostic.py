import copy
import json
import unittest
from pathlib import Path

from tools.summarize_c_order_diagnostic import build_public, markdown, statistics
from tools.validate_result_json import validate
from tests.test_result_schema import function_call_document


ROOT = Path(__file__).resolve().parents[1]


class COrderDiagnosticTests(unittest.TestCase):
    def test_reverse_result_is_excluded_from_normal_validation(self):
        document = function_call_document("c")
        document["execution"]["measurement_order"] = ["function_call", "direct"]
        self.assertTrue(validate(document, Path("reverse.json")))
        self.assertFalse(validate(document, Path("reverse.json"), allow_diagnostic_order=True))
        document["execution"]["measurement_order"] = ["direct", "function_call"]
        self.assertFalse(validate(document, Path("direct.json")))

    def test_statistics_use_input_order_and_cutoff_is_descriptive(self):
        samples = [0.1] * 25 + [0.3] * 25
        self.assertEqual(statistics(samples), {"median_ms": 0.2,
            "first_25_median_ms": 0.1, "last_25_median_ms": 0.3,
            "at_least_0_2_ms": 25})

    def test_failed_attempt_is_recorded_without_success_samples(self):
        record = {"git_head": "abc", "c_source_sha256": "0" * 64,
                  "runs": [{"order": "A", "started_at": "start", "ended_at": "end",
                            "status": "failed", "reason_code": "RUN_FAILED"}]}
        public = build_public(record, ROOT)
        self.assertEqual(public["runs"][0]["status"], "failed")
        self.assertNotIn("cases", public["runs"][0])
        record["runs"][0]["order"] = "B"
        with self.assertRaisesRegex(ValueError, "fixed AB/BA plan"):
            build_public(record, ROOT)

    def test_published_table_recomputes_from_all_samples(self):
        for prefix in ("", "pilot-"):
            with self.subTest(prefix=prefix):
                public_path = ROOT / f"artifacts/c-order-diagnostic/{prefix}public-data.json"
                table_path = ROOT / f"artifacts/c-order-diagnostic/{prefix}summary.md"
                public = json.loads(public_path.read_text(encoding="utf-8"))
                self.assertEqual(len(public["runs"]), 20)
                self.assertEqual([run["order"] for run in public["runs"]], public["plan"])
                self.assertEqual(sum(run["order"] == "A" for run in public["runs"]), 10)
                self.assertEqual(sum(run["order"] == "B" for run in public["runs"]), 10)
                for run in public["runs"]:
                    self.assertEqual(run["measurement_order"], ["direct", "function_call"] if run["order"] == "A" else ["function_call", "direct"])
                    if run["status"] == "success":
                        self.assertEqual(run["checksums"], {"direct": 500000500000, "function_call": 500000500000})
                        for case in ("direct", "function_call"):
                            item = run["cases"][case]
                            self.assertEqual(len(item["samples_ms"]), 50)
                            for field, value in statistics(item["samples_ms"]).items():
                                self.assertEqual(item[field], value)
                self.assertEqual(markdown(public), table_path.read_text(encoding="utf-8"))
                self.assertNotIn("C:\\", public_path.read_text(encoding="utf-8"))
                altered = copy.deepcopy(public)
                altered["runs"][0]["cases"]["direct"]["median_ms"] += 1
                with self.assertRaisesRegex(ValueError, "published statistics differ"):
                    markdown(altered)


if __name__ == "__main__":
    unittest.main()
