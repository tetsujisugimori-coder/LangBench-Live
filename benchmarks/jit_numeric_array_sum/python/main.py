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
BENCHMARK = "jit_numeric_array_sum"
ARRAY_SIZE = 1_000_000
ITERATIONS = 50
EXPECTED_CHECKSUM = 499_999_500_000
RESULT_FILE = "jit_numeric_array_sum_python_result.json"
RUNNER = "vscode_terminal_powershell"
RUNNER_LABEL = "VSCode Terminal / PowerShell"


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def round_ms(value: float) -> float:
    return round(value, 3)


def elapsed_ms(start_ns: int, end_ns: int) -> float:
    return round_ms((end_ns - start_ns) / 1_000_000)


def get_total_memory_bytes():
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys
    except (AttributeError, OSError):
        pass
    return None


def summarize_results(results: list[dict]) -> dict:
    elapsed_values = [item["elapsed_ms"] for item in results]
    sorted_values = sorted(elapsed_values)
    middle = len(sorted_values) // 2
    median = (
        (sorted_values[middle - 1] + sorted_values[middle]) / 2
        if len(sorted_values) % 2 == 0
        else sorted_values[middle]
    )
    return {
        "count": len(results),
        "average_ms": round_ms(sum(elapsed_values) / len(elapsed_values)),
        "median_ms": round_ms(median),
        "fastest_ms": round_ms(min(elapsed_values)),
        "slowest_ms": round_ms(max(elapsed_values)),
    }


def build_metadata(project_root: Path) -> dict:
    argv = [str(Path(sys.executable)), *sys.argv]
    return {
        "type": "langbench_result",
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "benchmark": BENCHMARK,
        "experiment": BENCHMARK,
        "language": LANGUAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "success",
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
        "runtime": {"name": "python", "version": platform.python_version()},
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
            "memory_total_bytes": get_total_memory_bytes(),
        },
        "output_file": str(project_root / "results" / RESULT_FILE),
    }


def run_benchmark(project_root: Path) -> dict:
    setup_start_ns = time.perf_counter_ns()
    values = list(range(ARRAY_SIZE))
    setup_ms = elapsed_ms(setup_start_ns, time.perf_counter_ns())
    results = []

    for iteration in range(1, ITERATIONS + 1):
        start_ns = time.perf_counter_ns()
        checksum = sum(values)
        iteration_ms = elapsed_ms(start_ns, time.perf_counter_ns())
        if checksum != EXPECTED_CHECKSUM:
            raise RuntimeError(f"checksum mismatch: {checksum}")
        results.append(
            {"iteration": iteration, "elapsed_ms": iteration_ms, "checksum": checksum}
        )

    return {
        **build_metadata(project_root),
        "array_size": ARRAY_SIZE,
        "iterations": ITERATIONS,
        "setup_ms": setup_ms,
        "results": results,
        "summary": summarize_results(results),
    }


def main() -> int:
    try:
        project_root = get_project_root()
        result = run_benchmark(project_root)
        output_path = project_root / "results" / RESULT_FILE
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except Exception as error:
        print("status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1

    print("status=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
