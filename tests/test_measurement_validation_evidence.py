import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.build_measurement_validation_evidence import build


def archive_value():
    current = {"implementation": {"name": "x", "version": "1"}, "options": [], "source_sha256": "a" * 64}
    result = lambda language: {"environment": {"os": "Windows", "os_version": "10", "cpu": "cpu", "architecture": "x64"},
        "engine": {"runtime": language, "runtime_version": "1",
                   **({"v8_version": "1"} if language == "javascript" else {}),
                   **({"python_implementation": "CPython"} if language == "python" else {})},
        "build": {"compiler": "gcc", "compiler_version": "1"},
        "optimization_analysis": {"provenance": {"current": dict(current)}}}
    return {"definition": {"benchmark": "function_call_numeric_sum", "schema_version": "1.0", "config": {},
                            "expected_checksum": 1, "measurement_order": ["direct", "function_call"]},
            "results": {name: result(name) for name in ("c", "python", "javascript")}}


class MeasurementValidationEvidenceTests(unittest.TestCase):
    def test_controls_hashes_and_collision_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); archive = root / "archive"; archive.mkdir()
            (archive / "measurement-manifest.json").write_text('{"schema_version":"2.0"}\n', encoding="utf-8")
            destination = root / "evidence"
            with patch("tools.build_measurement_validation_evidence.load_archive", return_value=archive_value()):
                build(archive, destination, {"issue": 74})
                controls = json.loads((destination / "comparison-controls.json").read_text())
                self.assertEqual("comparable", controls["controls"]["match"]["verdict"])
                self.assertTrue(all(controls["controls"][name]["verdict"] != "comparable"
                                    for name in ("missing", "mismatch", "unknown")))
                hashes = json.loads((destination / "files.sha256.json").read_text())
                self.assertEqual({"README.md", "comparison-controls.json", "execution.json",
                                  "measurement-manifest.json", "validation.json"},
                                 {item["file"] for item in hashes["files"]})
                with self.assertRaisesRegex(ValueError, "already exists"):
                    build(archive, destination, {"issue": 74})


if __name__ == "__main__": unittest.main()
