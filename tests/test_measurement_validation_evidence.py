import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_result_schema import build_optimization_analysis, function_call_document
from tools.archive_results import archive_results
from tools.build_measurement_validation_evidence import MANIFEST, build, comparison_controls


class MeasurementValidationEvidenceTests(unittest.TestCase):
    def run_builder(self, archive: Path, destination: Path, root: Path, stage: str | None = None):
        identity = root / "identity.json"
        identity.write_text(json.dumps({"issue": 74}), encoding="utf-8")
        env = os.environ.copy()
        if stage:
            env.update(LANGBENCH_HOSTED_FIXTURE="1", LANGBENCH_HOSTED_FAILURE_STAGE=stage)
        return subprocess.run([sys.executable, "-B", "tools/build_measurement_validation_evidence.py",
                               str(archive), str(destination), "--identity", str(identity)],
                              cwd=Path(__file__).resolve().parents[1], env=env,
                              capture_output=True, text=True, encoding="utf-8", check=False)

    def make_archive(self, root: Path, unsafe_option: str | None = None) -> Path:
        base = function_call_document("python")
        definition = root / "experiment-definition.json"
        definition.write_text(json.dumps({"schema_version": "1.0", "benchmark": "function_call_numeric_sum",
            "languages": ["c", "javascript", "python"], "config": base["config"],
            "expected_checksum": base["validation"]["expected_checksum"]}), encoding="utf-8")
        paths = []
        for language in ("python", "javascript", "c"):
            document = function_call_document(language); document["environment"].update(os="Windows", architecture="x64")
            if language == "python": document["engine"].update(runtime_version="3.14.7", python_implementation="CPython", python_optimize=0)
            if language == "javascript": document["engine"].update(runtime_version="v24.20.0", v8_version="13.6", exec_argv=[], node_options=unsafe_option or "")
            optimization = build_optimization_analysis(); condition = optimization["provenance"]["current"]
            if language == "c":
                condition["implementation"] = {"name": "GCC", "version": "gcc 15"}; condition["options"] = ["-O2"]
                optimization["jit"] = {"applicable": False, "result": "not_applicable"}
            if language == "javascript":
                optimization["provenance"]["applies_to"].insert(0, "jit")
                optimization["provenance"]["artifact_findings"]["jit"] = {"result": "not_detected"}
                if unsafe_option: condition["options"] = [unsafe_option]
            optimization["provenance"]["analysis"] = copy.deepcopy(condition); optimization["implementation"] = condition["implementation"]
            document = {**dict(list(document.items())[:13]), "optimization_analysis": optimization, **dict(list(document.items())[13:])}
            path = root / f"{language}.json"; path.write_text(json.dumps(document) + "\n", encoding="utf-8"); paths.append(path)
        runners = {name: {"path": name, "sha256": "c" * 64} for name in ("orchestrator", "c", "python", "javascript")}
        capture = {"schema_version": "1.0", "experiment_id": base["experiment_id"],
            "run_ids": {language: function_call_document(language)["run_id"] for language in ("c", "python", "javascript")},
            "measurement_git_sha": "b" * 40, "runners": runners,
            "sources": {language: {"path": f"main.{language}", "sha256": "a" * 64} for language in ("c", "python", "javascript")}}
        captured = root / "capture.json"; captured.write_text(json.dumps(capture), encoding="utf-8")
        return archive_results(paths, base["experiment_id"], root / "history", definition, captured)

    def test_formal_archive_controls_hashes_and_collision_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); archive = self.make_archive(root); destination = root / "evidence"
            originals = {path.name: path.read_bytes() for path in archive.iterdir() if path.is_file()}
            build(archive, destination, {"issue": 74, "sync_run_id": 123})
            controls = json.loads((destination / "comparison-controls.json").read_text(encoding="utf-8"))
            for language in ("c", "python", "javascript"):
                self.assertTrue(controls["languages"][language]["match"]["exact_applicability"])
                self.assertTrue(all(not controls["languages"][language][name]["exact_applicability"]
                                    for name in ("missing", "mismatch", "unknown")))
            hashes = json.loads((destination / "files.sha256.json").read_text(encoding="utf-8"))
            self.assertIn(MANIFEST, {item["file"] for item in hashes["files"]})
            self.assertEqual((archive / MANIFEST).read_bytes(), (destination / MANIFEST).read_bytes())
            manifest_entry = json.loads((destination / "archive.json").read_text(encoding="utf-8"))["measurement_manifest"]
            self.assertEqual(hashlib.sha256((destination / MANIFEST).read_bytes()).hexdigest(), manifest_entry["sha256"])
            for item in hashes["files"]:
                self.assertEqual(hashlib.sha256((destination / item["file"]).read_bytes()).hexdigest(), item["sha256"])
            self.assertFalse({"c.json", "python.json", "javascript.json"} & {path.name for path in destination.iterdir()})
            self.assertEqual(originals, {path.name: path.read_bytes() for path in archive.iterdir() if path.is_file()})
            manifest = json.loads((destination / MANIFEST).read_text(encoding="utf-8"))
            recalculated = comparison_controls(manifest)
            self.assertEqual(recalculated["languages"], controls["languages"])
            with self.assertRaisesRegex(ValueError, "already exists"): build(archive, destination, {"issue": 74})

    def test_secret_in_formal_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); archive = self.make_archive(root, "token=dummy-secret")
            with self.assertRaisesRegex(ValueError, "unsafe artifact content"):
                build(archive, root / "evidence", {"issue": 74})

    def test_signed_url_and_private_or_credential_identity_fail_closed(self):
        cases = [
            ({"download": "https://example.invalid/a?X-Amz-Signature=dummy"}, "signed URL"),
            ({"download": "https://example.invalid/a?sig=dummy"}, "signed URL"),
            ({"path": r"C:\\Users\\alice\\private"}, "unsafe artifact content"),
            ({"credential": "dummy-secret"}, "unsafe artifact content"),
        ]
        for identity, reason in cases:
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); archive = self.make_archive(root)
                with self.assertRaisesRegex(ValueError, reason): build(archive, root / "evidence", identity)

    def test_signed_url_in_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.make_archive(root, "https://example.invalid/a?X-Amz-Signature=dummy")
            with self.assertRaisesRegex(ValueError, "signed URL"): build(archive, root / "evidence", {"issue": 74})

    def test_tampered_manifest_validator_failure_is_not_a_success_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); archive = self.make_archive(root)
            manifest_path = archive / MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")); manifest["schema_version"] = "broken"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            index_path = archive / "archive.json"; index = json.loads(index_path.read_text(encoding="utf-8"))
            index["measurement_manifest"]["sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            index_path.write_text(json.dumps(index), encoding="utf-8")
            completed = self.run_builder(archive, root / "evidence", root)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("schema_version", completed.stderr)
            self.assertFalse((root / "evidence" / "files.sha256.json").exists())

    def test_control_and_safety_stage_failures_are_nonzero_without_success_bundle(self):
        for stage in ("control", "safety"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); archive = self.make_archive(root); destination = root / "evidence"
                completed = self.run_builder(archive, destination, root, stage)
                self.assertNotEqual(0, completed.returncode)
                if stage == "control": self.assertIn("negative v2 control became exact", completed.stderr)
                if stage == "safety": self.assertIn("signed URL", completed.stderr)
                self.assertFalse((destination / "files.sha256.json").exists())


if __name__ == "__main__": unittest.main()
