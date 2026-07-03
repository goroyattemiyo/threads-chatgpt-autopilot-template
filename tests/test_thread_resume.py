import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.post_daily import post_schedule_item
from src.schedule_store import ScheduleFile


class FixedRandom:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, minimum, maximum):
        value = self.values.pop(0)
        assert minimum <= value <= maximum
        return value


class FakeAPI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_text(self, text, reply_to_id=""):
        self.calls.append((text, reply_to_id))
        return self.responses.pop(0)


class ThreadResumeTests(unittest.TestCase):
    def test_retry_continues_from_unfinished_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schedule_path = root / "week.yml"
            item = {
                "id": "thread-1",
                "scheduled_at": "2026-07-06T07:00:00+09:00",
                "publish_after": "2026-07-06T07:02:00+09:00",
                "status": "ready",
                "text": "root",
                "thread_posts": [{"text": "reply1"}, {"text": "reply2"}],
                "thread_delay_min_seconds": 8,
                "thread_delay_max_seconds": 25,
                "threads_post_id": "",
                "thread_post_ids": [],
            }
            schedule = ScheduleFile(
                schedule_path, date(2026, 7, 6), date(2026, 7, 12), [item]
            )
            log_path = root / "posted_log.yml"

            first = FakeAPI(
                [{"id": "root-id"}, {"id": "reply-1"}, {"error": "failed"}]
            )
            result = post_schedule_item(
                schedule,
                item,
                api=first,
                sleep_fn=lambda _: None,
                rng=FixedRandom([8, 9]),
                log_path=log_path,
            )
            self.assertEqual(result, 1)
            self.assertEqual(item["status"], "error")
            self.assertEqual(item["thread_progress"]["reply_ids"], ["reply-1"])

            item["status"] = "ready"
            second = FakeAPI([{"id": "reply-2"}])
            result = post_schedule_item(
                schedule,
                item,
                api=second,
                sleep_fn=lambda _: None,
                rng=FixedRandom([10]),
                log_path=log_path,
            )
            self.assertEqual(result, 0)
            self.assertEqual(second.calls, [("reply2", "reply-1")])
            self.assertEqual(item["status"], "posted")
            self.assertEqual(item["thread_post_ids"], ["reply-1", "reply-2"])


if __name__ == "__main__":
    unittest.main()
