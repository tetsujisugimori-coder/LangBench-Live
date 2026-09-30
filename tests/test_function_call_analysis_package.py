import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate_function_call_analysis import FILES, validate_package


class AnalysisPackageTests(unittest.TestCase):
    def make_package(self, root: Path) -> str:
        source = json.loads((ROOT / "artifacts/function-call-analysis/manifest.json").read_text(encoding="utf-8"))
        (root / "manifest.json").write_text(json.dumps(source), encoding="utf-8")
        for name in FILES - {"manifest.json"}:
            (root / name).write_text(f"fixture {name}\n", encoding="utf-8")
        sha = "a" * 40
        provenance = {
            "schema_version": "1.0", "analysis_id": source["analysis_id"], "code_sha": sha,
            "generated_at": "2026-09-30T00:00:00Z", "operating_system": "fixture Windows",
            "architecture": "x64", "measurement_orders": ["direct_first", "function_call_first"],
            "trace_is_benchmark": False,
            "evidence_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FILES},
        }
        (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        return sha

    def test_valid_fixture_and_expected_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); sha = self.make_package(root)
            self.assertEqual([], validate_package(root, sha))

    def test_modified_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); sha = self.make_package(root)
            (root / "main.s").write_text("changed", encoding="utf-8")
            self.assertTrue(any("modified" in error for error in validate_package(root, sha)))

    def test_wrong_sha_missing_evidence_and_trace_confusion_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.make_package(root)
            provenance = json.loads((root / "provenance.json").read_text())
            provenance["trace_is_benchmark"] = True
            (root / "provenance.json").write_text(json.dumps(provenance))
            (root / "python-bytecode.txt").unlink()
            errors = validate_package(root, "b" * 40)
            self.assertTrue(any("trusted main SHA" in error for error in errors))
            self.assertTrue(any("modified or is missing" in error for error in errors))
            self.assertTrue(any("must not" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
