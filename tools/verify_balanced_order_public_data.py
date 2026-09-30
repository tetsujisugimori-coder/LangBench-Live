#!/usr/bin/env python3
"""Verify committed balanced-order publication by rebuilding it from public samples."""
import csv, json, statistics, sys
from pathlib import Path

def main() -> int:
    root = Path(sys.argv[1]); data = json.loads((root / "public-data.json").read_text())
    rows = list(csv.DictReader((root / "public-samples.csv").open(encoding="utf-8")))
    if len(rows) != 3600: raise ValueError("expected exactly 3,600 public samples")
    for run in data["runs"]:
        for language, result in run["languages"].items():
            values = {case: [float(r["elapsed_ms"]) for r in rows if int(r["series_run"]) == run["series_run"] and r["language"] == language and r["case"] == case] for case in ("direct", "function_call")}
            if any(len(v) != 50 for v in values.values()): raise ValueError("sample identity/count mismatch")
            delta = statistics.median(values["function_call"]) - statistics.median(values["direct"])
            if delta != result["median_delta_ms"]: raise ValueError("published aggregate mismatch")
    print("balanced-order public data verified: 3600 samples")
    return 0
if __name__ == "__main__": raise SystemExit(main())
