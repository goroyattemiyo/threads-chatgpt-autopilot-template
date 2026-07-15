from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src import post_due


class AccountSafetyLockTests(unittest.TestCase):
    @patch("src.post_due.get_config", return_value=True)
    def test_configured_lock_accepts_boolean_true(self, get_config_mock) -> None:
        self.assertTrue(post_due.configured_account_safety_locked())
        get_config_mock.assert_called_once_with(
            "account_safety", "posting_locked", default=False
        )

    @patch("src.post_due.get_config", return_value=" off ")
    def test_configured_lock_parses_false_string(self, _get_config_mock) -> None:
        self.assertFalse(post_due.configured_account_safety_locked())

    @patch("src.post_due.get_config", return_value=" account review ")
    def test_lock_reason_is_trimmed(self, _get_config_mock) -> None:
        self.assertEqual(post_due.account_safety_lock_reason(), "account review")

    @patch("src.post_due.configured_account_safety_locked", return_value=True)
    @patch("src.post_due.account_safety_lock_reason", return_value="account review")
    @patch("src.post_due.configured_threads_enabled")
    @patch("src.post_due.load_active_schedule_files")
    def test_live_post_stops_before_schedule_or_api_work(
        self,
        load_active_schedule_files_mock,
        configured_threads_enabled_mock,
        _lock_reason_mock,
        _safety_locked_mock,
    ) -> None:
        with patch("builtins.print") as print_mock:
            result = post_due.post_due(dry_run=False)

        self.assertEqual(result, 0)
        load_active_schedule_files_mock.assert_not_called()
        configured_threads_enabled_mock.assert_not_called()
        output = "\n".join(
            " ".join(str(part) for part in call.args)
            for call in print_mock.call_args_list
        )
        self.assertIn("account_safety.posting_locked", output)
        self.assertIn("account review", output)

    @patch("src.post_due.configured_account_safety_locked", return_value=True)
    @patch("src.post_due.service_timezone", return_value=timezone.utc)
    @patch(
        "src.post_due.now_local",
        return_value=datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    )
    @patch("src.post_due.load_active_schedule_files", return_value=[])
    @patch("src.post_due.initialize_active_timings", return_value=[])
    @patch("src.post_due.select_candidate", return_value=None)
    def test_dry_run_remains_available_while_locked(
        self,
        _select_candidate_mock,
        _initialize_active_timings_mock,
        load_active_schedule_files_mock,
        _now_local_mock,
        _service_timezone_mock,
        safety_locked_mock,
    ) -> None:
        result = post_due.post_due(dry_run=True)

        self.assertEqual(result, 0)
        safety_locked_mock.assert_not_called()
        load_active_schedule_files_mock.assert_called_once_with(include_past=True)


if __name__ == "__main__":
    unittest.main()
