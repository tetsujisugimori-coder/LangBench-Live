"""Validate and publish the precommitted 40-run C order follow-up series."""

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .summarize_c_order_diagnostic import (
        CASES, OPTIONS, ORDERS, coverage, followup_plan, monitor_summary,
        statistics, utc_from_qpc, validate_trace,
    )
    from .validate_result_json import validate
else:
    from summarize_c_order_diagnostic import (
        CASES, OPTIONS, ORDERS, coverage, followup_plan, monitor_summary,
        statistics, utc_from_qpc, validate_trace,
    )
    from validate_result_json import validate


def source(folder, name):
    path = folder / name
    if not path.is_file():
        return None
    return {"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_followup_monitor(trace, monitor):
    if monitor.get("schema_version") != "1.0" or monitor.get("requested_interval_ms") != 20:
        raise ValueError("monitor format or interval differs from the fixed conditions")
    return monitor_summary(trace, monitor)


def check_conditions(document, run, record):
    if (document["execution"].get("measurement_order") != ORDERS[run["order"]]
            or document["optimization_analysis"]["provenance"]["current"]["source_sha256"] != record["c_source_sha256"]
            or document["optimization_analysis"]["provenance"]["current"]["options"] != OPTIONS
            or document["config"] != {"item_count": 1000000, "warmup_iterations": 5,
                                      "measurement_iterations": 50, "numeric_type": "integer",
                                      "value_field": "value", "cases": list(CASES)}
            or document["validation"]["expected_checksum"] != 500000500000
            or any(document["validation"][f"{case}_checksum"] != 500000500000 for case in CASES)):
        raise ValueError(f"run {run['number']}: diagnostic conditions differ")


def build_public(record, folder):
    plan = followup_plan()
    if record.get("schema_version") != "3.0" or record.get("plan") != plan:
        raise ValueError("follow-up fixed plan differs")
    saved_plan = json.loads((folder / "plan.json").read_text(encoding="utf-8-sig"))
    if saved_plan != plan:
        raise ValueError("saved plan differs")
    if len(record["runs"]) != 40:
        raise ValueError("40 planned runs are required")
    public = {"schema_version": "3.0", "benchmark": "function_call_numeric_sum",
              "design": "20 pairs; 10 AB and 10 BA; one monitored run per pair; each A/B monitoring condition occurs five times in each pair position",
              "plan": plan, "source_plan": source(folder, "plan.json"),
              "source_record": source(folder, "runs.json"), "git_head": record["git_head"],
              "c_source_sha256": record["c_source_sha256"], "runs": []}
    for index, run in enumerate(record["runs"], 1):
        if run["number"] != index or {key: run[key] for key in ("pair", "position", "order", "monitored")} != plan[index - 1]:
            raise ValueError(f"run {index}: fixed plan differs")
        for key in ("c_measurement_status", "trace_status", "monitor_launch_status",
                    "monitor_exit_status", "monitor_file_status", "monitor_validation_status"):
            if key not in run:
                raise ValueError(f"run {index}: missing state {key}")
        if not run.get("started_at") or not run.get("ended_at") or run["c_measurement_status"] not in ("success", "failed") or run["trace_status"] not in ("success", "failed"):
            raise ValueError(f"run {index}: state was not finalized")
        if run["trace_status"] == "success" and run["c_measurement_status"] != "success":
            raise ValueError(f"run {index}: trace succeeded without C result")
        if run["monitored"] and any(run[key] in ("pending", "not_planned") for key in (
                "monitor_launch_status", "monitor_exit_status", "monitor_file_status", "monitor_validation_status")):
            raise ValueError(f"run {index}: monitoring was not finalized")
        if run["status"] != ("success" if run["c_measurement_status"] == "success" and run["trace_status"] == "success" else "failed"):
            raise ValueError(f"run {index}: C/trace status differs")
        monitor_ok = all(run[key] == "success" for key in ("monitor_launch_status", "monitor_exit_status",
                                                          "monitor_file_status", "monitor_validation_status"))
        expected_monitor = "recorded" if run["monitored"] and monitor_ok else ("failed" if run["monitored"] else "not_planned")
        if run["monitor_status"] != expected_monitor:
            raise ValueError(f"run {index}: monitor status differs")
        if not run["monitored"] and any(run[key] != "not_planned" for key in (
                "monitor_launch_status", "monitor_exit_status", "monitor_file_status", "monitor_validation_status")):
            raise ValueError(f"run {index}: unplanned monitoring state")
        entry = {key: run[key] for key in ("number", "pair", "position", "order", "monitored",
                                           "started_at", "ended_at", "status", "c_measurement_status",
                                           "trace_status", "monitor_status", "monitor_launch_status",
                                           "monitor_exit_status", "monitor_file_status", "monitor_validation_status")}
        entry["measurement_order"] = ORDERS[run["order"]]
        entry["c_failure_code"] = run.get("reason_code")
        entry["monitor_failure_code"] = run.get("monitor_reason_code")
        names = {"source_result": f"run-{index:02d}.json", "source_trace": f"run-{index:02d}-trace.json",
                 "source_monitor": f"run-{index:02d}-monitor.json"}
        for key, name in names.items():
            item = source(folder, name)
            if item:
                entry[key] = item
        monitor = None
        if run["monitor_status"] == "recorded":
            monitor_path = folder / names["source_monitor"]
            if not monitor_path.is_file():
                raise ValueError(f"run {index}: successful monitor source missing")
            monitor = json.loads(monitor_path.read_text(encoding="utf-8-sig"))
            summary = validate_followup_monitor(None, monitor)
        else:
            summary = {"status": "not_planned" if not run["monitored"] else "failed",
                       "observations": 0, "valid_observations": 0}
        entry["monitor"] = summary
        if run["status"] == "success":
            result_path = folder / names["source_result"]
            trace_path = folder / names["source_trace"]
            if not result_path.is_file() or not trace_path.is_file():
                raise ValueError(f"run {index}: successful C/trace source missing")
            document = json.loads(result_path.read_text(encoding="utf-8-sig"))
            errors = validate(document, result_path, allow_diagnostic_order=True)
            if errors:
                raise ValueError("; ".join(errors))
            check_conditions(document, run, record)
            trace = json.loads(trace_path.read_text(encoding="utf-8-sig"))
            validate_trace(trace, document)
            entry["compiler"] = document["build"]["compiler"]
            entry["compiler_version"] = document["build"]["compiler_version"]
            entry["compiler_options"] = OPTIONS
            entry["checksums"] = {case: document["validation"][f"{case}_checksum"] for case in CASES}
            entry["optimization_analysis_status"] = document["optimization_analysis"]["provenance"]["status"]
            entry["clock"] = {"type": "windows_qpc", "frequency_hz": trace["frequency_hz"],
                              "anchor": trace["anchor"]}
            if monitor is not None:
                summary = validate_followup_monitor(trace, monitor)
            entry["monitor"] = summary
            for case in CASES:
                samples = document["results"][case]["samples_ms"]
                case_trace = trace["cases"][case]
                timed = []
                for sample in case_trace["samples"]:
                    timed.append({"number": sample["number"], "start_qpc": sample["start_qpc"],
                                  "end_qpc": sample["end_qpc"], "sample_ms": sample["sample_ms"],
                                  "coverage": coverage(sample["start_qpc"], sample["end_qpc"], summary,
                                                       trace["frequency_hz"])})
                entry.setdefault("cases", {})[case] = {"samples_ms": samples, **statistics(samples),
                    "start_utc": utc_from_qpc(case_trace["start_qpc"], trace),
                    "end_utc": utc_from_qpc(case_trace["end_qpc"], trace),
                    "coverage": coverage(case_trace["start_qpc"], case_trace["end_qpc"], summary,
                                         trace["frequency_hz"]), "timed_samples": timed}
        public["runs"].append(entry)
    return public


def slow_ranges(samples):
    numbers = [i for i, value in enumerate(samples, 1) if value >= 0.2]
    groups = []
    for number in numbers:
        if groups and number == groups[-1][-1] + 1:
            groups[-1].append(number)
        else:
            groups.append([number])
    return ", ".join(str(group[0]) if len(group) == 1 else f"{group[0]}–{group[-1]}" for group in groups) or "—"


def markdown(public):
    if public["schema_version"] != "3.0":
        raise ValueError("not a follow-up series")
    def fmt(value):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    lines = ["# C measurement order follow-up: 40 planned runs", "",
             "A = direct → function_call; B = function_call → direct. Each run has 50 repeated samples per case.",
             "0.2 ms is descriptive only; it is not a significance threshold. CPU averages cover roughly 20 ms and cannot identify the load or cause of an individual 0.1–0.3 ms sample.", "",
             "## Planned conditions and direct distribution", "",
             "| Order | Monitor | Planned | C success | Trace success | Monitor success | Direct run medians ms (sorted) | Slow runs | Slow samples |",
             "|---|---|---:|---:|---:|---:|---|---:|---:|"]
    for order in ("A", "B"):
        for monitored in (True, False):
            runs = [r for r in public["runs"] if r["order"] == order and r["monitored"] == monitored]
            good = [r for r in runs if r["status"] == "success"]
            medians = sorted(r["cases"]["direct"]["median_ms"] for r in good)
            slow_runs = sum(r["cases"]["direct"]["at_least_0_2_ms"] > 0 for r in good)
            slow_samples = sum(r["cases"]["direct"]["at_least_0_2_ms"] for r in good)
            for r in good:
                if statistics(r["cases"]["direct"]["samples_ms"]) != {k: r["cases"]["direct"][k] for k in statistics(r["cases"]["direct"]["samples_ms"])}:
                    raise ValueError(f"run {r['number']}: published statistics differ from samples")
            lines.append(f"| {order} | {'あり' if monitored else 'なし'} | {len(runs)} | {sum(r['c_measurement_status'] == 'success' for r in runs)} | {sum(r['trace_status'] == 'success' for r in runs)} | {sum(r['monitor_status'] == 'recorded' for r in runs)} | {', '.join(map(fmt, medians)) or '—'} | {slow_runs} | {slow_samples} |")
    lines += ["", "## Every planned run", "",
              "| Run | Pair/position | Order | Monitor | C | Trace | Monitor result | Direct median ms | ≥0.2 ms positions | Direct missing CPU samples |",
              "|---:|---|---|---|---|---|---|---:|---|---:|"]
    slow_rows = []
    for r in public["runs"]:
        label = "CPU観測なし" if not r["monitored"] else ("取得成功" if r["monitor_status"] == "recorded" else "取得失敗")
        if r["status"] == "success":
            direct = r["cases"]["direct"]
            missing = sum(s["coverage"]["coverage"] == "missing" for s in direct["timed_samples"])
            median = fmt(direct["median_ms"])
            positions = slow_ranges(direct["samples_ms"])
            for sample in direct["timed_samples"]:
                if sample["sample_ms"] < 0.2:
                    continue
                observations = []
                for number in sample["coverage"].get("overlapping_observation_numbers", []):
                    obs = r["monitor"]["observations_data"][number - 1]
                    observations.append(f"{number}: {obs['start_qpc']}–{obs['end_qpc']} ({'欠測' if obs['cpu_busy_percent'] is None else 'CPU値あり'})")
                slow_rows.append(f"| {r['number']} | {sample['number']} | {fmt(sample['sample_ms'])} | {sample['start_qpc']}–{sample['end_qpc']} | {', '.join(observations) or label} |")
        else:
            missing, median, positions = "—", "—", "—"
        lines.append(f"| {r['number']} | {r['pair']}/{r['position']} | {r['order']} | {'あり' if r['monitored'] else 'なし'} | {r['c_measurement_status']} | {r['trace_status']} | {label} | {median} | {positions} | {missing} |")
    lines += ["", "## Slow direct samples and QPC overlap", "",
              "Overlaps compare raw QPC intervals. A missing CPU value is not zero load. No overlap does not rule out a short load change.", "",
              "| Run | Sample | ms | Sample QPC interval | Overlapping monitor interval QPC |",
              "|---:|---:|---:|---|---|"] + (slow_rows or ["| — | — | — | — | No ≥0.2 ms direct samples |"])
    monitored_slow = any(r["monitored"] and r["status"] == "success" and r["cases"]["direct"]["at_least_0_2_ms"] for r in public["runs"])
    if not monitored_slow:
        lines += ["", "監視ありの遅いdirectサンプルは0件です。CPU負荷との関係は判定不能です。"]
    lines += ["", "観測区間の重なりは時間的な対応だけを示します。CPU負荷を遅延原因とは判定しません。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--print-plan", action="store_true")
    parser.add_argument("--validate-monitor", type=Path)
    parser.add_argument("--validate-trace", type=Path)
    parser.add_argument("--public-output", type=Path)
    parser.add_argument("--table-output", type=Path)
    args = parser.parse_args()
    if args.print_plan:
        print(json.dumps(followup_plan(), ensure_ascii=False, indent=2))
        return
    if args.validate_monitor:
        monitor = json.loads(args.validate_monitor.read_text(encoding="utf-8-sig"))
        trace = json.loads(args.validate_trace.read_text(encoding="utf-8-sig")) if args.validate_trace else None
        validate_followup_monitor(trace, monitor)
        return
    if not args.directory:
        parser.error("directory is required")
    record = json.loads((args.directory / "runs.json").read_text(encoding="utf-8-sig"))
    public = build_public(record, args.directory)
    output = json.dumps(public, ensure_ascii=False, indent=2) + "\n"
    if args.public_output:
        args.public_output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if args.table_output:
        args.table_output.write_text(markdown(public), encoding="utf-8")


if __name__ == "__main__":
    main()
