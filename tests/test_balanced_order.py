import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_balanced_order import (CSV_COLUMNS, PLAN, analyze, csv_rows,
                                          manifest_payload, summary_text)
from tools.verify_balanced_order_public_data import verify


class BalancedOrderTest(unittest.TestCase):
    def make_series(self, root: Path) -> Path:
        runs = []
        for number, order in enumerate(PLAN, 1):
            experiment, archive = f"experiment-{number}", f"archive-{number}"
            runs.append({"order": number, "status": "success", "experiment_id": experiment,
                         "archive_id": archive, "block": (number - 1) // 4 + 1,
                         "requested_order": order, "actual_order": order})
            cases = []
            for language in ("python", "javascript", "c"):
                for case in ("direct", "function_call"):
                    base = 1.0 if case == "direct" else 2.0
                    cases.append({"language": language, "case": case,
                                  "samples_ms": [base + i / 1000 for i in range(50)]})
            report = {"runs": [{"experiment_id": experiment, "archive_id": archive,
                                "run_ids": {language: f"run-{number}-{language}" for language in ("python", "javascript", "c")},
                                "cases": cases}]}
            (root / f"run-{number:02d}-samples.json").write_text(json.dumps(report), encoding="utf-8")
        series = {"series_id": "series-test", "git_head": "a" * 40,
                  "input_sha256": ["source=" + "b" * 64], "host": {"os": "fixture"},
                  "planned_orders": list(PLAN), "requested_runs": 12, "successful_runs": 12, "runs": runs}
        path = root / "runs.json"; path.write_text(json.dumps(series), encoding="utf-8"); return path

    def publish(self, root: Path):
        payload, samples = analyze(self.make_series(root))
        (root / "public-data.json").write_text(json.dumps(payload), encoding="utf-8")
        with (root / "public-data.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS); writer.writeheader(); writer.writerows(csv_rows(payload))
        with (root / "public-samples.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=samples[0]); writer.writeheader(); writer.writerows(samples)
        (root / "manifest.json").write_text(json.dumps(manifest_payload(payload)), encoding="utf-8")
        (root / "summary.md").write_text(summary_text(payload), encoding="utf-8")
        return payload

    def test_fixed_plan_publication_and_full_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); payload = self.publish(root); verify(root)
            with (root / "public-samples.csv").open(encoding="utf-8") as stream:
                self.assertEqual(3600, sum(1 for _ in stream) - 1)
            self.assertEqual(6, payload["order_summaries"]["c"]["direct_first"]["run_count"])
            self.assertEqual(4, payload["block_summaries"]["python"]["1"]["run_count"])

    def test_incomplete_series_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_series(Path(directory)); data = json.loads(path.read_text(encoding="utf-8"))
            data["successful_runs"] = 11; path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incomplete"): analyze(path)

    def test_report_identity_block_and_duplicate_case_are_rejected(self):
        mutations = (("identity", lambda root, series: self.mutate_report(root, "experiment_id", "wrong")),
                     ("block", lambda root, series: series["runs"][0].update(block=2)),
                     ("duplicate", lambda root, series: self.duplicate_case(root)))
        for name, mutation in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); path = self.make_series(root); series = json.loads(path.read_text(encoding="utf-8"))
                mutation(root, series); path.write_text(json.dumps(series), encoding="utf-8")
                with self.assertRaises(ValueError): analyze(path)

    @staticmethod
    def mutate_report(root, key, value):
        path = root / "run-01-samples.json"; report = json.loads(path.read_text(encoding="utf-8")); report["runs"][0][key] = value; path.write_text(json.dumps(report), encoding="utf-8")

    @staticmethod
    def duplicate_case(root):
        path = root / "run-01-samples.json"; report = json.loads(path.read_text(encoding="utf-8")); report["runs"][0]["cases"][1] = report["runs"][0]["cases"][0]; path.write_text(json.dumps(report), encoding="utf-8")

    def test_verifier_rejects_every_published_aggregate_and_identity_tamper(self):
        mutations = {
            "mean": lambda root, data: data["runs"][0]["languages"]["python"]["direct"].update(mean_ms=99),
            "sd": lambda root, data: data["runs"][0]["languages"]["python"]["direct"].update(sample_sd_ms=99),
            "ratio": lambda root, data: data["runs"][0]["languages"]["python"].update(median_ratio=99),
            "sign": lambda root, data: data["runs"][0]["languages"]["python"].update(sign="negative"),
            "order-summary": lambda root, data: data["order_summaries"]["python"]["direct_first"].update(median_delta_ms=99),
            "block-summary": lambda root, data: data["block_summaries"]["python"]["1"].update(median_delta_ms=99),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); data = self.publish(root); mutation(root, data)
                (root / "public-data.json").write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "mismatch"): verify(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.publish(root)
            with (root / "public-data.csv").open(encoding="utf-8") as stream: rows = list(csv.DictReader(stream))
            rows[0]["direct_mean_ms"] = "99"
            with (root / "public-data.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "mismatch"): verify(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.publish(root)
            with (root / "public-samples.csv").open(encoding="utf-8") as stream: rows = list(csv.DictReader(stream))
            rows[1] = rows[0].copy()
            with (root / "public-samples.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "duplicate"): verify(root)


if __name__ == "__main__": unittest.main()
