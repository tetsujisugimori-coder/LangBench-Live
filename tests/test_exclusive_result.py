import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmarks/function_call_numeric_sum/python/main.py"
SPEC = importlib.util.spec_from_file_location("function_call_python_main", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExclusiveResultTests(unittest.TestCase):
    def test_exclusive_write_preserves_existing_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "diagnostics" / "python.json"
            path.parent.mkdir()
            original = b"existing diagnostic raw\n"
            path.write_bytes(original)

            with self.assertRaises(FileExistsError):
                MODULE.write_result(path, {"replacement": True}, exclusive=True)

            self.assertEqual(path.read_bytes(), original)

    def test_regular_write_keeps_existing_fixed_result_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            path.write_text("old", encoding="utf-8")

            MODULE.write_result(path, {"status": "success"})

            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "status": "success"\n}\n')


if __name__ == "__main__":
    unittest.main()
