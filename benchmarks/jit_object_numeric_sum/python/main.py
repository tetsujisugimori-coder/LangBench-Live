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
    ms = int(now.microsecond / 1000)
    return f"{now:%Y%m%d_%H%M%S}_{ms:03d}_{LANGUAGE}_{BENCHMARK}"


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


def summarize_results(results: list[dict]) -> dict:
    elapsed_values = [item["elapsed_ms"] for item in results]
    sorted_elapsed_values = sorted(elapsed_values)
    middle_index = len(sorted_elapsed_values) // 2
    median = (
        (sorted_elapsed_values[middle_index - 1] + sorted_elapsed_values[middle_index]) / 2
        if len(sorted_elapsed_values) % 2 == 0
        else sorted_elapsed_values[middle_index]
    )

    return {
        "count": len(results),
        "average_ms": round_ms(sum(elapsed_values) / len(elapsed_values)),
        "median_ms": round_ms(median),
        "fastest_ms": round_ms(min(elapsed_values)),
        "slowest_ms": round_ms(max(elapsed_values)),
    }


def build_metadata(project_root: Path, status: str, experiment_id: str, run_id: str) -> dict:
    argv = [str(Path(sys.executable)), *sys.argv]
    return {
        "type": "langbench_result",
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "benchmark": BENCHMARK,
        "experiment": BENCHMARK,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "language": LANGUAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "status": status,
        "engine": {
            "runtime": "python",
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
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
            "version": platform.python_version(),
        },
        "build": {
            "required": False,
            "compiler": None,
            "compiler_version": None,
            "compile_command": None,
            "compile_ms": None,
        },
        "environment": {
            "os_name": platform.system() or None,
            "os_platform": sys.platform,
            "os_version": platform.version() or None,
            "cpu_model": platform.processor() or None,
            "cpu_threads": os.cpu_count(),
            "memory_total_bytes": None,
        },
        "output_file": str(project_root / "results" / RESULT_FILE),
    }


def build_error_result(project_root: Path, status: str, message: str, error_type: str, experiment_id: str, run_id: str) -> dict:
    result = build_metadata(project_root, status, experiment_id, run_id)
    result["error_message"] = message
    result["error_type"] = error_type
    return result


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

    results = []
    for iteration in range(1, ITERATIONS + 1):
        iteration_start_ns = time.perf_counter_ns()
        checksum = sum_object_values(values)
        iteration_ms = elapsed_ms(iteration_start_ns, time.perf_counter_ns())
        if checksum != EXPECTED_CHECKSUM:
            raise RuntimeError(f"checksum mismatch: {checksum}")
        results.append(
            {
                "iteration": iteration,
                "elapsed_ms": iteration_ms,
                "checksum": checksum,
            }
        )

    benchmark_total_ms = round_ms(sum(item["elapsed_ms"] for item in results))
    postprocess_start_ns = time.perf_counter_ns()
    summary = summarize_results(results)
    result = {
        **build_metadata(project_root, "success", experiment_id, run_id),
        "array_size": ARRAY_SIZE,
        "iterations": ITERATIONS,
        "warmup_iterations": WARMUP_ITERATIONS,
        "setup_ms": setup_ms,
        "warmup_ms": warmup_ms,
        "expected_checksum": EXPECTED_CHECKSUM,
        "results": results,
        "summary": summary,
        "timing": {
            "process_startup_ms": None,
            "setup_ms": setup_ms,
            "warmup_ms": warmup_ms,
            "compile_ms": None,
            "benchmark_total_ms": benchmark_total_ms,
            "postprocess_ms": None,
            "result_write_ms": None,
            "runtime_total_ms": None,
            "end_to_end_total_ms": None,
        },
    }
    postprocess_ms = elapsed_ms(postprocess_start_ns, time.perf_counter_ns())
    result["timing"]["postprocess_ms"] = postprocess_ms
    return result


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

        result_write_start_ns = time.perf_counter_ns()
        save_result(result, output_path)
        result_write_ms = elapsed_ms(result_write_start_ns, time.perf_counter_ns())
        result["timing"]["result_write_ms"] = result_write_ms
        result["timing"]["runtime_total_ms"] = round_ms(
            result["timing"]["setup_ms"]
            + result["timing"]["warmup_ms"]
            + result["timing"]["benchmark_total_ms"]
            + result["timing"]["postprocess_ms"]
            + result["timing"]["result_write_ms"]
        )

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
