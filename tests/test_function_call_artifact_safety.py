import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_function_call_artifact_safety import scan


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


if __name__ == "__main__":
    unittest.main()
