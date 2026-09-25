"""Read-only CPU topology diagnostics. This module never changes CPU affinity."""

import argparse
import ctypes
import json
import os
import platform
from pathlib import Path


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="also write the diagnostic JSON to this path")
    args = parser.parse_args()
    result = collect_topology()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print("CPU Topology")
    print(f"Logical CPUs: {result['logical_cpu_count']}")
    print(f"Physical cores: {result['physical_core_count'] if result['physical_core_count'] is not None else 'unknown'}")
    print(f"Processor groups: {result['processor_group_count'] if result['processor_group_count'] is not None else 'unknown'}")
    affinity = result.get("process_affinity")
    print(f"Process affinity CPUs: {affinity['allowed_logical_cpu_count'] if affinity else 'unknown'}")
    for group in result["processor_groups"]:
        print(f"\nGroup {group['group_id']}\nLogical processors: {group['logical_cpu_count']}")
    if result.get("error"):
        print(f"Diagnostic status: {result['status']} ({result['error']})")
    if args.output:
        print(f"recorded={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
