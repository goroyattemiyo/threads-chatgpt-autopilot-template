from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.github_checkpoint import checkpoint_enabled, checkpoint_file
from src.post_due import audit_overdue


class WorkflowSafetyTests(unittest.TestCase):
    def test_checkpoint_requires_explicit_opt_in(self):
        with patch.dict(
            os.environ,
            {"GITHUB_ACTIONS": "true", "ENABLE_GITHUB_CHECKPOINTS": ""},
            clear=False,
        ):
            self.assertFalse(checkpoint_enabled())

    def test_checkpoint_is_noop_without_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.yml"
            path.write_text("status: ready\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"GITHUB_ACTIONS": "true", "ENABLE_GITHUB_CHECKPOINTS": ""},
                clear=False,
            ), patch("src.github_checkpoint.requests.get") as request_get:
                checkpoint_file(path, "test checkpoint")
                request_get.assert_not_called()

    @patch("src.post_due.overdue_ready_items")
    @patch("src.post_due.load_active_schedule_files", return_value=[])
    def test_overdue_findings_are_successful_audit(
        self,
        _load_files,
        overdue_items,
    ):
        overdue_items.return_value = [
            {
                "id": "post-1",
                "file": "posts/schedules/week.yml",
                "classification": "review_required",
                "reason": "publish time has passed",
            }
        ]
        self.assertEqual(audit_overdue(), 0)

    def test_workflow_yaml_is_parseable(self):
        workflow_dir = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for path in sorted(workflow_dir.glob("*.yml")):
            with self.subTest(path=path.name):
                yaml.compose(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
