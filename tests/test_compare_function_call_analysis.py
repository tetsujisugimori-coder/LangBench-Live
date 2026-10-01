import copy
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from compare_function_call_analysis import (
    ANALYSIS_CODE_SHA, MEASUREMENT_SHA256, build_comparison, main,
    publish_outputs, render_markdown, validate_measurement,
)

PACKAGE = ROOT / "artifacts/function-call-analysis-issue68-prb/analysis-package"
MEASUREMENT = ROOT / "artifacts/direct-function-call-balanced-order/manifest.json"


class CompareFunctionCallAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.measurement = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        self.analysis = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        self.provenance = json.loads((PACKAGE / "provenance.json").read_text(encoding="utf-8"))

    def rows(self):
        result = build_comparison(self.measurement, self.analysis, self.provenance,
                                  MEASUREMENT_SHA256)
        return {row["language"]: row for row in result["languages"]}

    def test_real_conditions_fail_closed(self):
        rows = self.rows()
        self.assertTrue(rows["c"]["exact_applicability"])
        self.assertFalse(rows["python"]["options_match"])
        self.assertEqual(["optimize=0"], rows["python"]["analysis_options"])
        self.assertEqual([], rows["python"]["measurement_options"])
        self.assertFalse(rows["python"]["exact_applicability"])
        self.assertFalse(rows["javascript"]["source_exact_match"])
        self.assertFalse(rows["javascript"]["implementation_match"])
        self.assertFalse(rows["javascript"]["exact_applicability"])
        self.assertEqual("unknown", rows["javascript"]["impact"])

    def test_v8_only_mismatch(self):
        self.measurement["host"]["v8"] = "13.6.233.17-node.53"
        self.assertTrue(self.rows()["javascript"]["implementation_match"])
        self.analysis["languages"]["javascript"]["condition"]["implementation"]["version"] = "13.5.0"
        self.assertFalse(self.rows()["javascript"]["implementation_match"])
        self.assertTrue(self.rows()["javascript"]["runtime_match"])

    def test_node_only_mismatch(self):
        self.analysis["languages"]["javascript"]["runtime"]["version"] = "v23.0.0"
        self.assertFalse(self.rows()["javascript"]["runtime_match"])

    def test_missing_or_unknown_order_fails_closed(self):
        self.provenance["order_coverage"]["c"]["confirmed"] = ["direct_first"]
        self.provenance["order_coverage"]["c"]["unconfirmed"] = ["function_call_first"]
        self.assertFalse(self.rows()["c"]["order_coverage_match"])
        self.assertFalse(self.rows()["c"]["exact_applicability"])
        self.provenance["order_coverage"]["c"] = {"basis": "static_analysis", "confirmed": ["unknown"], "unconfirmed": []}
        self.assertFalse(self.rows()["c"]["order_coverage_match"])

    def test_other_or_modified_measurement_rejected(self):
        for field, value in (("series_id", "other"), ("measurement_git_sha", "0" * 40),
                             ("issue", 67), ("benchmark", "other"), ("status", "failed")):
            changed = copy.deepcopy(self.measurement)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "identity mismatch"):
                validate_measurement(changed, MEASUREMENT_SHA256)
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            validate_measurement(self.measurement, "0" * 64)

    def test_missing_source_hash_fails_closed(self):
        self.measurement["input_sha256"] = []
        with self.assertRaisesRegex(ValueError, "source hashes"):
            self.rows()
        self.measurement = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        self.analysis["languages"]["c"]["condition"]["source_sha256"] = None
        self.assertFalse(self.rows()["c"]["exact_applicability"])

    def test_markdown_records_limits(self):
        result = build_comparison(self.measurement, self.analysis, self.provenance,
                                  MEASUREMENT_SHA256)
        text = render_markdown(result)
        self.assertIn("optimize=0", text)
        self.assertIn("V8", text)
        self.assertIn("因果関係を示さない", text)
        self.assertEqual("not_established", result["causal_conclusion"])

    def test_collision_and_validation_failure_do_not_overwrite(self):
        base = ROOT / "work" / f"comparison-test-{uuid.uuid4().hex}"
        base.mkdir(parents=True)
        try:
            output = base / "comparison"
            output.mkdir()
            original = output / "comparison.json"
            original.write_text("existing", encoding="utf-8")
            result = build_comparison(self.measurement, self.analysis, self.provenance,
                                      MEASUREMENT_SHA256)
            with self.assertRaises(FileExistsError):
                publish_outputs(original, output / "comparison.md", result)
            self.assertEqual("existing", original.read_text(encoding="utf-8"))
            with patch("compare_function_call_analysis.validate_package", return_value=["invalid"]):
                with patch.object(sys, "argv", ["compare", str(PACKAGE), str(MEASUREMENT),
                                                "--expected-sha", ANALYSIS_CODE_SHA,
                                                "--json-output", str(original),
                                                "--markdown-output", str(output / "comparison.md")]):
                    with self.assertRaises(SystemExit):
                        main()
            self.assertEqual("existing", original.read_text(encoding="utf-8"))
            self.assertFalse((output / "comparison.md").exists())
        finally:
            shutil.rmtree(base)


if __name__ == "__main__":
    unittest.main()
