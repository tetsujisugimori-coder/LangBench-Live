import csv
import json
import sys
import time
from pathlib import Path


BENCHMARK = "csv_line_count"
LANGUAGE = "python"
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
        "line_count": line_count,
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
    print(f"sample={sample_result['sample']}")
    print(f"file={sample_result['file']}")
    print(f"expected_data_rows={sample_result['expected_data_rows']}")
    for run in sample_result["runs"]:
        print(
            f"run={run['run']} "
            f"elapsed_ms={run['elapsed_ms']:.3f} "
            f"line_count={run['line_count']}"
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
            "sample": sample["name"],
            "file": sample["file"],
            "expected_data_rows": sample["expected_data_rows"],
            "runs": runs,
            "summary": summarize_runs(runs),
        }
        samples.append(sample_result)
        print_sample_result(sample_result)

    return {
        "benchmark": BENCHMARK,
        "language": LANGUAGE,
        "samples": samples,
    }


def main() -> int:
    try:
        project_root = get_project_root()
        validate_samples(project_root)
        result = run_benchmark(project_root)
        save_result(result, project_root / "results" / "results" / "python_result.json")
    except Exception as error:
        print("status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1

    print("status=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
