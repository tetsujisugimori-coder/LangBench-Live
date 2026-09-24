"""Validate private C order runs and emit path-free, reproducible public data."""

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .validate_result_json import median_from_samples, validate
else:
    from validate_result_json import median_from_samples, validate

CASES = ("direct", "function_call")
ORDERS = {"A": list(CASES), "B": list(reversed(CASES))}
OPTIONS = ["-O2", "-std=c11", "-Wall", "-Wextra"]


def statistics(samples):
    assert len(samples) == 50
    return {
        "median_ms": median_from_samples(samples),
        "first_25_median_ms": median_from_samples(samples[:25]),
        "last_25_median_ms": median_from_samples(samples[25:]),
        "at_least_0_2_ms": sum(value >= 0.2 for value in samples),
    }


def build_public(record, folder):
    expected_plan = [order for pair in range(10) for order in (("A", "B") if pair % 2 == 0 else ("B", "A"))]
    if [run["order"] for run in record["runs"]] != expected_plan[:len(record["runs"])]:
        raise ValueError("run order differs from the fixed AB/BA plan")
    public = {"schema_version": "1.0", "benchmark": "function_call_numeric_sum",
              "design": "10 pairs: 5 AB and 5 BA; one A and one B in each pair",
              "plan": expected_plan, "git_head": record["git_head"],
              "c_source_sha256": record["c_source_sha256"], "runs": []}
    for index, run in enumerate(record["runs"], 1):
        entry = {"number": index, "pair": (index + 1) // 2, "order": run["order"],
                 "measurement_order": ORDERS[run["order"]],
                 "started_at": run["started_at"], "ended_at": run["ended_at"],
                 "status": run["status"]}
        if run["status"] == "success":
            raw_path = folder / f"run-{index:02d}.json"
            raw = raw_path.read_bytes()
            document = json.loads(raw)
            errors = validate(document, raw_path, allow_diagnostic_order=True)
            if errors:
                raise ValueError("; ".join(errors))
            if (document["execution"].get("measurement_order") != ORDERS[run["order"]]
                    or document["optimization_analysis"]["provenance"]["current"]["source_sha256"] != record["c_source_sha256"]
                    or document["optimization_analysis"]["provenance"]["current"]["options"] != OPTIONS
                    or document["config"] != {"item_count": 1000000, "warmup_iterations": 5,
                                             "measurement_iterations": 50, "numeric_type": "integer",
                                             "value_field": "value", "cases": list(CASES)}
                    or document["validation"]["expected_checksum"] != 500000500000):
                raise ValueError(f"run {index}: diagnostic conditions differ")
            entry["source_result"] = {"file": raw_path.name, "sha256": hashlib.sha256(raw).hexdigest()}
            entry["compiler"] = document["build"]["compiler"]
            entry["compiler_version"] = document["build"]["compiler_version"]
            entry["compiler_options"] = OPTIONS
            entry["checksums"] = {case: document["validation"][f"{case}_checksum"] for case in CASES}
            entry["cases"] = {case: {"samples_ms": document["results"][case]["samples_ms"],
                                     **statistics(document["results"][case]["samples_ms"])} for case in CASES}
            entry["optimization_analysis_status"] = document["optimization_analysis"]["provenance"]["status"]
        else:
            entry["failure_reason"] = run["reason_code"]
        public["runs"].append(entry)
    return public


def markdown(public):
    def display(value):
        return f"{value:.4f}".rstrip("0").rstrip(".")

    lines = ["# C measurement order diagnostic", "",
             "A = direct → function_call; B = function_call → direct. Each row is one run; 50 samples are repeated measurements within that run.",
             "0.2 ms is a descriptive cutoff, not a decision threshold.", ""]
    for order in ("A", "B"):
        lines += [f"## {order}", "", "| Run | Pair | Case | Median ms | First 25 ms | Last 25 ms | ≥0.2 ms |", "|---:|---:|---|---:|---:|---:|---:|"]
        for run in public["runs"]:
            if run["order"] != order:
                continue
            if run["status"] != "success":
                lines.append(f"| {run['number']} | {run['pair']} | failed | — | — | — | — |")
                continue
            for case in CASES:
                item = run["cases"][case]
                if statistics(item["samples_ms"]) != {key: item[key] for key in ("median_ms", "first_25_median_ms", "last_25_median_ms", "at_least_0_2_ms")}:
                    raise ValueError(f"run {run['number']}: published statistics differ from samples")
                lines.append(f"| {run['number']} | {run['pair']} | {case} | {display(item['median_ms'])} | {display(item['first_25_median_ms'])} | {display(item['last_25_median_ms'])} | {item['at_least_0_2_ms']}/50 |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--validate-result", type=Path)
    parser.add_argument("--public-output", type=Path)
    parser.add_argument("--table-output", type=Path)
    args = parser.parse_args()
    if args.validate_result:
        document = json.loads(args.validate_result.read_text(encoding="utf-8"))
        errors = validate(document, args.validate_result, allow_diagnostic_order=True)
        if errors:
            parser.error("; ".join(errors))
        return
    if args.directory is None:
        parser.error("directory is required")
    record = json.loads((args.directory / "runs.json").read_text(encoding="utf-8-sig"))
    public = build_public(record, args.directory)
    output = json.dumps(public, ensure_ascii=False, indent=2) + "\n"
    if args.public_output:
        args.public_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if args.table_output:
        args.table_output.write_text(markdown(public), encoding="utf-8")


if __name__ == "__main__":
    main()
