"""Capture system CPU busy intervals with Windows QPC timestamps."""

import argparse
import ctypes
import json
import time
from pathlib import Path


class FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


def filetime_value(value):
    return (value.high << 32) | value.low


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--stop", type=Path, required=True)
    parser.add_argument("--interval-ms", type=int, default=20)
    args = parser.parse_args()
    if args.interval_ms < 1:
        parser.error("interval must be positive")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    frequency = ctypes.c_int64()
    if not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)):
        raise OSError(ctypes.get_last_error(), "QueryPerformanceFrequency failed")

    def qpc():
        value = ctypes.c_int64()
        if not kernel.QueryPerformanceCounter(ctypes.byref(value)):
            raise OSError(ctypes.get_last_error(), "QueryPerformanceCounter failed")
        return value.value

    def cpu_times():
        idle, kernel_time, user = FileTime(), FileTime(), FileTime()
        if not kernel.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel_time), ctypes.byref(user)):
            raise OSError(ctypes.get_last_error(), "GetSystemTimes failed")
        return filetime_value(idle), filetime_value(kernel_time), filetime_value(user)

    observations = []
    previous = None
    previous_end = None
    started_qpc = qpc()
    args.ready.write_text("ready\n", encoding="ascii")
    while not args.stop.exists():
        begin = qpc()
        try:
            current = cpu_times()
            error = None
        except OSError as exc:
            current = None
            error = str(exc)
        end = qpc()
        entry = {"start_qpc": previous_end if previous_end is not None else begin,
                 "end_qpc": end, "probe_start_qpc": begin,
                 "probe_duration_qpc": end - begin, "cpu_busy_percent": None,
                 "error": error}
        if previous is not None and current is not None:
            total = (current[1] - previous[1]) + (current[2] - previous[2])
            idle = current[0] - previous[0]
            if total > 0 and 0 <= idle <= total:
                entry["cpu_busy_percent"] = 100 * (total - idle) / total
            else:
                entry["error"] = "invalid CPU time delta"
        elif error is None:
            entry["error"] = "first probe has no preceding CPU time"
        observations.append(entry)
        previous = current
        previous_end = end
        time.sleep(args.interval_ms / 1000)
    result = {"schema_version": "1.0", "clock": "windows_qpc", "frequency_hz": frequency.value,
              "requested_interval_ms": args.interval_ms, "started_qpc": started_qpc,
              "ended_qpc": qpc(), "observations": observations}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
