"""Validate private C order runs and emit path-free, reproducible public data."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __package__:
    from .validate_result_json import median_from_samples, validate
else:
    from validate_result_json import median_from_samples, validate

CASES = ("direct", "function_call")
ORDERS = {"A": list(CASES), "B": list(reversed(CASES))}
OPTIONS = ["-O2", "-std=c11", "-Wall", "-Wextra"]


def fixed_plan():
    plan = []
    for pair in range(1, 11):
        orders = ("A", "B") if pair % 2 else ("B", "A")
        first_monitored = pair % 4 in (0, 1) or pair == 10
        for position, order in enumerate(orders, 1):
            plan.append({"pair": pair, "position": position, "order": order,
                         "monitored": first_monitored if position == 1 else not first_monitored})
    return plan


def utc_from_qpc(tick, trace):
    anchor = trace["anchor"]
    middle = (anchor["qpc_before"] + anchor["qpc_after"]) / 2
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    value = epoch + timedelta(microseconds=anchor["filetime_100ns"] / 10)
    return (value + timedelta(seconds=(tick - middle) / trace["frequency_hz"])).isoformat().replace("+00:00", "Z")


def validate_trace(trace, document):
    if trace.get("clock") != "windows_qpc" or not isinstance(trace.get("frequency_hz"), int) or trace["frequency_hz"] <= 0:
        raise ValueError("invalid C trace clock")
    anchor = trace["anchor"]
    if not 0 <= anchor["qpc_after"] - anchor["qpc_before"] <= trace["frequency_hz"]:
        raise ValueError("invalid C clock anchor")
    order = document["execution"]["measurement_order"]
    if trace.get("measurement_order") != order:
        raise ValueError("C trace order differs from result")
    previous_case_end = None
    for case in order:
        item = trace["cases"][case]
        samples = item["samples"]
        if len(samples) != 50 or item["start_qpc"] > samples[0]["start_qpc"] or item["end_qpc"] < samples[-1]["end_qpc"]:
            raise ValueError(f"{case}: invalid trace extent or sample count")
        if previous_case_end is not None and previous_case_end > item["start_qpc"]:
            raise ValueError("C cases overlap or have wrong order")
        previous_case_end = item["end_qpc"]
        previous_end = None
        for number, (sample, reported) in enumerate(zip(samples, document["results"][case]["samples_ms"]), 1):
            start, end = sample["start_qpc"], sample["end_qpc"]
            if sample["number"] != number or start >= end or (previous_end is not None and start < previous_end):
                raise ValueError(f"{case}: sample order differs")
            previous_end = end
            # The benchmark subtracts two large floating-point millisecond values
            # before rounding. Recomputing from integer QPC ticks can differ by 0.001 ms.
            if sample["sample_ms"] != reported or abs(round((end - start) * 1000 / trace["frequency_hz"], 3) - reported) > 0.00101:
                raise ValueError(f"{case}: trace duration differs from samples_ms")


def monitor_summary(trace, monitor):
    if monitor is None:
        return {"status": "missing", "observations": 0, "valid_observations": 0}
    if monitor.get("clock") != "windows_qpc" or monitor.get("frequency_hz") != trace["frequency_hz"]:
        raise ValueError("monitor and C clocks cannot be compared")
    interval = monitor["requested_interval_ms"]
    if not isinstance(interval, int) or interval < 1:
        raise ValueError("invalid monitor interval")
    observations = monitor["observations"]
    for observation in observations:
        if not (observation["start_qpc"] <= observation["probe_start_qpc"] <= observation["end_qpc"]
                and observation["probe_duration_qpc"] == observation["end_qpc"] - observation["probe_start_qpc"]):
            raise ValueError("invalid monitor observation interval")
        busy = observation["cpu_busy_percent"]
        if busy is not None and not 0 <= busy <= 100:
            raise ValueError("invalid CPU busy percent")
    valid = [item for item in observations if item["cpu_busy_percent"] is not None]
    duration_ms = [item["probe_duration_qpc"] * 1000 / trace["frequency_hz"] for item in observations]
    actual_intervals_ms = [(right["probe_start_qpc"] - left["probe_start_qpc"]) * 1000 / trace["frequency_hz"]
                           for left, right in zip(observations, observations[1:])]
    return {"status": "recorded", "requested_interval_ms": interval,
            "observations": len(observations), "valid_observations": len(valid),
            "failed_observations": len(observations) - len(valid),
            "actual_interval_ms_median": median_from_samples(actual_intervals_ms) if actual_intervals_ms else None,
            "actual_interval_ms_max": max(actual_intervals_ms) if actual_intervals_ms else None,
            "probe_duration_ms_median": median_from_samples(duration_ms) if duration_ms else None,
            "probe_duration_ms_max": max(duration_ms) if duration_ms else None,
            "observations_data": observations}


def coverage(start, end, monitor, frequency):
    if monitor["status"] != "recorded":
        return {"overlapping_observations": 0, "valid_cpu_observations": 0,
                "nearby_observations": 0, "coverage": "not_monitored" if monitor["status"] == "not_planned" else "missing"}
    margin = monitor["requested_interval_ms"] * frequency / 1000
    overlapping = [item for item in monitor["observations_data"] if item["start_qpc"] <= end and item["end_qpc"] >= start]
    nearby = [item for item in monitor["observations_data"] if item["start_qpc"] <= end + margin and item["end_qpc"] >= start - margin]
    valid = [item for item in overlapping if item["cpu_busy_percent"] is not None]
    return {"overlapping_observations": len(overlapping), "valid_cpu_observations": len(valid),
            "nearby_observations": len(nearby), "coverage": "observed" if valid else "missing",
            "overlapping_cpu_busy_percent": [item["cpu_busy_percent"] for item in valid]}


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
    current = record.get("schema_version") == "2.0"
    if current and ([{key: run[key] for key in ("pair", "position", "order", "monitored")} for run in record["runs"]]
                    != fixed_plan()[:len(record["runs"]) ] or record["plan"] != fixed_plan()):
        raise ValueError("monitoring conditions differ from the fixed plan")
    public = {"schema_version": "1.0", "benchmark": "function_call_numeric_sum",
              "design": "10 pairs: 5 AB and 5 BA; one A and one B in each pair",
              "plan": expected_plan, "git_head": record["git_head"],
              "c_source_sha256": record["c_source_sha256"], "runs": []}
    if current:
        public["schema_version"] = "2.0"
        public["design"] = "10 pairs; A/B and monitoring on/off balanced by order and position"
        public["plan"] = fixed_plan()
    for index, run in enumerate(record["runs"], 1):
        entry = {"number": index, "pair": (index + 1) // 2, "order": run["order"],
                 "measurement_order": ORDERS[run["order"]],
                 "started_at": run["started_at"], "ended_at": run["ended_at"],
                 "status": run["status"]}
        if current:
            entry.update(position=run["position"], monitored=run["monitored"])
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
            if current:
                trace_path = folder / f"run-{index:02d}-trace.json"
                trace_raw = trace_path.read_bytes()
                trace = json.loads(trace_raw)
                validate_trace(trace, document)
                entry["source_trace"] = {"file": trace_path.name, "sha256": hashlib.sha256(trace_raw).hexdigest()}
                entry["clock"] = {"type": "windows_qpc", "frequency_hz": trace["frequency_hz"],
                                  "anchor": trace["anchor"],
                                  "utc_anchor_uncertainty_ms_at_least":
                                  (trace["anchor"]["qpc_after"] - trace["anchor"]["qpc_before"]) * 1000 / trace["frequency_hz"]}
                monitor_path = folder / f"run-{index:02d}-monitor.json"
                if run["monitored"] and monitor_path.exists():
                    monitor_raw = monitor_path.read_bytes()
                    monitor = json.loads(monitor_raw)
                    entry["source_monitor"] = {"file": monitor_path.name,
                                               "sha256": hashlib.sha256(monitor_raw).hexdigest()}
                    summary = monitor_summary(trace, monitor)
                elif run["monitored"]:
                    summary = monitor_summary(trace, None)
                else:
                    summary = {"status": "not_planned", "observations": 0, "valid_observations": 0}
                entry["monitor"] = {key: value for key, value in summary.items() if key != "observations_data"}
                if summary["status"] == "recorded":
                    entry["monitor"]["observations_data"] = summary["observations_data"]
                for case in CASES:
                    case_trace = trace["cases"][case]
                    entry["cases"][case]["start_utc"] = utc_from_qpc(case_trace["start_qpc"], trace)
                    entry["cases"][case]["end_utc"] = utc_from_qpc(case_trace["end_qpc"], trace)
                    entry["cases"][case]["coverage"] = coverage(case_trace["start_qpc"], case_trace["end_qpc"], summary, trace["frequency_hz"])
                    entry["cases"][case]["timed_samples"] = [
                        {"number": sample["number"], "start_qpc": sample["start_qpc"],
                         "end_qpc": sample["end_qpc"], "start_utc": utc_from_qpc(sample["start_qpc"], trace),
                         "end_utc": utc_from_qpc(sample["end_qpc"], trace),
                         "sample_ms": sample["sample_ms"],
                         "coverage": coverage(sample["start_qpc"], sample["end_qpc"], summary, trace["frequency_hz"])}
                        for sample in case_trace["samples"]]
        else:
            entry["failure_reason"] = run["reason_code"]
            if current:
                entry["monitor_status"] = run["monitor_status"]
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
    if public.get("schema_version") == "2.0":
        lines += ["## Monitoring and temporal coverage", "",
                  "CPU busy is sampled over intervals using GetSystemTimes. C and monitor QPC ticks share the Windows performance counter; UTC labels use the C FILETIME anchor and are approximate. Overlap uses QPC ticks only.",
                  "Changes shorter than the requested 20 ms sampling interval can be missed. Missing CPU data does not mean zero load. Observations are temporal associations, not evidence of cause.", "",
                  "| Run | Order | Position | Monitor | Status | CPU valid/all | Interval median/max ms | Probe median/max ms | Direct median ms | Direct ≥0.2 ms | Direct case valid overlaps | Slow direct samples with valid overlap |",
                  "|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for run in public["runs"]:
            if run["status"] != "success":
                lines.append(f"| {run['number']} | {run['order']} | {run['position']} | {'on' if run['monitored'] else 'off'} | failed | — | — | — | — | — | — | — |")
                continue
            monitor = run["monitor"]
            direct = run["cases"]["direct"]
            probe = (f"{display(monitor['probe_duration_ms_median'])}/{display(monitor['probe_duration_ms_max'])}"
                     if monitor["status"] == "recorded" and monitor["observations"] else "—")
            interval = (f"{display(monitor['actual_interval_ms_median'])}/{display(monitor['actual_interval_ms_max'])}"
                        if monitor["status"] == "recorded" and monitor["actual_interval_ms_median"] is not None else "—")
            slow_covered = sum(sample["sample_ms"] >= 0.2 and sample["coverage"]["valid_cpu_observations"] > 0
                               for sample in direct["timed_samples"])
            lines.append(f"| {run['number']} | {run['order']} | {run['position']} | {'on' if run['monitored'] else 'off'} | {monitor['status']} | {monitor['valid_observations']}/{monitor['observations']} | {interval} | {probe} | {display(direct['median_ms'])} | {direct['at_least_0_2_ms']}/50 | {direct['coverage']['valid_cpu_observations']} | {slow_covered}/{direct['at_least_0_2_ms']} |")
        lines += ["", "## Direct distribution by planned condition", "",
                  "| Order | Monitor | Successful runs | Median range ms | ≥0.2 ms samples / samples |",
                  "|---|---|---:|---:|---:|"]
        for order in ("A", "B"):
            for monitored in (True, False):
                selected = [run["cases"]["direct"] for run in public["runs"]
                            if run["status"] == "success" and run["order"] == order and run["monitored"] == monitored]
                range_text = f"{display(min(item['median_ms'] for item in selected))}–{display(max(item['median_ms'] for item in selected))}" if selected else "—"
                lines.append(f"| {order} | {'on' if monitored else 'off'} | {len(selected)} | {range_text} | {sum(item['at_least_0_2_ms'] for item in selected)}/{50 * len(selected)} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--validate-result", type=Path)
    parser.add_argument("--validate-trace", type=Path)
    parser.add_argument("--public-output", type=Path)
    parser.add_argument("--table-output", type=Path)
    args = parser.parse_args()
    if args.validate_result:
        document = json.loads(args.validate_result.read_text(encoding="utf-8"))
        errors = validate(document, args.validate_result, allow_diagnostic_order=True)
        if errors:
            parser.error("; ".join(errors))
        if args.validate_trace:
            validate_trace(json.loads(args.validate_trace.read_text(encoding="utf-8")), document)
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
