import tempfile
import unittest
from pathlib import Path

from src.sync_post_schedule import build_cron_entries, replace_generated_schedule, sync


class SyncPostScheduleTests(unittest.TestCase):
    def test_builds_three_utc_runs_for_20_jst(self):
        entries = build_cron_entries("Asia/Tokyo", ["20:00"], [-3, 2, 7])
        self.assertEqual(
            entries,
            [
                "    - cron: '57 10 * * *'",
                "    - cron: '2 11 * * *'",
                "    - cron: '7 11 * * *'",
            ],
        )

    def test_removes_duplicate_cron_entries(self):
        entries = build_cron_entries("Asia/Tokyo", ["20:00", "20:00"], [-3, 2, 7])
        self.assertEqual(len(entries), 3)

    def test_replaces_only_generated_block(self):
        workflow = """name: test\non:\n  schedule:\n    # BEGIN AUTO-GENERATED POSTING SCHEDULE\n    - cron: '0 0 * * *'\n    # END AUTO-GENERATED POSTING SCHEDULE\n  workflow_dispatch:\n"""
        updated = replace_generated_schedule(workflow, ["    - cron: '2 11 * * *'"])
        self.assertIn("    - cron: '2 11 * * *'", updated)
        self.assertIn("  workflow_dispatch:", updated)
        self.assertNotIn("    - cron: '0 0 * * *'", updated)

    def test_sync_uses_service_config_as_source_of_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "service.yml"
            workflow = root / "post-due.yml"
            config.write_text(
                """service:\n  timezone: Asia/Tokyo\nposting:\n  time_slots:\n    night: \"20:00\"\n  schedule_offsets_minutes:\n    - -3\n    - 2\n    - 7\n""",
                encoding="utf-8",
            )
            workflow.write_text(
                """on:\n  schedule:\n    # BEGIN AUTO-GENERATED POSTING SCHEDULE\n    - cron: '0 0 * * *'\n    # END AUTO-GENERATED POSTING SCHEDULE\n""",
                encoding="utf-8",
            )
            self.assertTrue(sync(config, workflow))
            text = workflow.read_text(encoding="utf-8")
            self.assertIn("    - cron: '57 10 * * *'", text)
            self.assertIn("    - cron: '2 11 * * *'", text)
            self.assertIn("    - cron: '7 11 * * *'", text)


if __name__ == "__main__":
    unittest.main()
