"""Check the actual published Issue #73 evidence, including Git byte transport."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.build_measurement_validation_evidence import comparison_controls
from tools.measurement_provenance import validate_manifest_v2

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path("artifacts/measurement-validation-issue73")
PUBLIC = ROOT / RELATIVE
EXPECTED = {
    "archive.json", "comparison-controls.json", "execution.json", "experiment.json",
    "measurement-manifest-v2.json", "README.md", "validation.json",
}


def hash_errors(files, entries):
    return [entry["file"] for entry in entries
            if hashlib.sha256(files[entry["file"]]).hexdigest() != entry["sha256"]]


class PublishedMeasurementValidationTests(unittest.TestCase):
    def setUp(self):
        self.files = {path.name: path.read_bytes() for path in PUBLIC.iterdir()}
        self.hashes = json.loads(self.files["files.sha256.json"])
        self.entries = self.hashes["files"]

    def test_published_hashes_manifest_and_controls(self):
        self.assertEqual("sha256", self.hashes["algorithm"])
        self.assertEqual("expanded artifact files", self.hashes["scope"])
        self.assertEqual(7, len(self.entries))
        self.assertEqual(EXPECTED, {entry["file"] for entry in self.entries})
        self.assertEqual(EXPECTED | {"files.sha256.json", "summary.md"}, set(self.files))
        self.assertEqual([], hash_errors(self.files, self.entries))
        manifest = json.loads(self.files["measurement-manifest-v2.json"])
        self.assertEqual([], validate_manifest_v2(manifest))
        controls = json.loads(self.files["comparison-controls.json"])
        self.assertEqual(comparison_controls(manifest)["languages"], controls["languages"])
        archive = json.loads(self.files["archive.json"])
        validation = json.loads(self.files["validation.json"])
        for key in ("measurement_manifest", "experiment_manifest"):
            entry = archive[key]
            self.assertEqual(hashlib.sha256(self.files[entry["file"]]).hexdigest(), entry["sha256"])
        self.assertEqual(archive["archive_id"], validation["archive_id"])
        self.assertEqual(archive["measurement_manifest"]["sha256"], validation["measurement_manifest_sha256"])
        self.assertEqual(manifest["measurement_git_sha"], json.loads(self.files["execution.json"])["trusted_sha"])

    def test_newline_conversion_reproduces_five_hash_failures(self):
        converted = {name: data.replace(b"\r\n", b"\n") for name, data in self.files.items()}
        for name in EXPECTED - {"README.md"}:
            self.assertEqual(json.loads(self.files[name]), json.loads(converted[name]))
        self.assertEqual(
            {"archive.json", "comparison-controls.json", "execution.json", "README.md", "validation.json"},
            set(hash_errors(converted, self.entries)),
        )

    def test_git_add_and_checkout_preserve_bytes_with_autocrlf(self):
        names = sorted(EXPECTED | {"files.sha256.json"})
        for autocrlf in ("true", "false"):
            with self.subTest(autocrlf=autocrlf), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                def git(*args):
                    return subprocess.check_output(
                        ["git", "-C", str(root), "-c", f"core.autocrlf={autocrlf}", *args],
                        stderr=subprocess.PIPE,
                    )
                git("init", "-q")
                (root / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
                (root / RELATIVE).mkdir(parents=True)
                paths = [f"{RELATIVE.as_posix()}/{name}" for name in names]
                for name in names:
                    (root / RELATIVE / name).write_bytes(self.files[name])
                git("add", "--", ".gitattributes", *paths)
                for name, path in zip(names, paths):
                    self.assertEqual(self.files[name], git("show", f":{path}"))
                checkout = root / "checkout"
                checkout.mkdir()
                git("checkout-index", "--all", f"--prefix={checkout.as_posix()}/")
                for name in names:
                    self.assertEqual(self.files[name], (checkout / RELATIVE / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
