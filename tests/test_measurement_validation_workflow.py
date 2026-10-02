import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MeasurementValidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/measurement-validation-windows.yml").read_text(encoding="utf-8")
        cls.runner = (ROOT / "tools/run_measurement_validation.ps1").read_text(encoding="utf-8")

    def test_dispatch_has_no_caller_controlled_inputs_and_uses_dedicated_labels(self):
        dispatch = self.workflow.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:\n", dispatch)
        self.assertNotIn("inputs:", dispatch)
        self.assertIn("runs-on: [self-hosted, Windows, X64, langbench-live-tetsu-windows]", self.workflow)
        self.assertIn("--ref '${{ github.ref }}'", self.workflow)
        self.assertIn("--event '${{ github.event_name }}'", self.workflow)
        self.assertIn('pulls/$number', self.workflow)
        self.assertIn('compare/$merge_sha...$RUN_SHA', self.workflow)
        self.assertIn("SYNC_RUN_ID: ${{ needs.authorize.outputs.sync_run_id }}", self.workflow)

    def test_validation_is_count_one_and_not_balanced(self):
        self.assertIn("-Count 1 -MeasurementOrder direct_first", self.runner)
        self.assertNotIn("-BalancedOrder", self.runner)
        self.assertIn("successful_runs -ne 1", self.runner)
        self.assertIn("Count=1 measurement failed with exit code", self.runner)
        self.assertIn("independent execution directory already exists", self.runner)

    def test_shared_copy_is_checked_locked_and_never_destructively_changed(self):
        for required in ("langbench-operation.lock", "function_call_numeric_sum.lock",
                         "--path-format=absolute','--git-path", "'status','--porcelain','--untracked-files=no'",
                         "'ls-files','--others','--exclude-standard'", "'ls-files','--others','--ignored'",
                         "Get-FileHash", "remote main changed during validation"):
            self.assertIn(required, self.runner)
        lowered = self.runner.lower()
        for prohibited in ("reset --hard", "git clean", "git stash", "git rebase"):
            self.assertNotIn(prohibited, lowered)
        self.assertIn("effective Git filter is refused", self.runner)
        self.assertIn("GIT_ATTR_NOSYSTEM", self.runner)
        self.assertIn("Count=1 measurement failed with exit code", self.runner)
        self.assertIn("& pwsh -NoProfile -Command 'exit 23'", self.runner)

    def test_upload_only_follows_successful_validation_and_checkout_is_not_cleaned(self):
        self.assertIn("clean: false", self.workflow)
        self.assertNotIn("if: ${{ always()", self.workflow)
        self.assertIn("check_function_call_artifact_safety", self.runner)


if __name__ == "__main__": unittest.main()
