import csv
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT = "LangBench Live"
EXPERIMENT = "csv_line_count"
EXPERIMENT_LABEL = "CSV行数カウント"
LANGUAGE = "python"
SCHEMA_VERSION = "1.0"
RESULT_FILE = "python_result.json"
RUNNER = "vscode_terminal_powershell"
RUNNER_LABEL = "VSCode Terminal / PowerShell"
MEASURE_RUNS = 3
SAMPLES = [
    {"name": "small", "file": "data/readingTest_small.csv", "expected_data_rows": 1000},
    {"name": "medium", "file": "data/readingTest_medium.csv", "expected_data_rows": 100000},
    {"name": "large", "file": "data/readingTest_large.csv", "expected_data_rows": 1000000},
]


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def count_csv_lines(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        return sum(1 for _ in reader)


def measure_once(csv_path: Path, run_number: int) -> dict:
    start_time = time.perf_counter()
    line_count = count_csv_lines(csv_path)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return {
        "run": run_number,
        "elapsed_ms": round(elapsed_ms, 3),
        "metrics": {
            "line_count": line_count,
        },
    }


def safe_value(getter, fallback=None):
    try:
        value = getter()
    except Exception:
        return fallback
    return value if value not in ("", None) else fallback


def build_metadata() -> dict:
    argv = [Path(sys.executable).name, *sys.argv]
    return {
        "execution": {
            "runner": RUNNER,
            "runner_label": RUNNER_LABEL,
            "cwd": str(Path.cwd()),
            "argv": argv,
            "command": subprocess.list2cmdline(argv),
            "script_path": str(Path(__file__).resolve()),
        },
        "runtime": {
            "name": "python",
            "version": safe_value(platform.python_version, "unknown"),
        },
        "environment": {
            "os_name": safe_value(platform.system, "unknown"),
            "os_platform": safe_value(lambda: sys.platform, "unknown"),
            "os_version": safe_value(platform.version, "unknown"),
            "cpu_model": safe_value(platform.processor, "unknown"),
            "cpu_threads": safe_value(os.cpu_count, None),
            "memory_total_bytes": None,
        },
    }


def summarize_runs(runs: list[dict]) -> dict:
    elapsed_values = [run["elapsed_ms"] for run in runs]
    sorted_elapsed_values = sorted(elapsed_values)
    middle_index = len(sorted_elapsed_values) // 2
    return {
        "count": len(runs),
        "average_ms": round(sum(elapsed_values) / len(elapsed_values), 3),
        "median_ms": round(sorted_elapsed_values[middle_index], 3),
        "fastest_ms": round(min(elapsed_values), 3),
        "slowest_ms": round(max(elapsed_values), 3),
    }


def save_result(result: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as result_file:
        json.dump(result, result_file, ensure_ascii=False, indent=2)
        result_file.write("\n")


def validate_samples(project_root: Path) -> None:
    missing_files = []
    for sample in SAMPLES:
        csv_path = project_root / sample["file"]
        if not csv_path.exists():
            missing_files.append(sample["file"])

    if missing_files:
        joined_files = ", ".join(missing_files)
        raise FileNotFoundError(
            f"Missing CSV file(s): {joined_files}. Run `python tools/create_sample_csv.py` first."
        )


def print_sample_result(sample_result: dict) -> None:
    print(f"sample={sample_result['name']}")
    print(f"input={sample_result['input']}")
    print(f"expected_data_rows={sample_result['expected']['data_rows']}")
    for run in sample_result["runs"]:
        print(
            f"run={run['run']} "
            f"elapsed_ms={run['elapsed_ms']:.3f} "
            f"line_count={run['metrics']['line_count']}"
        )

    summary = sample_result["summary"]
    print(
        f"summary count={summary['count']} "
        f"average_ms={summary['average_ms']:.3f} "
        f"median_ms={summary['median_ms']:.3f} "
        f"fastest_ms={summary['fastest_ms']:.3f} "
        f"slowest_ms={summary['slowest_ms']:.3f}"
    )


def run_benchmark(project_root: Path) -> dict:
    samples = []
    for sample in SAMPLES:
        csv_path = project_root / sample["file"]
        runs = [
            measure_once(csv_path, run_number)
            for run_number in range(1, MEASURE_RUNS + 1)
        ]
        sample_result = {
            "name": sample["name"],
            "input": sample["file"],
            "input_file": sample["file"],
            "input_file_size_bytes": safe_value(lambda: csv_path.stat().st_size, None),
            "expected": {
                "data_rows": sample["expected_data_rows"],
            },
            "runs": runs,
        }
        summary = summarize_runs(runs)
        sample_result["summary"] = summary
        sample_result["line_count"] = runs[-1]["metrics"]["line_count"]
        sample_result["average_ms"] = summary["average_ms"]
        sample_result["median_ms"] = summary["median_ms"]
        samples.append(sample_result)
        print_sample_result(sample_result)

    metadata = build_metadata()
    return {
        "type": "langbench_result",
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "experiment": EXPERIMENT,
        "experiment_label": EXPERIMENT_LABEL,
        "language": LANGUAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "success",
        **metadata,
        "samples": samples,
    }


def main() -> int:
    try:
        project_root = get_project_root()
        validate_samples(project_root)
        result = run_benchmark(project_root)
        save_result(result, project_root / "results" / RESULT_FILE)
    except Exception as error:
        print("status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1

    print("status=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
