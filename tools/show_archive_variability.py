"""Show variation of case medians across independent archived runs."""

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

if __package__:
    from .compare_archives import ArchiveError, LANGUAGES, compare_archives, load_archive
    from .show_archive_metrics import CASES, VERDICT_LABELS, format_number, identity
    from .validate_result_json import median_from_samples
else:
    from compare_archives import ArchiveError, LANGUAGES, compare_archives, load_archive
    from show_archive_metrics import CASES, VERDICT_LABELS, format_number, identity
    from validate_result_json import median_from_samples


def build_report(paths: list[Path], archives: list[dict]) -> dict:
    runs = []
    for path, archive in zip(paths, archives):
        medians = [
            {"language": language, "case": case,
             "median_ms": median_from_samples(archive["results"][language]["results"][case]["samples_ms"])}
            for language in LANGUAGES for case in CASES
        ]
        runs.append({**identity(path, archive), "medians": medians})

    counts = {"comparable": 0, "caution": 0, "incomparable": 0}
    pairs = []
    for (left_index, left), (right_index, right) in itertools.combinations(enumerate(archives), 2):
        judgment = compare_archives(left, right)
        counts[judgment["verdict"]] += 1
        pairs.append({"left_index": left_index, "right_index": right_index, **judgment})
    verdict = "incomparable" if counts["incomparable"] else "caution" if counts["caution"] else "comparable"
    report = {"schema_version": "1.0", "unit": "ms", "verdict": verdict,
              "runs": runs, "pairwise": {"counts": counts, "pairs": pairs}}
    if verdict != "incomparable":
        cases = []
        for position, (language, case) in enumerate(itertools.product(LANGUAGES, CASES)):
            values = [run["medians"][position]["median_ms"] for run in runs]
            low, high = min(values), max(values)
            delta = high - low
            row = {"language": language, "case": case, "min_median_ms": low,
                   "max_median_ms": high, "range_ms": delta if math.isfinite(delta) else None}
            if row["range_ms"] is None:
                row["range_unavailable_reason"] = "NONFINITE_RESULT"
            cases.append(row)
        report["aggregate"] = {"status": "reference" if verdict == "caution" else "comparable",
                               "cases": cases}
    return report


def print_text(report: dict) -> None:
    print(f"判定: {VERDICT_LABELS[report['verdict']]} ({report['verdict']})")
    print("各履歴の中央値は実行内の samples_ms から計算した値です。単位: ms")
    for index, run in enumerate(report["runs"]):
        print(f"履歴 {index + 1}: {run['path']} (archive_id={run['archive_id']}, "
              f"experiment_id={run['experiment_id']}, archived_at={run['archived_at']})")
        for row in run["medians"]:
            print(f"  {row['language']}/{row['case']}: {format_number(row['median_ms'])} ms")
    counts = report["pairwise"]["counts"]
    print(f"全組判定: comparable={counts['comparable']}, caution={counts['caution']}, "
          f"incomparable={counts['incomparable']}")
    for pair in report["pairwise"]["pairs"]:
        print(f"  履歴 {pair['left_index'] + 1}-{pair['right_index'] + 1}: {pair['verdict']}")
        for reason in pair["reasons"]:
            print(f"    [{reason['code']}] {reason['field']}: {reason['message']}")
    if report["verdict"] == "incomparable":
        print("比較不可の組があるため、全履歴の集団の最小・最大・差は表示しません。")
        return
    if report["verdict"] == "caution":
        print("実行間の最小・最大・差は参考値です。原因コードと対象フィールドは上記の各組に示します。")
    else:
        print("実行間の最小・最大・差 (最大−最小):")
    for row in report["aggregate"]["cases"]:
        spread = f"{format_number(row['range_ms'])} ms" if row["range_ms"] is not None else "計算不能 (NONFINITE_RESULT)"
        print(f"  {row['language']}/{row['case']}: 最小 {format_number(row['min_median_ms'])} ms, "
              f"最大 {format_number(row['max_median_ms'])} ms, 差 {spread}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("archives", type=Path, nargs="+", help="two or more archive directories")
    args = parser.parse_args()
    if len(args.archives) < 2:
        parser.error("at least two archive directories are required")
    try:
        resolved = [path.resolve() for path in args.archives]
        if len(set(resolved)) != len(resolved):
            raise ArchiveError("DUPLICATE_ARCHIVE", "each input must be a distinct archive directory")
        archives = [load_archive(path) for path in args.archives]
        archive_ids = [archive["index"]["archive_id"] for archive in archives]
        if len(set(archive_ids)) != len(archive_ids):
            raise ArchiveError("DUPLICATE_ARCHIVE", "each input must have a distinct archive_id")
        report = build_report(args.archives, archives)
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
