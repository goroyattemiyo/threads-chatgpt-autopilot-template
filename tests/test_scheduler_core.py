import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.schedule_store import ScheduleFile
from src.scheduler import ensure_timing_fields, select_candidate

JST = ZoneInfo("Asia/Tokyo")


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def randint(self, minimum, maximum):
        assert minimum <= self.value <= maximum
        return self.value


class SchedulerCoreTests(unittest.TestCase):
    def test_delay_is_fixed_after_first_draw(self):
        item = {
            "id": "p1",
            "scheduled_at": "2026-07-06T07:00:00+09:00",
            "delay_min_minutes": 2,
            "delay_max_minutes": 14,
            "status": "ready",
        }
        ensure_timing_fields(item, JST, rng=FixedRandom(9))
        self.assertEqual(item["publish_after"], "2026-07-06T07:09:00+09:00")
        before = dict(item)
        ensure_timing_fields(item, JST, rng=FixedRandom(14))
        self.assertEqual(item, before)

    def test_legacy_slot_is_migrated(self):
        item = {
            "id": "legacy",
            "date": "2026-07-06",
            "time_slot": "afternoon",
            "status": "ready",
        }
        ensure_timing_fields(item, JST, rng=FixedRandom(0))
        self.assertEqual(item["scheduled_at"], "2026-07-06T15:00:00+09:00")
        self.assertEqual(item["publish_after"], "2026-07-06T15:00:00+09:00")

    def test_posting_resume_has_priority(self):
        schedule = ScheduleFile(
            Path("week.yml"),
            date(2026, 7, 6),
            date(2026, 7, 12),
            [
                {
                    "id": "ready-old",
                    "scheduled_at": "2026-07-06T07:00:00+09:00",
                    "publish_after": "2026-07-06T07:02:00+09:00",
                    "status": "ready",
                },
                {
                    "id": "posting-new",
                    "scheduled_at": "2026-07-06T08:00:00+09:00",
                    "publish_after": "2026-07-06T08:02:00+09:00",
                    "status": "posting",
                },
            ],
        )
        selected = select_candidate(
            [schedule], datetime(2026, 7, 6, 9, 0, tzinfo=JST), JST
        )
        self.assertEqual(selected.item["id"], "posting-new")

    def test_later_posted_blocks_older_same_series(self):
        schedule = ScheduleFile(
            Path("week.yml"),
            date(2026, 7, 6),
            date(2026, 7, 12),
            [
                {
                    "id": "series-001",
                    "series_id": "series-a",
                    "scheduled_at": "2026-07-06T07:00:00+09:00",
                    "publish_after": "2026-07-06T07:02:00+09:00",
                    "status": "ready",
                },
                {
                    "id": "series-002",
                    "series_id": "series-a",
                    "scheduled_at": "2026-07-06T08:00:00+09:00",
                    "publish_after": "2026-07-06T08:02:00+09:00",
                    "status": "posted",
                    "threads_post_id": "existing-id",
                },
            ],
        )
        now = datetime(2026, 7, 6, 9, 0, tzinfo=JST)
        self.assertIsNone(select_candidate([schedule], now, JST))
        schedule.entries[0]["allow_out_of_order"] = True
        self.assertEqual(select_candidate([schedule], now, JST).item["id"], "series-001")


if __name__ == "__main__":
    unittest.main()
