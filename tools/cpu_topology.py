"""Read-only CPU topology diagnostics. This module never changes CPU affinity."""

import argparse
from collections import Counter
from itertools import combinations
import ctypes
import json
import os
import platform
from pathlib import Path


class TopologyUnavailableError(ValueError):
    """Raised when topology collection did not produce analyzable core data."""


def _cpu_id(value, *, default_group=None):
    if isinstance(value, int) and not isinstance(value, bool):
        if default_group is None:
            raise ValueError("logical CPU integer identifiers require a default processor group")
        group_id, processor_number = default_group, value
    elif isinstance(value, dict):
        group_id = value.get("group_id")
        processor_number = value.get("processor_number")
    else:
        raise ValueError(f"invalid logical CPU identifier: {value!r}")
    if (not isinstance(group_id, int) or isinstance(group_id, bool) or group_id < 0
            or not isinstance(processor_number, int) or isinstance(processor_number, bool)
            or processor_number < 0):
        raise ValueError(f"logical CPU identifier requires non-negative integer group_id and processor_number: {value!r}")
    return group_id, processor_number


def _cpu_label(cpu_id):
    if cpu_id["group_id"] == 0:
        return f"CPU {cpu_id['processor_number']}"
    return f"Group {cpu_id['group_id']} CPU {cpu_id['processor_number']}"


def build_logical_cpu_index(topology: dict) -> dict:
    """Index collected core records by (group_id, processor_number), without OS calls."""
    if not isinstance(topology, dict):
        raise ValueError("topology must be a dictionary")
    status = topology.get("status")
    if status != "available":
        detail = topology.get("error")
        suffix = f": {detail}" if detail else ""
        raise TopologyUnavailableError(f"CPU topology status is {status!r}{suffix}")
    cores = topology.get("cores")
    if not isinstance(cores, list):
        raise ValueError("topology cores must be a list")
    index = {}
    group_ids = set()
    for core_position, core in enumerate(cores):
        if not isinstance(core, dict):
            raise ValueError(f"core at index {core_position} must be a dictionary")
        if "core_id" not in core:
            raise ValueError(f"core at index {core_position} is missing core_id")
        core_id = core["core_id"]
        if not isinstance(core_id, int) or isinstance(core_id, bool) or core_id < 0:
            raise ValueError(f"core at index {core_position} has invalid core_id: {core_id!r}")
        processors = core.get("logical_processors")
        if not isinstance(processors, list):
            raise ValueError(f"core {core_id} logical_processors must be a list")
        for processor in processors:
            cpu_key = _cpu_id(processor)
            if cpu_key in index:
                raise ValueError(f"logical CPU group {cpu_key[0]} processor {cpu_key[1]} appears in multiple cores")
            group_ids.add(cpu_key[0])
            index[cpu_key] = {
                "group_id": cpu_key[0],
                "processor_number": cpu_key[1],
                "core_id": core_id,
                "efficiency_class": core.get("efficiency_class"),
                "logical_processors_on_core": [],
            }
    for item in index.values():
        item["logical_processors_on_core"] = [
            {"group_id": group_id, "processor_number": processor_number}
            for group_id, processor_number in index
            if group_id == item["group_id"] and index[(group_id, processor_number)]["core_id"] == item["core_id"]
        ]
        item["sibling_logical_cpus"] = [
            cpu for cpu in item["logical_processors_on_core"]
            if cpu["processor_number"] != item["processor_number"]
        ]
        item["sibling_logical_cpu_count"] = len(item["sibling_logical_cpus"])
        item["logical_thread_count"] = len(item["logical_processors_on_core"])
    groups = topology.get("processor_groups")
    if groups is not None:
        if not isinstance(groups, list):
            raise ValueError("topology processor_groups must be a list")
        for group in groups:
            if not isinstance(group, dict):
                raise ValueError("processor group records must be dictionaries")
            group_id = group.get("group_id")
            if not isinstance(group_id, int) or isinstance(group_id, bool) or group_id < 0:
                raise ValueError(f"invalid processor group identifier: {group_id!r}")
            group_ids.add(group_id)
    return {"logical_cpus": index, "processor_group_ids": sorted(group_ids)}


def analyze_topology(topology: dict, logical_cpus=None) -> dict:
    """Return topology summary, selected CPU details, and pair comparisons."""
    indexed = build_logical_cpu_index(topology)
    cpu_index = indexed["logical_cpus"]
    group_ids = set(indexed["processor_group_ids"])
    declared_group_count = topology.get("processor_group_count")
    if declared_group_count is not None and (
        not isinstance(declared_group_count, int) or isinstance(declared_group_count, bool) or declared_group_count < 0
    ):
        raise ValueError("processor_group_count must be a non-negative integer or None")
    selected = []
    for requested in logical_cpus or []:
        # Bare numbers retain compatibility with affinity diagnostics, which address group 0 CPU N.
        group_id = requested.get("group_id", 0) if isinstance(requested, dict) else 0
        if isinstance(requested, dict) and group_id not in group_ids:
            raise ValueError(f"processor group {group_id} does not exist in the collected topology")
        key = _cpu_id(requested, default_group=0)
        if key not in cpu_index:
            group_exists = key[0] in group_ids
            if not group_exists:
                raise ValueError(f"processor group {key[0]} does not exist in the collected topology")
            raise ValueError(f"logical CPU group {key[0]} processor {key[1]} does not exist in the collected topology")
        selected.append(key)

    core_threads = Counter(len(core["logical_processors"]) for core in topology["cores"])
    efficiency_cores = Counter()
    efficiency_cpus = Counter()
    for core in topology["cores"]:
        efficiency_class = core.get("efficiency_class")
        if efficiency_class is not None and (not isinstance(efficiency_class, int) or isinstance(efficiency_class, bool)):
            raise ValueError(f"core {core['core_id']} has invalid efficiency_class: {efficiency_class!r}")
        if efficiency_class is not None:
            efficiency_cores[efficiency_class] += 1
            efficiency_cpus[efficiency_class] += len(core["logical_processors"])
    affinity = topology.get("process_affinity")
    affinity_count = None
    if affinity is not None:
        if not isinstance(affinity, dict):
            raise ValueError("process_affinity must be a dictionary or None")
        affinity_count = affinity.get("allowed_logical_cpu_count")
        if affinity_count is None:
            ids = affinity.get("allowed_logical_cpu_ids")
            if ids is not None and not isinstance(ids, list):
                raise ValueError("process_affinity allowed_logical_cpu_ids must be a list")
            affinity_count = len(ids) if ids is not None else None
        elif not isinstance(affinity_count, int) or isinstance(affinity_count, bool) or affinity_count < 0:
            raise ValueError("process_affinity allowed_logical_cpu_count must be a non-negative integer")
    summary = {
        "logical_cpu_count": len(cpu_index),
        "physical_core_count": len(topology["cores"]),
        "processor_group_count": max(len(group_ids), declared_group_count or 0),
        "process_affinity_logical_cpu_count": affinity_count,
        "physical_cores_by_logical_thread_count": dict(sorted(core_threads.items())),
        "efficiency_class_physical_core_counts": dict(sorted(efficiency_cores.items())),
        "efficiency_class_logical_cpu_counts": dict(sorted(efficiency_cpus.items())),
    }
    analyses = []
    for key in selected:
        item = cpu_index[key]
        analyses.append({
            "logical_cpu": {"group_id": key[0], "processor_number": key[1]},
            "core_id": item["core_id"],
            "efficiency_class": item["efficiency_class"],
            "logical_processors_on_core": item["logical_processors_on_core"],
            "sibling_logical_cpus": item["sibling_logical_cpus"],
            "sibling_logical_cpu_count": item["sibling_logical_cpu_count"],
            "logical_thread_count": item["logical_thread_count"],
        })
    comparisons = []
    for first_key, second_key in combinations(selected, 2):
        first, second = cpu_index[first_key], cpu_index[second_key]
        comparisons.append({
            "first_logical_cpu": {"group_id": first_key[0], "processor_number": first_key[1]},
            "second_logical_cpu": {"group_id": second_key[0], "processor_number": second_key[1]},
            "same_processor_group": first_key[0] == second_key[0],
            "same_physical_core": first_key[0] == second_key[0] and first["core_id"] == second["core_id"],
            "same_efficiency_class": (
                None if first["efficiency_class"] is None or second["efficiency_class"] is None
                else first["efficiency_class"] == second["efficiency_class"]
            ),
        })
    return {"topology_summary": summary, "logical_cpu_analysis": analyses, "comparisons": comparisons}


def unavailable(error: str, status: str | None = None) -> dict:
    return {
        "status": status or ("unsupported" if os.name != "nt" else "unavailable"),
        "source": "Windows processor topology APIs",
        "error": error,
        "logical_cpu_count": os.cpu_count(),
        "physical_core_count": None,
        "processor_group_count": None,
        "processor_groups": [],
        "process_affinity": None,
        "cores": [],
    }


def _windows_topology() -> dict:
    """Collect processor core/group masks and the calling process' allowed mask."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    word = ctypes.c_size_t

    class GroupAffinity(ctypes.Structure):
        _fields_ = [("mask", word), ("group", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3)]

    class ProcessorNumber(ctypes.Structure):
        _fields_ = [("group", ctypes.c_ushort), ("number", ctypes.c_ubyte), ("reserved", ctypes.c_ubyte)]

    kernel.GetActiveProcessorGroupCount.restype = ctypes.c_ushort
    kernel.GetActiveProcessorCount.argtypes = [ctypes.c_ushort]
    kernel.GetActiveProcessorCount.restype = ctypes.c_uint32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetCurrentThread.restype = ctypes.c_void_p
    kernel.GetThreadGroupAffinity.argtypes = [ctypes.c_void_p, ctypes.POINTER(GroupAffinity)]
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(word), ctypes.POINTER(word)]
    kernel.GetLogicalProcessorInformationEx.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel.GetLogicalProcessorInformationEx.restype = ctypes.c_int

    group_count = int(kernel.GetActiveProcessorGroupCount())
    groups = []
    for group_id in range(group_count):
        count = int(kernel.GetActiveProcessorCount(group_id))
        groups.append({"group_id": group_id, "logical_cpu_count": count,
                       "logical_processors": [{"group_id": group_id, "processor_number": n} for n in range(count)]})

    size = ctypes.c_uint32(0)
    kernel.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))
    if not size.value:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_string_buffer(size.value)
    if not kernel.GetLogicalProcessorInformationEx(0, buffer, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    cores = []
    offset = 0
    base_offset = 24
    affinity_size = ctypes.sizeof(GroupAffinity)
    while offset < size.value:
        relationship, record_size = ctypes.c_uint32.from_buffer(buffer, offset).value, ctypes.c_uint32.from_buffer(buffer, offset + 4).value
        if record_size < base_offset or offset + record_size > size.value:
            raise ValueError("invalid processor-core topology record")
        group_total = ctypes.c_ushort.from_buffer(buffer, offset + 8 + 22).value
        processors = []
        for index in range(group_total):
            entry = GroupAffinity.from_buffer(buffer, offset + 8 + base_offset + index * affinity_size)
            mask = int(entry.mask)
            bit = 0
            while mask:
                if mask & 1:
                    processors.append({"group_id": int(entry.group), "processor_number": bit})
                mask >>= 1
                bit += 1
        cores.append({"core_id": len(cores), "logical_processors": processors,
                      "efficiency_class": buffer.raw[offset + 9]})
        offset += record_size

    process = kernel.GetCurrentProcess()
    thread_affinity = GroupAffinity()
    if not kernel.GetThreadGroupAffinity(kernel.GetCurrentThread(), ctypes.byref(thread_affinity)):
        raise ctypes.WinError(ctypes.get_last_error())
    process_mask, system_mask = word(), word()
    affinity = None
    if kernel.GetProcessAffinityMask(process, ctypes.byref(process_mask), ctypes.byref(system_mask)):
        active = next((g for g in groups if g["group_id"] == thread_affinity.group), None)
        if active:
            allowed_mask = int(process_mask.value)
            # A thread group restriction is also part of the effective allowed set.
            if allowed_mask:
                allowed_mask &= int(thread_affinity.mask)
            ids = []
            bit = 0
            while allowed_mask:
                if allowed_mask & 1:
                    ids.append({"group_id": int(thread_affinity.group), "processor_number": bit})
                allowed_mask >>= 1
                bit += 1
            affinity = {"source": "GetProcessAffinityMask and GetThreadGroupAffinity",
                        "allowed_logical_cpu_count": len(ids), "allowed_logical_cpu_ids": ids,
                        "group_scope_note": "Process affinity mask is reported for the current thread's processor group."}
    return {
        "status": "available", "source": "GetActiveProcessorGroupCount, GetActiveProcessorCount, GetLogicalProcessorInformationEx(RelationProcessorCore), GetProcessAffinityMask, GetThreadGroupAffinity",
        "logical_cpu_count": sum(group["logical_cpu_count"] for group in groups),
        "physical_core_count": len(cores), "processor_group_count": group_count,
        "processor_groups": groups, "process_affinity": affinity, "cores": cores,
    }


def collect_topology() -> dict:
    if platform.system() != "Windows":
        return unavailable("Windows processor topology APIs are not available on this platform", "unsupported")
    try:
        return _windows_topology()
    except Exception as error:
        result = unavailable(f"{type(error).__name__}: {error}", "unavailable")
        result["logical_cpu_count"] = os.cpu_count()
        return result


def safe_collect_topology() -> dict:
    """Return topology diagnostics without allowing them to fail a benchmark."""
    try:
        return collect_topology()
    except Exception as error:
        try:
            logical_cpu_count = os.cpu_count()
        except Exception as cpu_count_error:
            logical_cpu_count = None
            error_message = (
                f"{type(error).__name__}: {error}; "
                f"os.cpu_count failed: {type(cpu_count_error).__name__}: {cpu_count_error}"
            )
        else:
            error_message = f"{type(error).__name__}: {error}"
        return {
            "status": "unavailable",
            "source": "Windows processor topology APIs",
            "error": error_message,
            "logical_cpu_count": logical_cpu_count,
            "physical_core_count": None,
            "processor_group_count": None,
            "processor_groups": [],
            "process_affinity": None,
            "cores": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="also write the diagnostic JSON to this path")
    parser.add_argument(
        "--analyze-cpu", action="append", default=[], metavar="N|GROUP:N",
        help="analyze a processor number (group 0) or a group-qualified CPU, e.g. 1:0",
    )
    args = parser.parse_args()
    result = collect_topology()
    try:
        requested = []
        for value in args.analyze_cpu:
            if ":" in value:
                group_text, processor_text = value.split(":", 1)
                requested.append({"group_id": int(group_text), "processor_number": int(processor_text)})
            else:
                requested.append(int(value))
        if result.get("status") == "available":
            analysis = analyze_topology(result, requested)
        elif requested:
            analysis = analyze_topology(result, requested)  # raises a status-specific diagnostic
        else:
            analysis = None
    except (TopologyUnavailableError, ValueError) as error:
        parser.error(str(error))
    output = dict(result)
    output["analysis"] = analysis
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print("CPU Topology")
    print(f"Logical CPUs: {result['logical_cpu_count']}")
    print(f"Physical cores: {result['physical_core_count'] if result['physical_core_count'] is not None else 'unknown'}")
    print(f"Processor groups: {result['processor_group_count'] if result['processor_group_count'] is not None else 'unknown'}")
    affinity = result.get("process_affinity")
    print(f"Process affinity CPUs: {affinity['allowed_logical_cpu_count'] if affinity else 'unknown'}")
    if analysis is not None:
        print("Threads per physical core:")
        for thread_count, core_count in analysis["topology_summary"]["physical_cores_by_logical_thread_count"].items():
            print(f"  {thread_count} thread(s): {core_count} core(s)")
        classes = analysis["topology_summary"]["efficiency_class_physical_core_counts"]
        if classes:
            print("EfficiencyClass raw values:")
            for efficiency_class, core_count in classes.items():
                cpu_count = analysis["topology_summary"]["efficiency_class_logical_cpu_counts"][efficiency_class]
                print(f"  efficiency_class {efficiency_class}: {core_count} physical core(s), {cpu_count} logical CPU(s)")
    for item in (analysis["logical_cpu_analysis"] if analysis is not None else []):
        cpu = item["logical_cpu"]
        core_processors = ", ".join(
            str(processor["processor_number"]) if processor["group_id"] == 0
            else f"{processor['group_id']}:{processor['processor_number']}"
            for processor in item["logical_processors_on_core"]
        )
        label = str(cpu["processor_number"]) if cpu["group_id"] == 0 else f"{cpu['group_id']}:{cpu['processor_number']}"
        print(f"\nLogical CPU {label}")
        print(f"  physical core: {item['core_id']}")
        print(f"  logical processors on this core: [{core_processors}]")
        print(f"  efficiency_class: {item['efficiency_class'] if item['efficiency_class'] is not None else 'unknown'}")
    for comparison in (analysis["comparisons"] if analysis is not None else []):
        first = comparison["first_logical_cpu"]
        second = comparison["second_logical_cpu"]
        print(f"\n{_cpu_label(first)} vs {_cpu_label(second)}")
        print(f"  same processor group: {'yes' if comparison['same_processor_group'] else 'no'}")
        print(f"  same physical core: {'yes' if comparison['same_physical_core'] else 'no'}")
        same_class = comparison["same_efficiency_class"]
        print(f"  same efficiency class: {'unknown' if same_class is None else ('yes' if same_class else 'no')}")
    for group in result["processor_groups"]:
        print(f"\nGroup {group['group_id']}\nLogical processors: {group['logical_cpu_count']}")
    if result.get("error"):
        print(f"Diagnostic status: {result['status']} ({result['error']})")
    if args.output:
        print(f"recorded={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
