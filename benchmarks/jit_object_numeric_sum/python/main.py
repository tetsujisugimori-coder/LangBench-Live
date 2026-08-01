import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT = "LangBench Live"
SCHEMA_VERSION = "1.0"
LANGUAGE = "python"
BENCHMARK = "jit_object_numeric_sum"
ARRAY_SIZE = 1_000_000
ITERATIONS = 50
WARMUP_ITERATIONS = 5
EXPECTED_CHECKSUM = 500_000_500_000
RESULT_FILE = "jit_object_numeric_sum_python_result.json"
RUNNER = "vscode_terminal_powershell"
RUNNER_LABEL = "VSCode Terminal / PowerShell"


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def round_ms(value: float) -> float:
    return round(value, 3)


def elapsed_ms(start_ns: int, end_ns: int) -> float:
    return round_ms((end_ns - start_ns) / 1_000_000)


def parse_arg(name: str) -> str | None:
    for arg in sys.argv[1:]:
        if arg.startswith(f"{name}="):
            return arg.split("=", 1)[1]
    return None


def generate_experiment_id() -> str:
    now = datetime.now().astimezone()
    return f"{now:%Y%m%d_%H%M%S}_{BENCHMARK}"


def generate_run_id() -> str:
    now = datetime.now().astimezone()
    return f"{now:%Y%m%d_%H%M%S}_{LANGUAGE}_{BENCHMARK}"


def get_experiment_id() -> str:
    return (
        parse_arg("--experiment-id")
        or os.getenv("LANGBENCH_EXPERIMENT_ID")
        or generate_experiment_id()
    )


def get_run_id() -> str:
    return (
        parse_arg("--run-id")
        or os.getenv("LANGBENCH_RUN_ID")
        or generate_run_id()
    )


def create_object_list(array_size: int) -> list[dict[str, int]]:
    return [{"value": index + 1} for index in range(array_size)]


def sum_object_values(values: list[dict[str, int]]) -> int:
    total = 0
    for item in values:
        total += item["value"]
    return total


def summarize_samples(samples_ms: list[float]) -> dict:
    sorted_elapsed_values = sorted(samples_ms)
    middle_index = len(sorted_elapsed_values) // 2
    median = (
        (sorted_elapsed_values[middle_index - 1] + sorted_elapsed_values[middle_index]) / 2
        if len(sorted_elapsed_values) % 2 == 0
        else sorted_elapsed_values[middle_index]
    )

    return {
        "samples_ms": samples_ms,
        "min_ms": round_ms(min(samples_ms)),
        "max_ms": round_ms(max(samples_ms)),
        "mean_ms": round_ms(sum(samples_ms) / len(samples_ms)),
        "median_ms": round_ms(median),
    }


def build_metadata(project_root: Path, status: str, experiment_id: str, run_id: str) -> dict:
    argv = [str(Path(sys.executable)), *sys.argv]
    return {
        "type": "langbench_result",
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "benchmark": BENCHMARK,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "language": LANGUAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "status": status,
        "engine": {
            "runtime": "python",
            "runtime_version": platform.python_version(),
            "compiler": None,
            "compiler_version": None,
            "python_implementation": platform.python_implementation(),
        },
        "execution": {
            "runner": RUNNER,
            "runner_label": RUNNER_LABEL,
            "cwd": str(Path.cwd()),
            "argv": argv,
        },
        "environment": {
            "os": platform.system() or None,
            "os_version": platform.version() or None,
            "architecture": platform.machine() or None,
            "cpu": platform.processor() or None,
            "logical_processors": os.cpu_count(),
            "memory_bytes": None,
        },
    }


def build_error_result(project_root: Path, status: str, message: str, error_type: str, experiment_id: str, run_id: str) -> dict:
    return {
        **build_metadata(project_root, status, experiment_id, run_id),
        "config": build_config(),
        "timing": empty_timing(),
        "results": empty_results(),
        "validation": {
            "checksum": None,
            "expected_checksum": EXPECTED_CHECKSUM,
            "tolerance": 0,
            "passed": False,
        },
        "error": {"type": error_type, "message": message},
    }


def build_config() -> dict:
    return {
        "item_count": ARRAY_SIZE,
        "warmup_iterations": WARMUP_ITERATIONS,
        "measurement_iterations": ITERATIONS,
        "numeric_type": "integer",
        "value_field": "value",
    }


def empty_timing() -> dict:
    return {
        "process_startup_ms": None,
        "setup_ms": None,
        "warmup_ms": None,
        "measurement_ms": None,
        "benchmark_total_ms": None,
    }


def empty_results() -> dict:
    return {
        "samples_ms": [],
        "min_ms": None,
        "max_ms": None,
        "mean_ms": None,
        "median_ms": None,
    }


def run_benchmark(project_root: Path, experiment_id: str, run_id: str) -> dict:
    setup_start_ns = time.perf_counter_ns()
    values = create_object_list(ARRAY_SIZE)
    setup_ms = elapsed_ms(setup_start_ns, time.perf_counter_ns())

    warmup_start_ns = time.perf_counter_ns()
    for _ in range(WARMUP_ITERATIONS):
        checksum = sum_object_values(values)
        if checksum != EXPECTED_CHECKSUM:
            raise RuntimeError(f"warmup checksum mismatch: {checksum}")
    warmup_ms = elapsed_ms(warmup_start_ns, time.perf_counter_ns())

    samples_ms = []
    checksum = None
    for _ in range(ITERATIONS):
        iteration_start_ns = time.perf_counter_ns()
        checksum = sum_object_values(values)
        iteration_ms = elapsed_ms(iteration_start_ns, time.perf_counter_ns())
        if checksum != EXPECTED_CHECKSUM:
            raise RuntimeError(f"checksum mismatch: {checksum}")
        samples_ms.append(iteration_ms)

    measurement_ms = round_ms(sum(samples_ms))
    benchmark_total_ms = round_ms(setup_ms + warmup_ms + measurement_ms)
    return {
        **build_metadata(project_root, "success", experiment_id, run_id),
        "config": build_config(),
        "timing": {
            "process_startup_ms": None,
            "setup_ms": setup_ms,
            "warmup_ms": warmup_ms,
            "measurement_ms": measurement_ms,
            "benchmark_total_ms": benchmark_total_ms,
        },
        "results": summarize_samples(samples_ms),
        "validation": {
            "checksum": checksum,
            "expected_checksum": EXPECTED_CHECKSUM,
            "tolerance": 0,
            "passed": checksum == EXPECTED_CHECKSUM,
        },
        "error": None,
    }


def save_result(result: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")


def main() -> int:
    project_root = get_project_root()
    experiment_id = get_experiment_id()
    run_id = get_run_id()

    try:
        result = run_benchmark(project_root, experiment_id, run_id)
        output_path = project_root / "results" / RESULT_FILE

        save_result(result, output_path)
        print(f"status={result['status']}")
        return 0
    except Exception as error:
        error_result = build_error_result(
            project_root,
            "error",
            str(error),
            type(error).__name__,
            experiment_id,
            run_id,
        )
        try:
            save_result(error_result, project_root / "results" / RESULT_FILE)
        except Exception:
            pass
        print("status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
