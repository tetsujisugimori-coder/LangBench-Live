"""Capture code identity before a function-call measurement starts."""
import argparse, json, subprocess
from pathlib import Path
from measurement_provenance import LANGUAGES, canonical_sha256, validate_capture

ROOT = Path(__file__).resolve().parents[1]

def capture(experiment_id: str) -> dict:
    suffix = {"c":"main.c", "python":"main.py", "javascript":"main.js"}
    item = lambda path: {"path": path.relative_to(ROOT).as_posix(), "sha256": canonical_sha256(path)}
    runner = ROOT / "benchmarks/function_call_numeric_sum/run_all.ps1"
    result = {"schema_version":"1.0", "experiment_id":experiment_id, "measurement_git_sha":subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip().lower(), "runner":item(runner), "sources":{language:item(ROOT / "benchmarks/function_call_numeric_sum" / language / suffix[language]) for language in LANGUAGES}}
    errors=validate_capture(result)
    if errors: raise ValueError("; ".join(errors))
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--output",required=True,type=Path); parser.add_argument("--experiment-id",required=True); args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(capture(args.experiment_id),indent=2)+"\n",encoding="utf-8")
if __name__ == "__main__": main()
