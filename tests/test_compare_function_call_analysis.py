import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from compare_function_call_analysis import build_comparison, render_markdown


class CompareFunctionCallAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.measurement = json.loads((ROOT / "artifacts/direct-function-call-balanced-order/manifest.json").read_text())
        self.analysis = {
            "analysis_id": "issue68-test", "languages": {
                "c": {"condition": {"source_sha256": "b107c19cdcc972e23c5968cc217f7c9ec88b06b840ab5aac8daa888fbe16cad3", "implementation": {"name": "GCC", "version": "16.1.0"}, "architecture": "x64", "options": ["-O2", "-std=c11", "-Wall", "-Wextra"]}},
                "python": {"condition": {"source_sha256": "f174bd2a03c028a333aa26550185fb2aa9636fe1b48235d68e14e6ef6252adcc", "implementation": {"name": "CPython", "version": "3.14.7"}, "architecture": "amd64", "options": []}},
                "javascript": {"condition": {"source_sha256": "6fe69643f08742fc7aaf51ba0b65a9312add16f5ed9ae9eacf3d2426c1d91473", "implementation": {"name": "V8", "version": "13.6.233.17-node.53"}, "architecture": "x64", "options": []}, "runtime": {"name": "Node.js", "version": "v24.20.0"}},
            }}
        coverage = {lang: {"basis": "trace_observed" if lang == "javascript" else "static_analysis", "confirmed": ["direct_first", "function_call_first"], "unconfirmed": []} for lang in ("c", "python", "javascript")}
        self.provenance = {"code_sha": "9" * 40, "trace_is_benchmark": False, "order_coverage": coverage}

    def test_exact_matches_are_separate_from_javascript_mismatch(self):
        result = build_comparison(self.measurement, self.analysis, self.provenance)
        rows = {row["language"]: row for row in result["languages"]}
        self.assertTrue(rows["c"]["exact_applicability"])
        self.assertTrue(rows["python"]["exact_applicability"])
        self.assertFalse(rows["javascript"]["source_exact_match"])
        self.assertFalse(rows["javascript"]["exact_applicability"])
        self.assertEqual("unknown", rows["javascript"]["impact"])
        self.assertEqual("not_established", result["causal_conclusion"])
        self.assertFalse(result["trace_is_benchmark"])

    def test_each_condition_mismatch_is_visible(self):
        self.analysis["languages"]["c"]["condition"].update(architecture="arm64", options=[])
        self.analysis["languages"]["python"]["condition"]["implementation"]["version"] = "3.13.0"
        rows = {row["language"]: row for row in build_comparison(self.measurement, self.analysis, self.provenance)["languages"]}
        self.assertFalse(rows["c"]["architecture_match"])
        self.assertFalse(rows["c"]["options_match"])
        self.assertFalse(rows["python"]["version_match"])

    def test_markdown_preserves_non_causal_language(self):
        text = render_markdown(build_comparison(self.measurement, self.analysis, self.provenance))
        self.assertIn("性能本測定ではない", text)
        self.assertIn("因果関係を示さない", text)
        self.assertIn("| javascript | no |", text)

    def test_missing_measurement_hash_fails_closed(self):
        self.measurement["input_sha256"] = []
        with self.assertRaisesRegex(ValueError, "source hashes"):
            build_comparison(self.measurement, self.analysis, self.provenance)


if __name__ == "__main__":
    unittest.main()
