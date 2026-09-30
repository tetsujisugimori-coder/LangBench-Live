import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_function_call_artifact_safety import issues, redact, scan
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

    def test_absolute_path_syntax_and_url_boundary(self):
        paths = [r"\\server\share\private\file.txt", r"\\?\C:\private\file.txt",
                 r"\\?\UNC\server\share\file.txt", r"\root\file.txt",
                 r"C:\private\file.txt", "D:/a/private/file.txt",
                 "/srv/private/file.txt", "/workspace/private/file.txt",
                 "/tmp", "/etc", r"\secret", "C:\\", "D:/",
                 "file:///C:/Users/alice/private", "file:///home/alice/private",
                 "/ユーザー/秘密"]
        for path in paths:
            with self.subTest(path=path):
                self.assertIn("absolute path", issues(path))
                sanitized, counts = redact(path)
                self.assertEqual({"absolute path": 1}, counts)
                self.assertEqual([], issues(sanitized))
        for safe in ("https://example.com/srv/private", r"split(/\s+/)",
                     "const r = /foo/;", "const r = /foo/i;",
                     "cl /O2 /EHsc main.c", "option /quiet"):
            with self.subTest(safe=safe):
                self.assertEqual([], issues(safe))
                self.assertEqual((safe, {}), redact(safe))

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
                "safe compiler reason\nD:/a/private ghp_abcdefghijklmnopqrst\nsafe final line\n", encoding="utf-8")
            report = prepare(raw, bundle)
            self.assertEqual("failed", report["raw_status"])
            self.assertEqual("partial", report["bundle_status"])
            report_text = (bundle / "gcc-optimization.txt").read_text(encoding="utf-8")
            self.assertIn("safe compiler reason", report_text)
            self.assertIn("safe final line", report_text)
            self.assertIn("<redacted-absolute-path>", report_text)
            self.assertIn("<redacted-credential>", report_text)
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
                "safe validation reason\nlate \\\\server\\share\\private\\path\nsafe exit code 23\n", encoding="utf-8")
            (raw / "main.s").write_text("secret=dummyvalue", encoding="utf-8")
            self.assertTrue(scan(raw))
            report = prepare(raw, bundle)
            self.assertEqual("partial", report["bundle_status"])
            self.assertIn("<redacted-credential>", (bundle / "main.s").read_text())
            validator_log = (bundle / "stage-logs" / "validator.stderr.txt").read_text()
            self.assertIn("safe validation reason", validator_log)
            self.assertIn("safe exit code 23", validator_log)
            self.assertIn("<redacted-absolute-path>", validator_log)
            file_record = next(item for item in report["files"] if item["file"] == "stage-logs/validator.stderr.txt")
            self.assertEqual(hashlib.sha256((raw / "stage-logs" / "validator.stderr.txt").read_bytes()).hexdigest(), file_record["raw_sha256"])
            self.assertEqual(hashlib.sha256((bundle / "stage-logs" / "validator.stderr.txt").read_bytes()).hexdigest(), file_record["upload_sha256"])
            self.assertEqual({"absolute path": 1}, file_record["redactions"])
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
            record = next(item for item in report["files"] if item["file"] == "main.s")
            self.assertEqual(record["raw_sha256"], record["upload_sha256"])

    def test_non_utf8_evidence_is_excluded_with_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, bundle = root / "raw", root / "upload"
            raw.mkdir()
            (raw / "run-state.json").write_text('{"status":"failed"}', encoding="utf-8")
            binary = b"\xff\x00\xfe"
            (raw / "main.s").write_bytes(binary)
            report = prepare(raw, bundle)
            self.assertFalse((bundle / "main.s").exists())
            self.assertEqual("non-UTF-8", report["excluded_files"][0]["reason"])
            self.assertEqual(hashlib.sha256(binary).hexdigest(), report["excluded_files"][0]["raw_sha256"])


if __name__ == "__main__":
    unittest.main()
