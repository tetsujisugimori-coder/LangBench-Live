import csv
import sys
from pathlib import Path


SAMPLES = [("small", 1000), ("medium", 100000), ("large", 1000000)]
HEADER = ["id", "name", "category", "value", "memo"]
CATEGORIES = ["A", "B", "C"]


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
        project_root = get_project_root()
        data_dir = project_root / "data"
        created_samples = []

        for sample_name, rows in SAMPLES:
            file_name = f"readingTest_{sample_name}.csv"
            csv_path = data_dir / file_name
            create_csv(csv_path, rows)
            created_samples.append((file_name, rows))
    except Exception as error:
        print("status=error", file=sys.stderr)
        print(f"message={error}", file=sys.stderr)
        return 1

    for file_name, rows in created_samples:
        print(f"file=data/{file_name}")
        print(f"rows={rows}")
    print("status=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
