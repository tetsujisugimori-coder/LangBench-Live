"""Show descriptive measurements from two validated function_call_numeric_sum archives."""

import argparse
import json
import math
import sys
from pathlib import Path

if __package__:
    from .compare_archives import ArchiveError, LANGUAGES, compare_archives, load_archive
    from .validate_result_json import median_from_samples
else:
    from compare_archives import ArchiveError, LANGUAGES, compare_archives, load_archive
    from validate_result_json import median_from_samples

CASES = ("direct", "function_call")
VERDICT_LABELS = {"comparable": "比較可能", "caution": "注意付き", "incomparable": "比較不可"}


def identity(path: Path, archive: dict) -> dict:
    index = archive["index"]
    return {"path": str(path), "archive_id": index["archive_id"],
            "experiment_id": index["experiment_id"], "archived_at": index["archived_at"]}


def build_report(left_path: Path, right_path: Path, left: dict, right: dict) -> dict:
    judgment = compare_archives(left, right)
    verdict = judgment["verdict"]
    measurements = []
    for language in LANGUAGES:
        for case in CASES:
            left_ms = median_from_samples(left["results"][language]["results"][case]["samples_ms"])
            right_ms = median_from_samples(right["results"][language]["results"][case]["samples_ms"])
            row = {"language": language, "case": case,
                   "left_median_ms": left_ms, "right_median_ms": right_ms}
            if verdict != "incomparable":
                delta = right_ms - left_ms
                row["delta_ms"] = delta if math.isfinite(delta) else None
                if row["delta_ms"] is None:
                    row["delta_unavailable_reason"] = "NONFINITE_RESULT"
                row["faster"] = "left" if right_ms > left_ms else "right" if right_ms < left_ms else "equal"
                if left_ms <= 0:
                    row["change_percent"] = None
                    row["change_percent_unavailable_reason"] = (
                        "LEFT_MEDIAN_ZERO" if left_ms == 0 else "LEFT_MEDIAN_NEGATIVE")
                elif row["delta_ms"] is None:
                    row["change_percent"] = None
                    row["change_percent_unavailable_reason"] = "NONFINITE_RESULT"
                else:
                    percent = (delta / left_ms) * 100
                    row["change_percent"] = percent if math.isfinite(percent) else None
                    if row["change_percent"] is None:
                        row["change_percent_unavailable_reason"] = "NONFINITE_RESULT"
            measurements.append(row)
    return {"schema_version": "1.0", "left": identity(left_path, left),
            "right": identity(right_path, right), **judgment, "measurements": measurements}


def format_number(value: float) -> str:
    return f"{value:.12g}"


def format_signed(value: float) -> str:
    return f"{value:+.12g}"


def print_text(report: dict) -> None:
    verdict = report["verdict"]
    print(f"判定: {VERDICT_LABELS[verdict]} ({verdict})")
    for side in ("left", "right"):
        item = report[side]
        print(f"{'左' if side == 'left' else '右'}: {item['path']} "
              f"(archive_id={item['archive_id']}, experiment_id={item['experiment_id']})")
    if verdict == "caution":
        print("以下の差・変化率・速度の表示は参考値です。")
    if verdict == "incomparable":
        print("条件が異なるため、差・変化率・速度の優劣は表示しません。")
    else:
        print("差(ms) = 右中央値 − 左中央値。変化率(%) = (右中央値 − 左中央値) / 左中央値 × 100。")
        print("時間が短い方が速く、差が正なら右が遅く、負なら右が速いです。左中央値が正なら変化率も同じ符号です。")
    for item in report["reasons"]:
        print(f"理由 [{item['code']}] {item['field']}: {item['message']}")
    for row in report["measurements"]:
        line = (f"{row['language']}/{row['case']}: 左 {format_number(row['left_median_ms'])} ms, "
                f"右 {format_number(row['right_median_ms'])} ms")
        if verdict != "incomparable":
            delta = (f"{format_signed(row['delta_ms'])} ms" if row["delta_ms"] is not None
                     else "計算不能 (有限な差にならない)")
            percent = (f"{format_signed(row['change_percent'])}%" if row["change_percent"] is not None
                       else "計算不能 (左中央値が0)" if row["change_percent_unavailable_reason"] == "LEFT_MEDIAN_ZERO"
                       else "計算不能 (左中央値が負)" if row["change_percent_unavailable_reason"] == "LEFT_MEDIAN_NEGATIVE"
                       else "計算不能 (有限な変化率にならない)")
            faster = {"left": "左が速い", "right": "右が速い", "equal": "同じ中央値"}[row["faster"]]
            line += f", 差 {delta}, 変化率 {percent}, {faster}"
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    try:
        left = load_archive(args.left)
        right = load_archive(args.right)
        report = build_report(args.left, args.right, left, right)
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
