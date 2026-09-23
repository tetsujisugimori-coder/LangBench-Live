"""Archive a validated function-call experiment without changing schema 1.0."""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .validate_result_json import validate
else:
    from validate_result_json import validate

BENCHMARK = "function_call_numeric_sum"
LANGUAGES = {"c", "python", "javascript"}
DEFAULT_EXPERIMENT_MANIFEST = Path(__file__).resolve().parents[1] / "experiments" / f"{BENCHMARK}.json"


def load_experiment_manifest(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version", "benchmark", "languages", "config", "expected_checksum"
    }:
        raise ValueError(f"{path}: invalid experiment manifest structure")
    if manifest["schema_version"] != "1.0" or manifest["benchmark"] != BENCHMARK:
        raise ValueError(f"{path}: unsupported experiment manifest")
    if manifest["languages"] != sorted(LANGUAGES):
        raise ValueError(f"{path}: experiment languages must be c, javascript, python")
    config = manifest["config"]
    if not isinstance(config, dict) or set(config) != {
        "item_count", "warmup_iterations", "measurement_iterations", "numeric_type", "value_field", "cases"
    }:
        raise ValueError(f"{path}: invalid experiment config")
    if (type(config["item_count"]) is not int or config["item_count"] <= 0
            or type(config["warmup_iterations"]) is not int or config["warmup_iterations"] < 0
            or type(config["measurement_iterations"]) is not int or config["measurement_iterations"] <= 0
            or config["numeric_type"] != "integer" or config["value_field"] != "value"
            or config["cases"] != ["direct", "function_call"]
            or type(manifest["expected_checksum"]) is not int
            or manifest["expected_checksum"] != config["item_count"] * (config["item_count"] + 1) // 2):
        raise ValueError(f"{path}: invalid experiment conditions")
    return raw, manifest


def archive_results(
    paths: list[Path], experiment_id: str, history_root: Path,
    manifest_path: Path = DEFAULT_EXPERIMENT_MANIFEST,
) -> Path:
    if len(paths) != len(LANGUAGES):
        raise ValueError("exactly three result files are required")
    manifest_raw, manifest = load_experiment_manifest(manifest_path)

    source_files: dict[str, tuple[bytes, dict]] = {}
    configs: set[str] = set()
    for path in paths:
        raw = path.read_bytes()
        document = json.loads(raw)
        errors = validate(document, path)
        if errors:
            raise ValueError("; ".join(errors))
        if document["benchmark"] != BENCHMARK or document["experiment_id"] != experiment_id:
            raise ValueError(f"{path}: unexpected benchmark or experiment_id")
        if document["status"] != "success" or document["validation"]["passed"] is not True:
            raise ValueError(f"{path}: only successful results can be archived")
        if document["config"] != manifest["config"]:
            raise ValueError(f"{path}: config differs from experiment manifest")
        if document["validation"]["expected_checksum"] != manifest["expected_checksum"]:
            raise ValueError(f"{path}: expected_checksum differs from experiment manifest")
        configs.add(json.dumps(document["config"], sort_keys=True))
        language = document["language"]
        if language in source_files:
            raise ValueError(f"{path}: duplicate language {language}")
        source_files[language] = (raw, document)
    if set(source_files) != LANGUAGES:
        raise ValueError("results must contain c, python, and javascript")
    if len(configs) != 1:
        raise ValueError("experiment config differs between language results")

    # validate() constrains experiment_id to a timestamp and a known benchmark.
    parent = history_root / experiment_id
    parent.mkdir(parents=True, exist_ok=True)
    archive_id = uuid.uuid4().hex
    destination = parent / archive_id
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
    try:
        entries = []
        (staging / "experiment.json").write_bytes(manifest_raw)
        for language in sorted(source_files):
            raw, document = source_files[language]
            name = f"{language}.json"
            (staging / name).write_bytes(raw)
            entries.append({
                "language": language,
                "file": name,
                "run_id": document["run_id"],
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
        index = {
            "archive_id": archive_id,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "benchmark": BENCHMARK,
            "experiment_id": experiment_id,
            "experiment_manifest": {
                "file": "experiment.json",
                "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            },
            "results": entries,
        }
        (staging / "archive.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if destination.exists():
            raise FileExistsError(destination)
        os.rename(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--history-root", type=Path, default=Path("results/history"))
    parser.add_argument("--experiment-manifest", type=Path, default=DEFAULT_EXPERIMENT_MANIFEST)
    parser.add_argument("paths", nargs=3, type=Path)
    args = parser.parse_args()
    try:
        destination = archive_results(args.paths, args.experiment_id, args.history_root, args.experiment_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"archive_error={error}")
        return 1
    print(f"archive_path={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
