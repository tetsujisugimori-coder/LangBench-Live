import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_function_call_artifact_safety import scan
from prepare_function_call_analysis_upload import prepare


class ArtifactSafetyTests(unittest.TestCase):
    def test_rejects_paths_and_credentials_without_echoing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "stage-logs").mkdir()
            (root / "stage-logs" / "stage.stderr.txt").write_text(
                "C:\\Users\\alice\\private ghp_abcdefghijklmnopqrst token=hiddenvalue",
                encoding="utf-8")
            errors = scan(root)
            self.assertTrue(any("absolute path" in error for error in errors))
            self.assertTrue(any("credential" in error for error in errors))
            self.assertNotIn("hiddenvalue", str(errors))
            self.assertNotIn("alice", str(errors))

    def test_sanitized_package_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run-state.json").write_text(
                '{"command":["python","<checkout>/tools/script.py"],"log":"<redacted>"}',
                encoding="utf-8")
            self.assertEqual([], scan(root))

    def test_drive_slash_and_workspace_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unsafe.txt").write_text("D:/a/LangBench/work /workspace/LangBench/work", encoding="utf-8")
            self.assertTrue(any("absolute path" in error for error in scan(root)))

    def test_failed_raw_keeps_only_inspected_diagnostics_in_upload_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, bundle = root / "raw", root / "upload"
            (raw / "stage-logs").mkdir(parents=True)
            (raw / "run-state.json").write_text('{"status":"failed"}', encoding="utf-8")
            (raw / "validation.json").write_text('{"status":"not_completed"}', encoding="utf-8")
            (raw / "stage-logs" / "gcc.stderr.txt").write_text("gcc exit 23", encoding="utf-8")
            (raw / "v8-optimization-direct_first.txt").write_text("safe prior trace", encoding="utf-8")
            (raw / "gcc-optimization.txt").write_text(
                "D:/a/private ghp_abcdefghijklmnopqrst", encoding="utf-8")
            report = prepare(raw, bundle)
            self.assertEqual("failed", report["raw_status"])
            self.assertEqual("partial", report["bundle_status"])
            self.assertFalse((bundle / "gcc-optimization.txt").exists())
            self.assertTrue((raw / "gcc-optimization.txt").exists())
            self.assertTrue((bundle / "run-state.json").exists())
            self.assertTrue((bundle / "stage-logs" / "gcc.stderr.txt").exists())
            self.assertTrue((bundle / "v8-optimization-direct_first.txt").exists())
            self.assertEqual([], scan(bundle))

    def test_scan_rejection_after_validation_cannot_enter_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, bundle = root / "raw", root / "upload"
            (raw / "stage-logs").mkdir(parents=True)
            (raw / "run-state.json").write_text('{"status":"success"}', encoding="utf-8")
            (raw / "validation.json").write_text('{"status":"valid"}', encoding="utf-8")
            (raw / "stage-logs" / "validator.stderr.txt").write_text(
                "late /workspace/private/path", encoding="utf-8")
            (raw / "main.s").write_text("secret=dummyvalue", encoding="utf-8")
            self.assertTrue(scan(raw))
            report = prepare(raw, bundle)
            self.assertEqual("partial", report["bundle_status"])
            self.assertFalse((bundle / "main.s").exists())
            self.assertIn("<redacted unsafe diagnostic>", (bundle / "stage-logs" / "validator.stderr.txt").read_text())
            self.assertEqual([], scan(bundle))

    def test_safe_evidence_is_copied_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, bundle = root / "raw", root / "upload"
            raw.mkdir()
            (raw / "run-state.json").write_bytes(b'{"status":"success"}\r\n')
            (raw / "main.s").write_bytes(b".text\r\nret\r\n")
            report = prepare(raw, bundle)
            self.assertEqual("complete", report["bundle_status"])
            self.assertEqual((raw / "main.s").read_bytes(), (bundle / "main.s").read_bytes())


if __name__ == "__main__":
    unittest.main()
