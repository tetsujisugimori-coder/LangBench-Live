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
    from .measurement_provenance import validate_capture, validate_manifest_v2
else:
    from validate_result_json import validate
    from measurement_provenance import validate_capture, validate_manifest_v2

BENCHMARK = "function_call_numeric_sum"
LANGUAGES = {"c", "python", "javascript"}
DEFAULT_EXPERIMENT_MANIFEST = Path(__file__).resolve().parents[1] / "experiments" / f"{BENCHMARK}.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_measurement_manifest(documents: dict[str, dict], measurement_order: list[str], capture: dict) -> dict:
    """Build v2 only from values actually observed by each benchmark process."""
    python, javascript, c = (documents[name] for name in ("python", "javascript", "c"))
    py_engine, js_engine, c_build = python["engine"], javascript["engine"], c["build"]
    capture_errors = validate_capture(capture)
    if capture_errors: raise ValueError("; ".join(capture_errors))
    if capture["experiment_id"] != python["experiment_id"]: raise ValueError("capture experiment_id differs from results")
    manifest = {
        "schema_version": "2.0", "measurement_git_sha": capture["measurement_git_sha"],
        "benchmark": BENCHMARK, "experiment_id": python["experiment_id"],
        "runner": capture["runner"],
        "measurement_order": measurement_order,
        "languages": {
            "c": {"source": capture["sources"]["c"], "os":c["environment"]["os"], "architecture":c["environment"]["architecture"], "runtime": {"name": "native", "version": c["engine"].get("runtime_version") or "native"}, "compiler": {"name": c_build["compiler"], "version": c_build["compiler_version"]}, "options": c["optimization_analysis"]["provenance"]["current"]["options"]},
            "python": {"source": capture["sources"]["python"], "os":python["environment"]["os"], "architecture":python["environment"]["architecture"], "runtime": {"name": "Python", "version": py_engine["runtime_version"]}, "implementation": {"name": py_engine["python_implementation"], "version": py_engine["runtime_version"]}, "optimize": py_engine["python_optimize"], "options": [f"optimize={py_engine['python_optimize']}"]},
            "javascript": {"source": capture["sources"]["javascript"], "os":javascript["environment"]["os"], "architecture":javascript["environment"]["architecture"], "runtime": {"name": "Node.js", "version": js_engine["runtime_version"]}, "implementation": {"name": "V8", "version": js_engine["v8_version"]}, "exec_argv": list(js_engine["exec_argv"]), "node_options": js_engine["node_options"], "options": [*js_engine["exec_argv"], *js_engine["node_options"].split()]},
        },
    }
    errors = validate_manifest_v2(manifest)
    if errors: raise ValueError("; ".join(errors))
    return manifest


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
    manifest_path: Path = DEFAULT_EXPERIMENT_MANIFEST, provenance_path: Path | None = None,
) -> Path:
    if len(paths) != len(LANGUAGES):
        raise ValueError("exactly three result files are required")
    manifest_raw, manifest = load_experiment_manifest(manifest_path)

    source_files: dict[str, tuple[bytes, dict]] = {}
    configs: set[str] = set()
    measurement_orders: set[tuple[str, ...]] = set()
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
        execution = document.get("execution")
        order = execution.get("measurement_order") if isinstance(execution, dict) else None
        if order is None:
            order = ["direct", "function_call"]  # Legacy result files used this fixed order.
        if order not in (["direct", "function_call"], ["function_call", "direct"]):
            raise ValueError(f"{path}: invalid measurement_order")
        measurement_orders.add(tuple(order))
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
    if len(measurement_orders) != 1:
        raise ValueError("measurement_order differs between language results")
    measurement_order = list(next(iter(measurement_orders)))
    documents = {name: value[1] for name, value in source_files.items()}
    has_v2_observations = (
        isinstance(documents["python"].get("engine", {}).get("python_optimize"), int)
        and isinstance(documents["javascript"].get("engine", {}).get("v8_version"), str)
        and isinstance(documents["javascript"].get("engine", {}).get("node_options"), str)
        and isinstance(documents["c"].get("optimization_analysis"), dict)
    )
    provenance_raw = None
    if has_v2_observations and provenance_path is not None:
        capture = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance_manifest = build_measurement_manifest(documents, measurement_order, capture)
        provenance_raw = (json.dumps(provenance_manifest, ensure_ascii=False, indent=2) + "\n").encode()

    # Store the actual case order as part of the hashed experiment definition.
    # Older archives omit this field and therefore retain their known direct-first meaning.
    archived_manifest = dict(manifest)
    archived_manifest["measurement_order"] = measurement_order
    archived_manifest_raw = (json.dumps(archived_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    # validate() constrains experiment_id to a timestamp and a known benchmark.
    parent = history_root / experiment_id
    parent.mkdir(parents=True, exist_ok=True)
    archive_id = uuid.uuid4().hex
    destination = parent / archive_id
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
    try:
        entries = []
        (staging / "experiment.json").write_bytes(archived_manifest_raw)
        if provenance_raw is not None:
            (staging / "measurement-manifest-v2.json").write_bytes(provenance_raw)
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
                "sha256": hashlib.sha256(archived_manifest_raw).hexdigest(),
            },
            "results": entries,
        }
        if provenance_raw is not None:
            index["measurement_manifest"] = {"file": "measurement-manifest-v2.json", "schema_version": "2.0", "sha256": hashlib.sha256(provenance_raw).hexdigest()}
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
    parser.add_argument("--measurement-provenance", type=Path)
    parser.add_argument("paths", nargs=3, type=Path)
    args = parser.parse_args()
    try:
        destination = archive_results(args.paths, args.experiment_id, args.history_root, args.experiment_manifest, args.measurement_provenance)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"archive_error={error}")
        return 1
    print(f"archive_path={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
