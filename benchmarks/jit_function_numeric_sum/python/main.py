import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT = "LangBench Live"
SCHEMA_VERSION = "1.0"
LANGUAGE = "python"
BENCHMARK = "jit_function_numeric_sum"
ARRAY_SIZE = 1000000
ITERATIONS = 50
RESULT_FILE = "jit_function_python_result.json"
RUNNER = "vscode_terminal_powershell"
RUNNER_LABEL = "VSCode Terminal / PowerShell"
EXPECTED_CHECKSUM = 1000000000000


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def round_ms(value: float) -> float:
    return round(value, 3)


def elapsed_ms(start_ns: int, end_ns: int) -> float:
    return round_ms((end_ns - start_ns) / 1_000_000)


def create_number_array(array_size: int) -> list[int]:
    values = [0] * array_size

    for index in range(array_size):
        values[index] = index

    return values


def transform_value(value: int) -> int:
    return value * 2 + 1


def sum_transformed_array(values: list[int]) -> int:
    total = 0

    for value in values:
        total += transform_value(value)

    return total


def safe_value(getter, fallback=None):
    try:
        value = getter()
    except Exception:
        return fallback
    return value if value not in ("", None) else fallback


def summarize_results(results: list[dict]) -> dict:
    elapsed_values = [result["elapsed_ms"] for result in results]
    sorted_elapsed_values = sorted(elapsed_values)
    middle_index = len(sorted_elapsed_values) // 2
    total_ms = sum(elapsed_values)
    summary = {
        "count": len(results),
        "average_ms": round_ms(total_ms / len(results)),
        "median_ms": round_ms(sorted_elapsed_values[middle_index]),
        "fastest_ms": round_ms(min(elapsed_values)),
        "slowest_ms": round_ms(max(elapsed_values)),
    }

    if results:
        first_iteration_ms = elapsed_values[0]
        summary["first_iteration_ms"] = round_ms(first_iteration_ms)
        if len(results) > 1:
            summary["average_ms_excluding_first"] = round_ms(
                sum(elapsed_values[1:]) / (len(results) - 1)
            )

    return summary


def build_metadata(project_root: Path, status: str) -> dict:
    argv = [str(Path(sys.executable)), *sys.argv]
    return {
        "type": "langbench_result",
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "benchmark": BENCHMARK,
        "experiment": BENCHMARK,
        "language": LANGUAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "engine": {
            "runtime": "python",
            "python_version": safe_value(platform.python_version, "unknown"),
            "python_implementation": safe_value(platform.python_implementation, "unknown"),
            "executable": str(Path(sys.executable)),
        },
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
        "output_file": str(project_root / "results" / RESULT_FILE),
    }


def save_result(result: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as result_file:
        json.dump(result, result_file, ensure_ascii=False, indent=2)
        result_file.write("\n")


def get_status(results: list[dict]) -> str:
    return (
        "success"
        if all(result["checksum"] == EXPECTED_CHECKSUM for result in results)
        else "failed"
    )


def run_benchmark(project_root: Path) -> dict:
    setup_start_ns = time.perf_counter_ns()
    values = create_number_array(ARRAY_SIZE)
    setup_ms = elapsed_ms(setup_start_ns, time.perf_counter_ns())
    results = []

    for iteration in range(1, ITERATIONS + 1):
        start_ns = time.perf_counter_ns()
        checksum = sum_transformed_array(values)
        iteration_elapsed_ms = elapsed_ms(start_ns, time.perf_counter_ns())

        results.append(
            {
                "iteration": iteration,
                "elapsed_ms": iteration_elapsed_ms,
                "checksum": checksum,
            }
        )

    status = get_status(results)

    return {
        **build_metadata(project_root, status),
        "array_size": ARRAY_SIZE,
        "iterations": ITERATIONS,
        "setup_ms": setup_ms,
        "expected_checksum": EXPECTED_CHECKSUM,
        "results": results,
        "summary": summarize_results(results),
    }


def main() -> int:
    try:
        project_root = get_project_root()
        result = run_benchmark(project_root)
        save_result(result, project_root / "results" / RESULT_FILE)
        print(f"status={result['status']}")
        return 0 if result["status"] == "success" else 1
    except Exception as error:
        print("status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
