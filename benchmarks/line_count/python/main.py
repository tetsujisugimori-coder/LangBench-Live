import csv
import json
import time
from pathlib import Path


BENCHMARK_ID = "line_count"
FILE_NAME = "readingTest.csv"
LANGUAGE = "Python"


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def count_data_rows(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)
        return sum(1 for _ in reader)


def save_result(result_path: Path, result: dict) -> None:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("w", encoding="utf-8") as result_file:
        json.dump(result, result_file, ensure_ascii=False, indent=2)
        result_file.write("\n")


def print_result(result: dict) -> None:
    print(f"language={result['language']}")
    print(f"benchmark={result['benchmark_id']}")
    print(f"file={result['file']}")
    if "rows" in result:
        print(f"rows={result['rows']}")
    if "elapsed_ms" in result:
        print(f"elapsed_ms={result['elapsed_ms']:.3f}")
    print(f"status={result['status']}")
    if "message" in result:
        print(f"message={result['message']}")


def main() -> int:
    project_root = get_project_root()
    csv_path = project_root / "data" / FILE_NAME
    result_path = project_root / "results" / "result.json"

    start_time = time.perf_counter()
    try:
        rows = count_data_rows(csv_path)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        result = {
            "benchmark_id": BENCHMARK_ID,
            "file": FILE_NAME,
            "language": LANGUAGE,
            "status": "success",
            "rows": rows,
            "elapsed_ms": round(elapsed_ms, 3),
        }
        exit_code = 0
    except Exception as error:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        result = {
            "benchmark_id": BENCHMARK_ID,
            "file": FILE_NAME,
            "language": LANGUAGE,
            "status": "error",
            "elapsed_ms": round(elapsed_ms, 3),
            "message": str(error),
        }
        exit_code = 1

    save_result(result_path, result)
    print_result(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
