import json
import tempfile
import unittest
from pathlib import Path
from tools.analyze_balanced_order import PLAN, analyze

class BalancedOrderTest(unittest.TestCase):
    def make_series(self, root: Path):
        runs = []
        for number, order in enumerate(PLAN, 1):
            experiment = f"experiment-{number}"
            runs.append({"status":"success", "experiment_id":experiment, "block":(number-1)//4+1,
                         "requested_order":order, "actual_order":order})
            cases = []
            sequence = ("direct", "function_call") if order == "direct_first" else ("function_call", "direct")
            for language in ("python", "javascript", "c"):
                for case in sequence:
                    base = 1.0 if case == "direct" else 2.0
                    cases.append({"language":language, "case":case, "samples_ms":[base + i / 1000 for i in range(50)]})
            (root / f"run-{number:02d}-samples.json").write_text(json.dumps({"runs":[{"archive_id":f"archive-{number}", "cases":cases}]}))
        series = {"series_id":"series-test", "planned_orders":list(PLAN), "requested_runs":12, "successful_runs":12, "runs":runs}
        path = root / "runs.json"; path.write_text(json.dumps(series)); return path

    def test_fixed_plan_and_3600_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, samples = analyze(self.make_series(Path(directory)))
            self.assertEqual(3600, len(samples)); self.assertEqual(6, payload["order_summaries"]["c"]["direct_first"]["run_count"])
            self.assertEqual(1, samples[0]["case_position"]); self.assertEqual("direct", samples[0]["case"])

    def test_incomplete_series_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_series(Path(directory)); data = json.loads(path.read_text()); data["successful_runs"] = 11; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "incomplete"): analyze(path)

if __name__ == "__main__": unittest.main()
