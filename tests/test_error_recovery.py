from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from src.error_recovery import classify_error, sanitize_error
from src.github_checkpoint import CheckpointError
from src.post_due import _persist_failure, post_due
from src.schedule_store import ScheduleFile
from src.scheduler import Candidate, select_candidate
from src.threads_api import ThreadsAPI
from src.utils import load_yaml, repo_path, save_yaml


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


class ErrorRecoveryTests(TestCase):
    def make_item(self, item_id: str = "recovery-test") -> dict:
        return {
            "id": item_id,
            "date": "2099-03-02",
            "time_slot": "morning",
            "scheduled_at": "2099-03-02T07:00:00+09:00",
            "publish_after": "2099-03-02T07:00:00+09:00",
            "category": "validation",
            "text": "エラー復旧テスト",
            "status": "ready",
            "threads_post_id": "",
            "thread_post_ids": [],
            "posted_at": "",
            "error": "",
        }

    def make_schedule(self, directory: Path, item: dict) -> ScheduleFile:
        path = directory / "2099-03-02_to_2099-03-08.yml"
        schedule = ScheduleFile(
            path=path,
            start=date(2099, 3, 2),
            end=date(2099, 3, 8),
            entries=[item],
        )
        save_yaml(path, schedule.entries)
        return schedule

    def test_sanitize_error_redacts_known_and_token_shaped_values(self) -> None:
        secret = "threads-secret-token-value"
        github_secret = "github-secret-token-value"
        with patch.dict(
            os.environ,
            {
                "THREADS_ACCESS_TOKEN": secret,
                "GITHUB_TOKEN": github_secret,
            },
            clear=False,
        ):
            result = sanitize_error(
                f"Bearer {secret} access_token={secret} Authorization:{github_secret}"
            )
        self.assertNotIn(secret, result)
        self.assertNotIn(github_secret, result)
        self.assertIn("[REDACTED]", result)

    def test_threads_api_sanitizes_invalid_token_payload(self) -> None:
        secret = "invalid-secret-token-value"
        response = FakeResponse(
            400,
            {
                "error": {
                    "message": f"Invalid OAuth access token {secret}",
                    "type": "OAuthException",
                    "code": 190,
                }
            },
        )
        with (
            patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": secret}, clear=False),
            patch("src.threads_api.requests.request", return_value=response),
        ):
            result = ThreadsAPI(secret, "user-001").get_me()

        self.assertEqual(result["status_code"], 400)
        self.assertEqual(result["error"]["code"], 190)
        self.assertNotIn(secret, str(result))
        self.assertIn("[REDACTED]", result["error"]["message"])

    def test_invalid_and_expired_tokens_are_authentication_errors(self) -> None:
        invalid = {
            "error": {
                "message": "Invalid OAuth access token.",
                "code": 190,
            }
        }
        expired = {
            "error": {
                "message": "Error validating access token: Session has expired.",
                "code": 190,
            }
        }
        self.assertEqual(classify_error(invalid), "authentication")
        self.assertEqual(classify_error(expired), "authentication")

    def test_missing_secret_is_recorded_as_configuration_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.make_item("missing-secret")
            schedule = self.make_schedule(root, item)
            candidate = Candidate(
                schedule_file=schedule,
                item=item,
                publish_after=datetime(2099, 3, 2, 7, tzinfo=timezone.utc),
                scheduled_at=datetime(2099, 3, 2, 7, tzinfo=timezone.utc),
            )

            with (
                patch("src.post_due.configured_threads_enabled", return_value=True),
                patch("src.post_due.load_active_schedule_files", return_value=[schedule]),
                patch("src.post_due.initialize_active_timings", return_value=[schedule]),
                patch("src.post_due.select_candidate", return_value=candidate),
                patch("src.post_due.validate_post_item_texts", return_value=[]),
                patch(
                    "src.post_due.post_schedule_item",
                    side_effect=RuntimeError(
                        "Required environment variable is missing: THREADS_ACCESS_TOKEN"
                    ),
                ),
                patch("src.post_due.checkpoint_file"),
            ):
                result = post_due(post_id=item["id"])

            self.assertEqual(result, 1)
            self.assertEqual(item["status"], "error")
            self.assertEqual(item["error_kind"], "configuration")
            self.assertIn("THREADS_ACCESS_TOKEN", item["error"])
            self.assertIn("GitHub Secret", item["recovery_action"])
            self.assertEqual(item["threads_post_id"], "")
            saved = load_yaml(schedule.path, default=[])
            self.assertEqual(saved[0]["error_kind"], "configuration")

    def test_invalid_token_metadata_is_persisted_without_secret(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.make_item("invalid-token")
            schedule = self.make_schedule(root, item)
            secret = "should-never-be-recorded"
            error = {
                "error": {
                    "message": f"Invalid OAuth access token {secret}",
                    "code": 190,
                }
            }

            with (
                patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": secret}, clear=False),
                patch("src.post_due.checkpoint_file"),
            ):
                kind = _persist_failure(schedule, item, error)

            self.assertEqual(kind, "authentication")
            self.assertEqual(item["error_code"], "190")
            self.assertNotIn(secret, item["error"])
            self.assertIn("Threads token", item["recovery_action"])

    def test_image_url_failure_is_classified_and_not_logged_as_posted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.make_item("image-url-error")
            item["image_url"] = "https://example.invalid/missing.webp"
            schedule = self.make_schedule(root, item)
            error = {
                "error": {
                    "message": "The image URL could not be downloaded.",
                    "code": 100,
                }
            }

            with patch("src.post_due.checkpoint_file"):
                kind = _persist_failure(schedule, item, error)

            self.assertEqual(kind, "image_url")
            self.assertEqual(item["status"], "error")
            self.assertIn("public", item["recovery_action"])
            self.assertEqual(item["threads_post_id"], "")

            log_path = root / "posted_log.yml"
            self.assertEqual(load_yaml(log_path, default=[]), [])

            candidate = select_candidate(
                [schedule],
                datetime(2099, 3, 2, 8, tzinfo=timezone.utc),
                timezone.utc,
                post_id=item["id"],
            )
            self.assertIsNone(candidate)

    def test_checkpoint_failure_logs_reconciliation_ids_and_saves_snapshot(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.make_item("checkpoint-error")
            schedule = self.make_schedule(root, item)
            candidate = Candidate(
                schedule_file=schedule,
                item=item,
                publish_after=datetime(2099, 3, 2, 7, tzinfo=timezone.utc),
                scheduled_at=datetime(2099, 3, 2, 7, tzinfo=timezone.utc),
            )

            def fail_after_post(*args, **kwargs):
                item["status"] = "posting"
                item["threads_post_id"] = "root-recovery-001"
                item["thread_post_ids"] = ["reply-recovery-001"]
                raise CheckpointError("Could not save checkpoint (HTTP 500).")

            output = io.StringIO()
            with (
                patch("src.post_due.configured_threads_enabled", return_value=True),
                patch("src.post_due.load_active_schedule_files", return_value=[schedule]),
                patch("src.post_due.initialize_active_timings", return_value=[schedule]),
                patch("src.post_due.select_candidate", return_value=candidate),
                patch("src.post_due.validate_post_item_texts", return_value=[]),
                patch("src.post_due.post_schedule_item", side_effect=fail_after_post),
                redirect_stdout(output),
                self.assertRaises(CheckpointError),
            ):
                post_due(post_id=item["id"])

            log = output.getvalue()
            self.assertIn("CRITICAL_CHECKPOINT_FAILURE", log)
            self.assertIn("root_post_id=root-recovery-001", log)
            self.assertIn("reply_post_ids=reply-recovery-001", log)
            self.assertIn("Do not rerun", log)

            saved = load_yaml(schedule.path, default=[])[0]
            self.assertEqual(saved["threads_post_id"], "root-recovery-001")
            self.assertEqual(saved["thread_post_ids"], ["reply-recovery-001"])
            self.assertIn("recovery artifact", saved["recovery_action"])

    def test_posting_workflow_keeps_failure_snapshot_and_warning(self) -> None:
        workflow = repo_path(".github", "workflows", "post-due.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Upload failure recovery snapshot", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("posts/schedules/*.yml", workflow)
        self.assertIn("posts/posted_log.yml", workflow)
        self.assertIn("Do not rerun the failed post", workflow)
        self.assertIn("Do not place authentication values in this issue", workflow)
