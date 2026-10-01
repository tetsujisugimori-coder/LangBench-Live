import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_function_call_artifact_safety import DuplicateJsonKey, issues, redact, scan
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

    def test_json_credential_fields_are_redacted_without_losing_safe_evidence(self):
        original = (r'{"password":"dummy-pass","nested":{"ToKeN":"dummy-token",'
                    r'"reason":"safe failure","exit_code":23},"events":[{'
                    r'"\u0073ecret":{"child":"dummy-child","trace":["prior trace"]},'
                    r'"AUTHORIZATION":"Basic ZHVtbXk="}],'
                    r'"authorization":["dummy-array",{"child":"dummy-child-2"}],'
                    r'"option":"cl /O2 /EHsc main.c","trace":"safe trace"}')
        self.assertEqual(["credential"], issues(original))
        cleaned, counts = redact(original)
        self.assertEqual({"credential": 5}, counts)
        decoded = json.loads(cleaned)
        self.assertEqual("<redacted-credential>", decoded["password"])
        self.assertEqual("<redacted-credential>", decoded["nested"]["ToKeN"])
        self.assertEqual("<redacted-credential>", decoded["events"][0]["secret"])
        self.assertEqual("<redacted-credential>", decoded["events"][0]["AUTHORIZATION"])
        self.assertEqual("<redacted-credential>", decoded["authorization"])
        self.assertEqual("safe failure", decoded["nested"]["reason"])
        self.assertEqual(23, decoded["nested"]["exit_code"])
        self.assertEqual("cl /O2 /EHsc main.c", decoded["option"])
        self.assertEqual("safe trace", decoded["trace"])
        for forbidden in ("dummy-pass", "dummy-token", "dummy-child", "dummy-array", "ZHVtbXk="):
            self.assertNotIn(forbidden, cleaned)
        self.assertEqual([], issues(cleaned))
        self.assertEqual((cleaned, {}), redact(cleaned))

    def test_prepare_redacts_json_fields_and_keeps_raw_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            raw, bundle = Path(directory) / "raw", Path(directory) / "upload"
            raw.mkdir()
            (raw / "run-state.json").write_text('{"status":"failed"}', encoding="utf-8")
            original = (r'{"password":"dummy-pass","nested":{"TOKEN":{"child":"dummy-child"}},'
                        r'"events":[{"authorization":"Basic ZHVtbXk="}],'
                        r'"reason":"safe error","exit_code":23,"trace":"prior trace",'
                        r'"option":"cl /O2 /EHsc main.c"}')
            diagnostic = raw / "diagnostic.json"
            diagnostic.write_text(original, encoding="utf-8")
            self.assertIn("credential", scan(raw)[0])
            report = prepare(raw, bundle)
            self.assertEqual(original, diagnostic.read_text(encoding="utf-8"))
            uploaded = (bundle / diagnostic.name).read_text(encoding="utf-8")
            self.assertNotIn("dummy-pass", uploaded)
            self.assertNotIn("dummy-child", uploaded)
            self.assertNotIn("ZHVtbXk=", uploaded)
            decoded = json.loads(uploaded)
            self.assertEqual("safe error", decoded["reason"])
            self.assertEqual(23, decoded["exit_code"])
            self.assertEqual("prior trace", decoded["trace"])
            self.assertEqual("cl /O2 /EHsc main.c", decoded["option"])
            record = next(item for item in report["files"] if item["file"] == diagnostic.name)
            self.assertEqual({"credential": 3}, record["redactions"])
            self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), record["raw_sha256"])
            self.assertEqual(hashlib.sha256(uploaded.encode()).hexdigest(), record["upload_sha256"])
            self.assertEqual([], scan(bundle))

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
                     "cl /O2 /EHsc main.c", "option /quiet",
                     "<checkout>/tools/trace.js", "<analysis-package>/main.s",
                     "<shared-repository>/results",
                     r"https:\/\/example.com\/srv\/private"):
            with self.subTest(safe=safe):
                self.assertEqual([], issues(safe))
                self.assertEqual((safe, {}), redact(safe))
        for unsafe in ("cwd = /secret/", "path = /tmp/", "return /etc/",
                       "trace (/home/)", "cwd = /quiet",
                       "stderr >/tmp/private.log", "path:/home/alice/file",
                       "tag=<note>/srv/private", r"\/home\/alice", r"\/tmp",
                       r"stderr >\/tmp\/private.log", r"path:\/home\/alice"):
            with self.subTest(unsafe=unsafe):
                self.assertIn("absolute path", issues(unsafe))
                self.assertEqual([], issues(redact(unsafe)[0]))
        escaped_json = r'{"cwd":"\/home\/alice"}'
        self.assertIn("absolute path", issues(escaped_json))
        cleaned, counts = redact(escaped_json)
        self.assertEqual({"absolute path": 1}, counts)
        self.assertEqual("<redacted-absolute-path>", json.loads(cleaned)["cwd"])
        nested_json = (r'{"cwd":"\/\u0068ome\/alice","nested":[{"path":"C:\\Users\\alice\\private"},'
                       r'{"url":"https:\/\/example.com\/srv\/private"}]}')
        self.assertIn("absolute path", issues(nested_json))
        cleaned, counts = redact(nested_json)
        nested = json.loads(cleaned)
        self.assertEqual({"absolute path": 2}, counts)
        self.assertEqual("<redacted-absolute-path>", nested["cwd"])
        self.assertEqual("<redacted-absolute-path>", nested["nested"][0]["path"])
        self.assertEqual("https://example.com/srv/private", nested["nested"][1]["url"])
        self.assertEqual([], issues(cleaned))
        unsafe_key = r'{"\/\u0068ome\/alice":"safe"}'
        self.assertIn("absolute path", issues(unsafe_key))
        self.assertEqual({"<redacted-absolute-path>": "safe"}, json.loads(redact(unsafe_key)[0]))
        colliding = r'{"/home/alice/a":"first","/home/bob/b":"second","/tmp":"third"}'
        collision_result = json.loads(redact(colliding)[0])
        self.assertEqual(["first", "second", "third"], list(collision_result.values()))
        self.assertEqual(["<redacted-absolute-path>", "<redacted-absolute-path>-1",
                          "<redacted-absolute-path>-2"], list(collision_result))
        credentials = r'{"ghp_abcdefghijklmnop":"first","ghp_qrstuvwxyzabcdefgh":"second"}'
        credential_result = json.loads(redact(credentials)[0])
        self.assertEqual(["first", "second"], list(credential_result.values()))
        self.assertEqual(["<redacted-credential>", "<redacted-credential>-1"], list(credential_result))
        for duplicate in (r'{"cwd":"/home/alice","cwd":"safe"}',
                          r'{"cwd":"safe","cwd":"/home/alice"}',
                          r'{"nested":{"cwd":"\/\u0068ome\/alice","cwd":"safe"}}',
                          r'{"credential":"ghp_abcdefghijklmnop","credential":"safe"}',
                          r'{"CWD":"/tmp","cwd":"safe"}'):
            with self.subTest(duplicate=duplicate):
                self.assertEqual(["duplicate JSON key"], issues(duplicate))
                with self.assertRaises(DuplicateJsonKey):
                    redact(duplicate)
        for unsafe in ("return /etc/gg;", "return /etc/uv;", "if (/home/gg)",
                       "const r = /foo/;", "const r = /foo/",
                       "return /foo/g", "return /etc/"):
            with self.subTest(trace=unsafe):
                self.assertIn("absolute path", issues(unsafe))
                self.assertEqual([], issues(redact(unsafe)[0]))

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

    def test_trace_copy_preserves_javascript_and_redacts_diagnostic_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, bundle = root / "raw", root / "upload"
            raw.mkdir()
            (raw / "run-state.json").write_text('{"status":"failed"}', encoding="utf-8")
            trace = raw / "v8-optimization-direct_first.txt"
            trace.write_text("[marking function for optimization]\nreturn /etc/gg;\ncwd = /secret/\n", encoding="utf-8")
            self.assertTrue(scan(raw))
            prepare(raw, bundle)
            uploaded = (bundle / trace.name).read_text(encoding="utf-8")
            self.assertIn("[marking function for optimization]", uploaded)
            self.assertNotIn("/etc/gg", uploaded)
            self.assertIn("cwd = <redacted-absolute-path>", uploaded)
            self.assertEqual([], scan(bundle))

    def test_scan_rejection_after_validation_cannot_enter_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, bundle = root / "raw", root / "upload"
            (raw / "stage-logs").mkdir(parents=True)
            (raw / "run-state.json").write_text(
                r'{"status":"success","cwd":"\/\u0068ome\/alice","paths":["\/tmp","safe"]}',
                encoding="utf-8")
            (raw / "validation.json").write_text('{"status":"valid"}', encoding="utf-8")
            (raw / "stage-logs" / "validator.stderr.txt").write_text(
                "safe validation reason\nlate \\\\server\\share\\private\\path\n"
                "stderr >/tmp/private.log\nsafe exit code 23\n", encoding="utf-8")
            (raw / "main.s").write_text("secret=dummyvalue", encoding="utf-8")
            duplicate = r'{"cwd":"/home/alice","cwd":"safe"}'
            (raw / "duplicate.json").write_text(duplicate, encoding="utf-8")
            colliding = r'{"/home/alice/a":"first","/home/bob/b":"second","/tmp":"third"}'
            (raw / "collision.json").write_text(colliding, encoding="utf-8")
            self.assertTrue(scan(raw))
            report = prepare(raw, bundle)
            self.assertEqual("partial", report["bundle_status"])
            self.assertFalse((bundle / "duplicate.json").exists())
            excluded = next(item for item in report["excluded_files"] if item["file"] == "duplicate.json")
            self.assertEqual("duplicate JSON key", excluded["reason"])
            self.assertEqual(hashlib.sha256(duplicate.encode()).hexdigest(), excluded["raw_sha256"])
            uploaded_collision = json.loads((bundle / "collision.json").read_text())
            self.assertEqual(["first", "second", "third"], list(uploaded_collision.values()))
            collision_record = next(item for item in report["files"] if item["file"] == "collision.json")
            self.assertEqual({"absolute path": 3}, collision_record["redactions"])
            self.assertEqual(hashlib.sha256(colliding.encode()).hexdigest(), collision_record["raw_sha256"])
            self.assertEqual(hashlib.sha256((bundle / "collision.json").read_bytes()).hexdigest(),
                             collision_record["upload_sha256"])
            self.assertEqual("<redacted-absolute-path>", json.loads((bundle / "run-state.json").read_text())["cwd"])
            self.assertEqual("<redacted-absolute-path>", json.loads((bundle / "run-state.json").read_text())["paths"][0])
            self.assertIn("<redacted-credential>", (bundle / "main.s").read_text())
            validator_log = (bundle / "stage-logs" / "validator.stderr.txt").read_text()
            self.assertIn("safe validation reason", validator_log)
            self.assertIn("safe exit code 23", validator_log)
            self.assertIn("<redacted-absolute-path>", validator_log)
            self.assertNotIn("/tmp/private.log", validator_log)
            file_record = next(item for item in report["files"] if item["file"] == "stage-logs/validator.stderr.txt")
            self.assertEqual(hashlib.sha256((raw / "stage-logs" / "validator.stderr.txt").read_bytes()).hexdigest(), file_record["raw_sha256"])
            self.assertEqual(hashlib.sha256((bundle / "stage-logs" / "validator.stderr.txt").read_bytes()).hexdigest(), file_record["upload_sha256"])
            self.assertEqual({"absolute path": 2}, file_record["redactions"])
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
