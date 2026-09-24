"""Inspect ordered samples in validated function_call_numeric_sum archives."""

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .compare_archives import ArchiveError, LANGUAGES, load_archive
    from .show_archive_metrics import CASES, format_number, identity
    from .validate_result_json import median_from_samples
else:
    from compare_archives import ArchiveError, LANGUAGES, load_archive
    from show_archive_metrics import CASES, format_number, identity
    from validate_result_json import median_from_samples


def build_report(paths: list[Path], archives: list[dict], languages: tuple[str, ...]) -> dict:
    runs = []
    for path, archive in zip(paths, archives):
        cases = []
        for language in languages:
            for case in CASES:
                samples = archive["results"][language]["results"][case]["samples_ms"]
                midpoint = len(samples) // 2
                cases.append({"language": language, "case": case, "samples_ms": samples,
                              "median_ms": median_from_samples(samples),
                              "min_ms": min(samples), "max_ms": max(samples),
                              "first_half_median_ms": median_from_samples(samples[:midpoint]),
                              "second_half_median_ms": median_from_samples(samples[midpoint:])})
        runs.append({**identity(path, archive), "cases": cases})
    return {"schema_version": "1.0", "unit": "ms", "runs": runs}


def print_text(report: dict) -> None:
    print("検証済み履歴のサンプル。入力順、単位 ms。中央値は samples_ms から再計算。")
    for index, run in enumerate(report["runs"], 1):
        print(f"履歴 {index}: {run['path']} (experiment_id={run['experiment_id']}, "
              f"archive_id={run['archive_id']}, archived_at={run['archived_at']})")
        for row in run["cases"]:
            print(f"  {row['language']}/{row['case']}: 中央値 {format_number(row['median_ms'])}, "
                  f"最小 {format_number(row['min_ms'])}, 最大 {format_number(row['max_ms'])}, "
                  f"前半 {format_number(row['first_half_median_ms'])}, "
                  f"後半 {format_number(row['second_half_median_ms'])}")
            print(f"    samples_ms (1-{len(row['samples_ms'])}): " + ", ".join(
                f"{i}:{format_number(value)}" for i, value in enumerate(row["samples_ms"], 1)))
    print("Cの各サンプルは0.001 ms単位で保存。丸め幅程度の差を原因として解釈しないでください。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--all-languages", action="store_true", help="include Python and JavaScript")
    parser.add_argument("archives", type=Path, nargs="+", help="one or more archive directories")
    args = parser.parse_args()
    try:
        resolved = [path.resolve() for path in args.archives]
        if len(set(resolved)) != len(resolved):
            raise ArchiveError("DUPLICATE_ARCHIVE", "each input must be a distinct archive directory")
        archives = [load_archive(path) for path in args.archives]
        archive_ids = [archive["index"]["archive_id"] for archive in archives]
        if len(set(archive_ids)) != len(archive_ids):
            raise ArchiveError("DUPLICATE_ARCHIVE", "each input must have a distinct archive_id")
        report = build_report(args.archives, archives, LANGUAGES if args.all_languages else ("c",))
    except (ArchiveError, OSError) as error:
        code = error.code if isinstance(error, ArchiveError) else "IO_ERROR"
        if args.json:
            print(json.dumps({"error": {"code": code, "message": str(error)}}, ensure_ascii=False))
        else:
            print(f"検証エラー [{code}]: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
