import json
import re
import unittest
from pathlib import Path

from tools.validate_result_json import ROOT_KEYS, normalize_legacy_result, validate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATHS = [
    PROJECT_ROOT / "results" / f"jit_object_numeric_sum_{language}_result.json"
    for language in ("python", "javascript", "c")
]


class ResultSchemaTests(unittest.TestCase):
    def test_readme_json_example_is_parseable(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### 結果JSON正式仕様（schema 1.0）", 1)[1]
        match = re.search(r"```json\s+(.*?)\s+```", section, re.DOTALL)
        self.assertIsNotNone(match)
        document = json.loads(match.group(1))
        self.assertEqual(ROOT_KEYS, list(document))

    def test_tracked_samples_follow_formal_schema(self) -> None:
        documents = []
        for path in RESULT_PATHS:
            with self.subTest(path=path):
                document = json.loads(path.read_text(encoding="utf-8"))
                documents.append(document)
                self.assertEqual([], validate(document, path))
                self.assertEqual(ROOT_KEYS, list(document))
        self.assertEqual(1, len({document["experiment_id"] for document in documents}))
        root_types = [{key: type(document[key]) for key in ROOT_KEYS} for document in documents]
        self.assertTrue(all(types == root_types[0] for types in root_types[1:]))

    def test_legacy_object_result_is_normalized(self) -> None:
        legacy = {
            "experiment": "jit_object_numeric_sum",
            "array_size": 3,
            "iterations": 2,
            "setup_ms": 1.0,
            "expected_checksum": 6,
            "results": [
                {"elapsed_ms": 0.25, "checksum": 6},
                {"elapsed_ms": 0.5, "checksum": 6},
            ],
            "timing": {"total_ms": 1.75},
        }
        normalized = normalize_legacy_result(legacy)
        self.assertEqual("jit_object_numeric_sum", normalized["benchmark"])
        self.assertEqual(3, normalized["item_count"])
        self.assertEqual(2, normalized["measurement_iterations"])
        self.assertEqual([0.25, 0.5], normalized["samples_ms"])
        self.assertEqual(0.75, normalized["measurement_ms"])
        self.assertEqual(1.75, normalized["benchmark_total_ms"])
        self.assertEqual(6, normalized["checksum"])
        self.assertEqual(6, normalized["expected_checksum"])


if __name__ == "__main__":
    unittest.main()
