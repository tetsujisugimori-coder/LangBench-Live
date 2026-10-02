import copy
import hashlib
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
    ANALYSIS_CODE_SHA, MEASUREMENT_SHA256, build_comparison, build_v2_comparison, main,
    publish_outputs, render_markdown, validate_measurement,
)
from tests.test_measurement_provenance import manifest as measurement_manifest_v2

PACKAGE = ROOT / "artifacts/function-call-analysis-issue68-prb/analysis-package"
MEASUREMENT = ROOT / "artifacts/direct-function-call-balanced-order/manifest.json"
COMPARISON = ROOT / "artifacts/function-call-analysis-issue68-prb/comparison-portable"


class CompareFunctionCallAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.measurement = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        self.analysis = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        self.provenance = json.loads((PACKAGE / "provenance.json").read_text(encoding="utf-8"))

    def rows(self):
        result = build_comparison(self.measurement, self.analysis, self.provenance,
                                  MEASUREMENT_SHA256)
        return {row["language"]: row for row in result["languages"]}

    def test_v2_adapter_uses_fail_closed_comparison(self):
        result = build_v2_comparison(measurement_manifest_v2(), self.analysis, self.provenance)
        self.assertTrue(all(not row["exact_applicability"] for row in result["languages"]))
        javascript = next(row for row in result["languages"] if row["language"] == "javascript")
        self.assertEqual("missing", javascript["checks"]["exec_argv"])

    def test_public_manifest_has_canonical_lf_digest(self):
        contents = MEASUREMENT.read_bytes()
        self.assertNotIn(b"\r\n", contents)
        self.assertEqual(MEASUREMENT_SHA256, hashlib.sha256(contents).hexdigest())
        self.assertNotEqual(MEASUREMENT_SHA256,
                            hashlib.sha256(contents.replace(b"\n", b"\r\n")).hexdigest())

    def test_cli_reproduces_published_comparison_and_rejects_crlf_input(self):
        base = ROOT / "work" / f"comparison-cli-{uuid.uuid4().hex}"
        base.mkdir(parents=True)
        try:
            output = base / "from-public-input"
            args = ["compare", str(PACKAGE), str(MEASUREMENT), "--expected-sha",
                    ANALYSIS_CODE_SHA, "--json-output", str(output / "comparison.json"),
                    "--markdown-output", str(output / "comparison.md")]
            with patch.object(sys, "argv", args):
                self.assertEqual(0, main())
            self.assertEqual(json.loads((COMPARISON / "comparison.json").read_text(encoding="utf-8")),
                             json.loads((output / "comparison.json").read_text(encoding="utf-8")))
            self.assertEqual((COMPARISON / "comparison.md").read_text(encoding="utf-8"),
                             (output / "comparison.md").read_text(encoding="utf-8"))
            altered = base / "crlf-manifest.json"
            altered.write_bytes(MEASUREMENT.read_bytes().replace(b"\n", b"\r\n"))
            rejected = base / "rejected"
            args[2] = str(altered)
            args[6] = str(rejected / "comparison.json")
            args[8] = str(rejected / "comparison.md")
            with patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    main()
            self.assertFalse(rejected.exists())
        finally:
            shutil.rmtree(base)

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
        self.analysis["languages"]["javascript"]["condition"]["implementation"]["version"] = "13.6.233.17-node.52"
        self.assertFalse(self.rows()["javascript"]["implementation_match"])

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

    def test_every_published_evidence_path_exists_and_matches_hash(self):
        for row in self.rows().values():
            for item in row["analysis_evidence"]:
                published = ROOT / item["published_path"]
                self.assertTrue(published.is_file())
                self.assertEqual(item["sha256"], hashlib.sha256(published.read_bytes()).hexdigest())
                self.assertNotEqual(item["original_path"], item["published_path"])
        old_c = ROOT / self.rows()["c"]["analysis_evidence"][0]["original_path"]
        self.assertNotEqual(hashlib.sha256(old_c.read_bytes()).hexdigest(),
                            self.rows()["c"]["analysis_evidence"][0]["sha256"])

    def test_invalid_evidence_references_fail_before_output(self):
        evidence = self.analysis["languages"]["c"]["evidence"]
        original = evidence[0]["path"]
        for path in ("artifacts/function-call-analysis-old/main.s",
                     "artifacts/function-call-analysis/../main.s"):
            evidence[0]["path"] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "original evidence path"):
                self.rows()
        evidence[0]["path"] = original
        evidence[1]["path"] = original
        with self.assertRaisesRegex(ValueError, "basename collision"):
            self.rows()

    def test_missing_or_modified_published_evidence_fails_closed(self):
        base = ROOT / "work" / f"evidence-test-{uuid.uuid4().hex}"
        shutil.copytree(PACKAGE, base)
        try:
            (base / "main.s").unlink()
            with self.assertRaisesRegex(ValueError, "missing or differs"):
                build_comparison(self.measurement, self.analysis, self.provenance,
                                 MEASUREMENT_SHA256, base)
            shutil.copy2(PACKAGE / "main.s", base / "main.s")
            (base / "main.s").write_text("modified", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or differs"):
                build_comparison(self.measurement, self.analysis, self.provenance,
                                 MEASUREMENT_SHA256, base)
        finally:
            shutil.rmtree(base)

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
