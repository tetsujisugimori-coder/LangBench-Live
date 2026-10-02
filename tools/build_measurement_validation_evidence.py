"""Build comparison controls and a minimal, hashed validation evidence bundle."""

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

if __package__:
    from .compare_archives import ArchiveError, compare_archives, load_archive
else:
    from compare_archives import ArchiveError, compare_archives, load_archive


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(archive: Path, destination: Path, identity: dict):
    if destination.exists(): raise ValueError("evidence destination already exists")
    destination.mkdir(parents=True)
    original = load_archive(archive)
    controls = {"purpose": "comparator controls only; not evidence of optimization or performance",
                "observed_order_coverage": original["definition"].get("measurement_order"), "controls": {}}
    controls["controls"]["match"] = compare_archives(original, copy.deepcopy(original))
    changed = copy.deepcopy(original); changed["results"]["python"]["environment"]["architecture"] += "-mismatch-control"
    controls["controls"]["mismatch"] = compare_archives(original, changed)
    missing = copy.deepcopy(original); missing["results"]["javascript"]["engine"].pop("v8_version", None)
    controls["controls"]["missing"] = compare_archives(original, missing)
    unknown = copy.deepcopy(original); unknown["results"]["c"]["optimization_analysis"]["provenance"]["current"]["implementation"] = "unknown"
    controls["controls"]["unknown"] = compare_archives(original, unknown)
    if controls["controls"]["match"]["verdict"] != "comparable": raise ValueError("matching control was not comparable")
    if any(controls["controls"][name]["verdict"] == "comparable" for name in ("missing", "mismatch", "unknown")):
        raise ValueError("negative control was promoted to comparable applicability")
    write_json(destination / "comparison-controls.json", controls)
    manifest_source = archive / "measurement-manifest.json"
    shutil.copy2(manifest_source, destination / "measurement-manifest.json")
    write_json(destination / "validation.json", {"status": "valid", "archive": archive.name})
    write_json(destination / "execution.json", identity)
    summary = ("# Windows measurement provenance validation\n\n"
               "This Count=1 run validates provenance, manifest v2, validators, comparison controls, and packaging. "
               "It does not support new performance or optimization conclusions. Controls test comparator behavior only.\n")
    (destination / "README.md").write_text(summary, encoding="utf-8")
    files = []
    for path in sorted(destination.iterdir()):
        if path.name != "files.sha256.json": files.append({"file": path.name, "sha256": digest(path)})
    write_json(destination / "files.sha256.json", {"algorithm": "sha256", "files": files})


def main():
    p = argparse.ArgumentParser(); p.add_argument("archive", type=Path); p.add_argument("destination", type=Path)
    p.add_argument("--identity", type=Path, required=True); a = p.parse_args()
    try: build(a.archive, a.destination, json.loads(a.identity.read_text(encoding="utf-8")))
    except (ValueError, ArchiveError, OSError, json.JSONDecodeError) as e: p.error(str(e))


if __name__ == "__main__": main()
