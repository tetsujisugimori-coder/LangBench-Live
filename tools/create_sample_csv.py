import csv
import sys
from pathlib import Path


DEFAULT_ROWS = 10
FILE_NAME = "readingTest.csv"
HEADER = ["id", "name", "category", "value", "memo"]
CATEGORIES = ["A", "B", "C"]


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_rows(args: list[str]) -> int:
    if not args:
        return DEFAULT_ROWS

    if len(args) > 1:
        raise ValueError("Specify exactly one row count. Example: python tools/create_sample_csv.py 100000")

    try:
        rows = int(args[0])
    except ValueError as error:
        raise ValueError("Row count must be a positive integer. Example: python tools/create_sample_csv.py 100000") from error

    if rows <= 0:
        raise ValueError("Row count must be a positive integer.")

    return rows


def build_row(row_id: int) -> list[object]:
    category = CATEGORIES[(row_id - 1) % len(CATEGORIES)]
    value = 100 + ((row_id - 1) % 1000)
    return [
        row_id,
        f"item_{row_id:06d}",
        category,
        value,
        f"memo_{row_id:06d}",
    ]


def create_csv(csv_path: Path, rows: int) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(HEADER)
        for row_id in range(1, rows + 1):
            writer.writerow(build_row(row_id))


def main() -> int:
    try:
        rows = parse_rows(sys.argv[1:])
        project_root = get_project_root()
        csv_path = project_root / "data" / FILE_NAME
        create_csv(csv_path, rows)
    except Exception as error:
        print(f"status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1

    print(f"file=data/{FILE_NAME}")
    print(f"rows={rows}")
    print("status=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
