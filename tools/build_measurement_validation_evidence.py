"""Build a minimal, safe, independently re-checkable validation bundle."""

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

if __package__:
    from .check_function_call_artifact_safety import scan
    from .compare_archives import ArchiveError, compare_archives, load_archive
    from .measurement_provenance import compare_conditions, validate_manifest_v2
else:
    from check_function_call_artifact_safety import scan
    from compare_archives import ArchiveError, compare_archives, load_archive
    from measurement_provenance import compare_conditions, validate_manifest_v2

MANIFEST = "measurement-manifest-v2.json"
SIGNED_URL = re.compile(r"(?i)https?://[^\s\"']*[?&](?:x-amz-signature|x-goog-signature|signature|sig|token|access_token)=[^\s&\"']+")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def signed_url_issues(root: Path) -> list[str]:
    errors = []
    for path in sorted(root.rglob("*")):
        if not path.is_file(): continue
        content = path.read_text(encoding="utf-8")
        if SIGNED_URL.search(content): errors.append(f"{path.relative_to(root).as_posix()}: signed URL")
        try: value = json.loads(content)
        except (ValueError, TypeError): continue
        def credential_field(item: object) -> bool:
            if isinstance(item, dict):
                return any(key.casefold() in {"credential", "api_key", "apikey"} or credential_field(child)
                           for key, child in item.items())
            return isinstance(item, list) and any(credential_field(child) for child in item)
        if credential_field(value): errors.append(f"{path.relative_to(root).as_posix()}: credential field")
    return errors


def analysis_from_manifest(manifest: dict, language: str) -> dict:
    """Create a synthetic comparator control, never an observed analysis claim."""
    measured = manifest["languages"][language]
    analysis = {
        "source_sha256": measured["source"]["sha256"], "os": measured["os"],
        "architecture": measured["architecture"], "runtime": copy.deepcopy(measured["runtime"]),
        "options": copy.deepcopy(measured["options"]),
        "order_coverage": {"basis": "trace_observed" if language == "javascript" else "static_analysis",
                           "confirmed": ["direct_first", "function_call_first"], "unconfirmed": []},
    }
    if language == "c": analysis["implementation"] = copy.deepcopy(measured["compiler"])
    if language == "python":
        analysis.update(implementation=copy.deepcopy(measured["implementation"]), optimize=measured["optimize"])
    if language == "javascript":
        analysis.update(implementation=copy.deepcopy(measured["implementation"]),
                        exec_argv=copy.deepcopy(measured["exec_argv"]), node_options=measured["node_options"])
    return analysis


def comparison_controls(manifest: dict) -> dict:
    controls = {"purpose": "synthetic comparator controls only; not observed order coverage, optimization evidence, or performance evidence",
                "languages": {}}
    for language in ("c", "python", "javascript"):
        base = analysis_from_manifest(manifest, language)
        variants = {"match": base, "missing": copy.deepcopy(base),
                    "mismatch": copy.deepcopy(base), "unknown": copy.deepcopy(base)}
        variants["missing"].pop("runtime")
        variants["mismatch"]["architecture"] += "-mismatch-control"
        variants["unknown"]["runtime"] = {"name": "unknown", "version": "unknown"}
        results = {name: compare_conditions(manifest, value, language) for name, value in variants.items()}
        if not results["match"]["exact_applicability"]:
            raise ValueError(f"{language} matching v2 control was not exact")
        if any(results[name]["exact_applicability"] for name in ("missing", "mismatch", "unknown")):
            raise ValueError(f"{language} negative v2 control became exact")
        controls["languages"][language] = results
    return controls


def build(archive: Path, destination: Path, identity: dict) -> None:
    if destination.exists(): raise ValueError("evidence destination already exists")
    destination.mkdir(parents=True)
    original = load_archive(archive)  # archive hashes, results and manifest v2 are validated here.
    manifest = original.get("measurement_manifest")
    errors = validate_manifest_v2(manifest)
    if errors: raise ValueError("manifest v2 validation failed: " + "; ".join(errors))
    fixture_stage = os.environ.get("LANGBENCH_HOSTED_FAILURE_STAGE")
    if fixture_stage and os.environ.get("LANGBENCH_HOSTED_FIXTURE") != "1":
        raise ValueError("hosted failure fixture is disabled")
    comparison_manifest = copy.deepcopy(manifest)
    if fixture_stage == "control":
        # A schema-valid unknown runtime makes the real unknown negative equal
        # the measurement, so comparison_controls must reject exact promotion.
        comparison_manifest["languages"]["javascript"]["runtime"] = {"name": "unknown", "version": "unknown"}
    controls = comparison_controls(comparison_manifest)
    controls["archive_identity_control"] = compare_archives(original, copy.deepcopy(original))
    controls["archive_identity_note"] = "legacy archive comparison is recorded separately; caution/missing stays visible and is not upgraded"

    # Copy formal archive material byte-for-byte so archive index hashes retain
    # their original meaning. Results/raw samples remain excluded; archive.json
    # records their hashes for later artifact-to-archive traceability.
    for name in (MANIFEST, "archive.json", "experiment.json"):
        shutil.copy2(archive / name, destination / name)
    write_json(destination / "comparison-controls.json", controls)
    write_json(destination / "validation.json", {
        "status": "valid", "validators": ["archive_reader", "measurement_manifest_v2"],
        "archive_id": original["index"]["archive_id"], "measurement_manifest_sha256": digest(archive / MANIFEST),
    })
    write_json(destination / "execution.json", identity)
    if fixture_stage == "safety":
        write_json(destination / "hosted-safety-failure.json", {"download": "https://example.invalid/a?sig=fixed-fixture"})
    (destination / "README.md").write_text(
        "# Windows measurement provenance validation\n\n"
        "Count=1 validates provenance, archive, manifest v2, and fail-closed comparator behavior. "
        "Controls are synthetic comparator inputs and do not establish observed order coverage, optimization, or performance. "
        "archive.json preserves hashes for excluded raw result files; the bundle itself can re-run manifest validation and controls. "
        "The artifact ZIP digest is separate from the SHA-256 values of expanded files.\n", encoding="utf-8")
    unsafe = scan(destination) + signed_url_issues(destination)
    if unsafe: raise ValueError("unsafe artifact content: " + "; ".join(unsafe))
    files = [{"file": path.name, "sha256": digest(path)} for path in sorted(destination.iterdir())
             if path.name != "files.sha256.json"]
    write_json(destination / "files.sha256.json", {"algorithm": "sha256", "scope": "expanded artifact files", "files": files})
    unsafe = scan(destination) + signed_url_issues(destination)
    if unsafe: raise ValueError("unsafe hashed artifact content: " + "; ".join(unsafe))


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("archive", type=Path); parser.add_argument("destination", type=Path)
    parser.add_argument("--identity", type=Path, required=True); args = parser.parse_args()
    try: build(args.archive, args.destination, json.loads(args.identity.read_text(encoding="utf-8")))
    except (ValueError, ArchiveError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__": raise SystemExit(main())
