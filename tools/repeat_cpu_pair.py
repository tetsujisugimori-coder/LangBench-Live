"""Run and save independent, identically configured CPU pair measurements."""

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

try:
    from .compare_cpu_pair_runs import compare
except ImportError:
    from compare_cpu_pair_runs import compare


ROOT = Path(__file__).resolve().parents[1]


def save_new(path, document):
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def repeat(output, repetitions, cycles, candidate_type):
    if repetitions < 2 or cycles < 1:
        raise ValueError("--repetitions must be at least 2 and --cycles at least 1")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    repeat_id = f"repeat-{datetime.now():%Y%m%d_%H%M%S}-{uuid.uuid4().hex[:8]}"
    manifest = {"schema_version": "1.0", "repeat_experiment_id": repeat_id,
                "started_at": datetime.now().astimezone().isoformat(),
                "candidate_type": candidate_type, "cycles_per_run": cycles,
                "planned_independent_runs": repetitions, "runs": []}
    save_new(output / "manifest.json", manifest)
    paths = []
    for number in range(1, repetitions + 1):
        directory = output / f"run-{number:03d}"
        row = {"number": number, "directory": directory.name, "status": "running"}
        manifest["runs"].append(row)
        save_new(output / "manifest.json", manifest)
        command = [sys.executable, "-B", str(ROOT / "tools/diagnose_c_affinity.py"),
                   "--candidate-type", candidate_type, "--runs", str(cycles),
                   "--repeat-experiment-id", repeat_id, "--output", str(directory)]
        try:
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            row["exit_code"] = process.returncode
            (output / f"run-{number:03d}.log").write_text(
                process.stdout + process.stderr, encoding="utf-8")
            if process.returncode:
                row.update(status="failed", error=f"child process exited with code {process.returncode}")
                save_new(output / "manifest.json", manifest)
                return 1

            document = json.loads((directory / "runs.json").read_text(encoding="utf-8"))
            row.update(status="complete", experiment_id=document["experiment_id"],
                       started_at=document["started_at"], ended_at=document["ended_at"])
            paths.append(directory)
            save_new(output / "manifest.json", manifest)
            if len(paths) >= 2:
                # Validate before allowing a third run under different conditions.
                comparison = compare(paths, require_same_repeat_id=True)
                save_new(output / "comparison.json", comparison)
            print(f"independent run {number}/{repetitions}: {row['experiment_id']}", flush=True)
        except ValueError as error:
            # A completed measurement can be incompatible with prior runs; preserve
            # that status and its raw files while recording why comparison stopped.
            if row.get("status") == "complete" and len(paths) >= 2:
                row.update(status="incompatible", comparison_error=str(error))
            else:
                row.update(status="failed", error=f"{type(error).__name__}: {error}")
            save_new(output / "manifest.json", manifest)
            raise
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}")
            save_new(output / "manifest.json", manifest)
            raise
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-type", choices=("same_core_siblings", "same_efficiency_class_different_core",
                                                     "different_efficiency_class"), required=True)
    parser.add_argument("--cycles", type=int, required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="new directory for the manifest and separate run directories")
    args = parser.parse_args(argv)
    try:
        return repeat(args.output, args.repetitions, args.cycles, args.candidate_type)
    except Exception as error:
        parser.exit(2, f"Repeat error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
