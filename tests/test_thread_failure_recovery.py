from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from src.post_daily import post_schedule_item
from src.post_due import select_candidate
from src.schedule_store import ScheduleFile
from src.utils import load_yaml, save_yaml


class FixedRng:
    def randint(self, minimum: int, maximum: int) -> int:
        return minimum


class FakeThreadsAPI:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def _next_response(self) -> dict[str, Any]:
        if not self._responses:
            raise AssertionError("Unexpected extra Threads API call.")
        return self._responses.pop(0)

    def post_text(self, text: str, reply_to_id: str = "") -> dict[str, Any]:
        self.calls.append({"type": "text", "text": text, "reply_to_id": reply_to_id})
        return self._next_response()

    def post_image(
        self,
        text: str,
        image_url: str,
        *,
        alt_text: str = "",
        reply_to_id: str = "",
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "type": "image",
                "text": text,
                "image_url": image_url,
                "alt_text": alt_text,
                "reply_to_id": reply_to_id,
            }
        )
        return self._next_response()


class ThreadFailureRecoveryTests(TestCase):
    def make_item(self, item_id: str) -> dict[str, Any]:
        return {
            "id": item_id,
            "date": "2099-01-09",
            "time_slot": "afternoon",
            "scheduled_at": "2099-01-09T15:00:00+09:00",
            "publish_after": "2099-01-09T15:00:00+09:00",
            "category": "validation",
            "text": "親投稿テスト",
            "thread_posts": [{"text": "返信1テスト"}, {"text": "返信2テスト"}],
            "thread_delay_min_seconds": 0,
            "thread_delay_max_seconds": 0,
            "status": "ready",
            "threads_post_id": "",
            "thread_post_ids": [],
            "posted_at": "",
            "error": "",
        }

    def make_schedule(self, directory: Path, item: dict[str, Any]) -> ScheduleFile:
        path = directory / "2099-01-05_to_2099-01-11.yml"
        schedule = ScheduleFile(
            path=path,
            start=date(2099, 1, 5),
            end=date(2099, 1, 11),
            entries=[item],
        )
        save_yaml(path, schedule.entries)
        return schedule

    def checkpoint_recorder(self, snapshots: list[tuple[str, list[dict[str, Any]]]]):
        def save_checkpoint(schedule_file: ScheduleFile, message: str) -> None:
            save_yaml(schedule_file.path, schedule_file.entries)
            snapshots.append((message, deepcopy(schedule_file.entries)))

        return save_checkpoint

    def test_root_failure_stops_before_any_reply(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.make_item("thread_root_failure")
            schedule = self.make_schedule(root, item)
            log_path = root / "posted_log.yml"
            snapshots: list[tuple[str, list[dict[str, Any]]]] = []
            api = FakeThreadsAPI([{"error": "forced root failure"}])

            with (
                patch(
                    "src.post_daily._save_schedule_checkpoint",
                    side_effect=self.checkpoint_recorder(snapshots),
                ),
                patch("src.post_daily._save_log_checkpoint"),
            ):
                result = post_schedule_item(
                    schedule,
                    item,
                    api=api,
                    sleep_fn=lambda _: None,
                    rng=FixedRng(),
                    log_path=log_path,
                )

            self.assertEqual(result, 1)
            self.assertEqual(len(api.calls), 1)
            self.assertEqual(api.calls[0]["reply_to_id"], "")
            self.assertEqual(item["status"], "error")
            self.assertIn("Root post failed", item["error"])
            self.assertEqual(item.get("threads_post_id", ""), "")
            self.assertEqual(item.get("thread_post_ids", []), [])
            self.assertEqual(item["thread_progress"]["root_post_id"], "")
            self.assertEqual(item["thread_progress"]["reply_ids"], [])
            self.assertEqual(load_yaml(log_path, default=[]), [])
            self.assertTrue(
                any(message == "chore: record Threads root failure" for message, _ in snapshots)
            )

    def test_partial_failure_requires_explicit_resume_and_posts_only_remaining_reply(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.make_item("thread_partial_failure")
            schedule = self.make_schedule(root, item)
            log_path = root / "posted_log.yml"
            first_snapshots: list[tuple[str, list[dict[str, Any]]]] = []
            first_api = FakeThreadsAPI(
                [
                    {"id": "root-001"},
                    {"id": "reply-001"},
                    {"error": "forced second reply failure"},
                ]
            )

            with (
                patch(
                    "src.post_daily._save_schedule_checkpoint",
                    side_effect=self.checkpoint_recorder(first_snapshots),
                ),
                patch("src.post_daily._save_log_checkpoint"),
            ):
                first_result = post_schedule_item(
                    schedule,
                    item,
                    api=first_api,
                    sleep_fn=lambda _: None,
                    rng=FixedRng(),
                    log_path=log_path,
                )

            self.assertEqual(first_result, 1)
            self.assertEqual(len(first_api.calls), 3)
            self.assertEqual(item["status"], "error")
            self.assertIn("Thread reply 2 failed", item["error"])
            self.assertEqual(item["threads_post_id"], "root-001")
            self.assertEqual(item["thread_post_ids"], ["reply-001"])
            self.assertEqual(item["thread_progress"]["root_post_id"], "root-001")
            self.assertEqual(item["thread_progress"]["reply_ids"], ["reply-001"])
            self.assertEqual(item["thread_progress"]["completed_replies"], 1)

            first_log = load_yaml(log_path, default=[])
            self.assertEqual([entry["post_id"] for entry in first_log], ["root-001", "reply-001"])

            candidate_while_error = select_candidate(
                [schedule],
                datetime(2099, 1, 9, 16, 0, tzinfo=timezone.utc),
                timezone.utc,
                post_id=item["id"],
            )
            self.assertIsNone(candidate_while_error)

            item["status"] = "posting"
            candidate_after_explicit_resume = select_candidate(
                [schedule],
                datetime(2099, 1, 9, 16, 0, tzinfo=timezone.utc),
                timezone.utc,
                post_id=item["id"],
            )
            self.assertIsNotNone(candidate_after_explicit_resume)

            resume_snapshots: list[tuple[str, list[dict[str, Any]]]] = []
            resume_api = FakeThreadsAPI([{"id": "reply-002"}])
            with (
                patch(
                    "src.post_daily._save_schedule_checkpoint",
                    side_effect=self.checkpoint_recorder(resume_snapshots),
                ),
                patch("src.post_daily._save_log_checkpoint"),
            ):
                resume_result = post_schedule_item(
                    schedule,
                    item,
                    api=resume_api,
                    sleep_fn=lambda _: None,
                    rng=FixedRng(),
                    log_path=log_path,
                )

            self.assertEqual(resume_result, 0)
            self.assertEqual(len(resume_api.calls), 1)
            self.assertEqual(resume_api.calls[0]["reply_to_id"], "reply-001")
            self.assertEqual(item["status"], "posted")
            self.assertEqual(item["error"], "")
            self.assertEqual(item["threads_post_id"], "root-001")
            self.assertEqual(item["thread_post_ids"], ["reply-001", "reply-002"])
            self.assertEqual(item["thread_progress"]["completed_replies"], 2)
            self.assertEqual(item["thread_count"], 3)

            final_log = load_yaml(log_path, default=[])
            self.assertEqual(
                [entry["post_id"] for entry in final_log],
                ["root-001", "reply-001", "reply-002"],
            )
            self.assertEqual(final_log[1]["reply_to_id"], "root-001")
            self.assertEqual(final_log[2]["reply_to_id"], "reply-001")

            already_posted_api = FakeThreadsAPI([])
            final_result = post_schedule_item(
                schedule,
                item,
                api=already_posted_api,
                sleep_fn=lambda _: None,
                rng=FixedRng(),
                log_path=log_path,
            )
            self.assertEqual(final_result, 0)
            self.assertEqual(already_posted_api.calls, [])
            self.assertEqual(
                [entry["post_id"] for entry in load_yaml(log_path, default=[])],
                ["root-001", "reply-001", "reply-002"],
            )
