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


def archive_results(paths: list[Path], experiment_id: str, history_root: Path) -> Path:
    if len(paths) != len(LANGUAGES):
        raise ValueError("exactly three result files are required")

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
    parser.add_argument("paths", nargs=3, type=Path)
    args = parser.parse_args()
    try:
        destination = archive_results(args.paths, args.experiment_id, args.history_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"archive_error={error}")
        return 1
    print(f"archive_path={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
