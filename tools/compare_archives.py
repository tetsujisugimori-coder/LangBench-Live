"""Check whether two function_call_numeric_sum archives can be compared."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .validate_result_json import validate
else:
    from validate_result_json import validate

BENCHMARK = "function_call_numeric_sum"
LANGUAGES = ("c", "javascript", "python")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
ARCHIVE_ID = re.compile(r"[0-9a-f]{32}\Z")


class ArchiveError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArchiveError("DUPLICATE_JSON_KEY", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> tuple[bytes, Any]:
    if not path.is_file() or path.is_symlink():
        raise ArchiveError("MISSING_FILE", f"missing or nonregular file: {path}")
    raw = path.read_bytes()
    try:
        return raw, json.loads(raw, object_pairs_hook=object_without_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveError("INVALID_JSON", f"invalid JSON: {path}: {error}") from error


def require_file(folder: Path, name: Any, expected: str) -> Path:
    if name != expected:
        raise ArchiveError("INVALID_FILE_REFERENCE", f"invalid file reference: {name!r}; expected {expected}")
    path = folder / expected
    if path.is_symlink():
        raise ArchiveError("INVALID_FILE_REFERENCE", f"symlink is not an archive file: {path}")
    return path


def check_hash(raw: bytes, recorded: Any, path: Path) -> None:
    if not isinstance(recorded, str) or not SHA256.fullmatch(recorded):
        raise ArchiveError("INVALID_SHA256", f"invalid recorded SHA-256: {path}")
    if hashlib.sha256(raw).hexdigest() != recorded:
        raise ArchiveError("SHA256_MISMATCH", f"SHA-256 mismatch: {path}")


def check_definition(definition: Any, path: Path) -> None:
    keys = {"schema_version", "benchmark", "languages", "config", "expected_checksum"}
    if not isinstance(definition, dict) or set(definition) != keys:
        raise ArchiveError("INVALID_DEFINITION", f"invalid experiment definition: {path}")
    config = definition["config"]
    config_keys = {"item_count", "warmup_iterations", "measurement_iterations", "numeric_type", "value_field", "cases"}
    if (not isinstance(definition["schema_version"], str) or not definition["schema_version"].strip()
            or definition["benchmark"] != BENCHMARK or definition["languages"] != list(LANGUAGES)
            or not isinstance(config, dict) or set(config) != config_keys
            or type(config["item_count"]) is not int or config["item_count"] <= 0
            or type(config["warmup_iterations"]) is not int or config["warmup_iterations"] < 0
            or type(config["measurement_iterations"]) is not int or config["measurement_iterations"] <= 0
            or config["numeric_type"] != "integer" or config["value_field"] != "value"
            or config["cases"] != ["direct", "function_call"]
            or type(definition["expected_checksum"]) is not int
            or definition["expected_checksum"] != config["item_count"] * (config["item_count"] + 1) // 2):
        raise ArchiveError("INVALID_DEFINITION", f"invalid experiment conditions: {path}")


def load_archive(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise ArchiveError("MISSING_ARCHIVE", f"missing or linked archive directory: {folder}")
    _, index = read_json(folder / "archive.json")
    if not isinstance(index, dict) or set(index) != {"archive_id", "archived_at", "benchmark", "experiment_id", "experiment_manifest", "results"}:
        raise ArchiveError("INVALID_ARCHIVE", f"invalid archive index: {folder}")
    if (not isinstance(index["archive_id"], str) or not ARCHIVE_ID.fullmatch(index["archive_id"])
            or index["archive_id"] != folder.name or index["benchmark"] != BENCHMARK
            or not isinstance(index["experiment_id"], str) or index["experiment_id"] != folder.parent.name
            or not isinstance(index["archived_at"], str) or not index["archived_at"].strip()):
        raise ArchiveError("INVALID_ARCHIVE", f"inconsistent archive metadata: {folder}")
    manifest_entry = index["experiment_manifest"]
    if not isinstance(manifest_entry, dict) or set(manifest_entry) != {"file", "sha256"}:
        raise ArchiveError("INVALID_ARCHIVE", f"invalid experiment reference: {folder}")
    definition_path = require_file(folder, manifest_entry["file"], "experiment.json")
    raw, definition = read_json(definition_path)
    check_hash(raw, manifest_entry["sha256"], definition_path)
    check_definition(definition, definition_path)
    if definition["benchmark"] != index["benchmark"]:
        raise ArchiveError("DEFINITION_MISMATCH", f"benchmark differs from archive index: {definition_path}")
    entries = index["results"]
    if not isinstance(entries, list) or len(entries) != 3:
        raise ArchiveError("INVALID_ARCHIVE", f"exactly three result references required: {folder}")
    results = {}
    files = {"experiment.json"}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"language", "file", "run_id", "sha256"}:
            raise ArchiveError("INVALID_ARCHIVE", f"invalid result reference: {folder}")
        language = entry["language"]
        if not isinstance(language, str) or language not in LANGUAGES:
            raise ArchiveError("INVALID_LANGUAGE", f"invalid language: {language!r}")
        if language in results:
            raise ArchiveError("DUPLICATE_LANGUAGE", f"duplicate language: {language!r}")
        if not isinstance(entry["file"], str):
            raise ArchiveError("INVALID_FILE_REFERENCE", f"invalid file reference: {entry['file']!r}")
        if entry["file"] in files:
            raise ArchiveError("DUPLICATE_FILE", f"duplicate file reference: {entry['file']}")
        path = require_file(folder, entry["file"], f"{language}.json")
        files.add(entry["file"])
        raw, document = read_json(path)
        check_hash(raw, entry["sha256"], path)
        try:
            errors = validate(document, path)
        except (KeyError, TypeError, ValueError) as error:
            raise ArchiveError("RESULT_VALIDATION_FAILED", f"result validation failed: {path}: {error}") from error
        if errors:
            raise ArchiveError("RESULT_VALIDATION_FAILED", "; ".join(errors))
        expected = {
            "language": (document["language"], language),
            "run_id": (document["run_id"], entry["run_id"]),
            "experiment_id": (document["experiment_id"], index["experiment_id"]),
            "benchmark": (document["benchmark"], definition["benchmark"]),
            "config": (document["config"], definition["config"]),
            "expected_checksum": (document["validation"]["expected_checksum"], definition["expected_checksum"]),
            "status": (document["status"], "success"),
            "validation.passed": (document["validation"]["passed"], True),
        }
        for field, (actual, recorded) in expected.items():
            if actual != recorded:
                raise ArchiveError("RESULT_DEFINITION_MISMATCH", f"{path}: {field} differs from archived experiment or index")
        results[language] = document
    if set(results) != set(LANGUAGES):
        raise ArchiveError("MISSING_LANGUAGE", f"missing language result: {folder}")
    return {"index": index, "definition": definition, "results": results}


def reason(code: str, field: str, message: str, language: str | None = None) -> dict:
    item = {"code": code, "field": field, "message": message}
    if language is not None:
        item["language"] = language
    return item


def present(value: Any) -> bool:
    # An empty options array records that no options were used.
    return value is not None and value != ""


def nested(document: dict, *names: str) -> Any:
    value = document
    for name in names:
        if not isinstance(value, dict):
            return None
        value = value.get(name)
    return value


def compare_archives(left: dict, right: dict) -> dict:
    hard = []
    for field in ("benchmark", "schema_version", "config", "expected_checksum"):
        if left["definition"][field] != right["definition"][field]:
            hard.append(reason("CONDITION_DIFFERENT", field, f"実験条件 {field} が異なります。"))
    if hard:
        return {"verdict": "incomparable", "reasons": hard}

    caution = []
    def check(language: str, field: str, a: Any, b: Any) -> None:
        if not present(a) or not present(b):
            caution.append(reason("INFORMATION_MISSING", field, f"{language} の {field} が片方または両方で記録されていません。", language))
        elif a != b:
            caution.append(reason("ENVIRONMENT_DIFFERENT", field, f"{language} の {field} が異なります。", language))

    for language in LANGUAGES:
        a, b = left["results"][language], right["results"][language]
        for field in ("os", "os_version", "cpu", "architecture"):
            check(language, f"environment.{field}", nested(a, "environment", field), nested(b, "environment", field))
        if language == "c":
            for field in ("compiler", "compiler_version"):
                check(language, f"build.{field}", nested(a, "build", field), nested(b, "build", field))
        else:
            for field in ("runtime", "runtime_version"):
                check(language, f"engine.{field}", nested(a, "engine", field), nested(b, "engine", field))
            field = "python_implementation" if language == "python" else "v8_version"
            check(language, f"engine.{field}", nested(a, "engine", field), nested(b, "engine", field))
        for field in ("implementation", "options", "source_sha256"):
            check(language, f"optimization_analysis.provenance.current.{field}",
                  nested(a, "optimization_analysis", "provenance", "current", field),
                  nested(b, "optimization_analysis", "provenance", "current", field))
    return {"verdict": "caution" if caution else "comparable", "reasons": caution}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    try:
        result = compare_archives(load_archive(args.left), load_archive(args.right))
    except (ArchiveError, OSError) as error:
        code = error.code if isinstance(error, ArchiveError) else "IO_ERROR"
        if args.json:
            print(json.dumps({"error": {"code": code, "message": str(error)}}))
        else:
            print(f"検証エラー [{code}]: {error}", file=sys.stderr)
        return 2
    result = {"schema_version": "1.0", "left": str(args.left), "right": str(args.right), **result}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print({"comparable": "比較可能", "caution": "注意付き", "incomparable": "比較不可"}[result["verdict"]])
        for item in result["reasons"]:
            print(f"- [{item['code']}] {item['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
