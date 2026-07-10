import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.schedule_store import ScheduleFile
from src.scheduler import overdue_ready_items

JST = ZoneInfo("Asia/Tokyo")


class OverdueGraceTests(unittest.TestCase):
    def setUp(self):
        self.schedule = ScheduleFile(
            Path("week.yml"),
            date(2026, 7, 6),
            date(2026, 7, 12),
            [
                {
                    "id": "post-1",
                    "scheduled_at": "2026-07-11T07:00:00+09:00",
                    "publish_after": "2026-07-11T07:00:00+09:00",
                    "status": "ready",
                }
            ],
        )

    @patch("src.scheduler.get_config", return_value=15)
    def test_post_is_not_overdue_at_grace_boundary(self, _get_config):
        now = datetime(2026, 7, 11, 7, 15, tzinfo=JST)
        self.assertEqual(overdue_ready_items([self.schedule], now, JST), [])

    @patch("src.scheduler.get_config", return_value=15)
    def test_post_is_overdue_after_grace_boundary(self, _get_config):
        now = datetime(2026, 7, 11, 7, 15, 1, tzinfo=JST)
        results = overdue_ready_items([self.schedule], now, JST)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["classification"], "review_required")
        self.assertIn("15-minute grace period", results[0]["reason"])


if __name__ == "__main__":
    unittest.main()
