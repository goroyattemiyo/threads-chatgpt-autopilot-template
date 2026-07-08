from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from src.image_delivery_preflight import (
    ImageDeliveryError,
    preflight_image_delivery,
    validate_local_configuration,
    validate_remote_repository,
)
from src.utils import repo_path


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class ImageDeliveryRecoveryTests(TestCase):
    def test_disabled_processing_skips_token_repository_and_network(self) -> None:
        request_get = Mock(side_effect=AssertionError("network must not be called"))
        result = preflight_image_delivery(
            enabled=False,
            repository="",
            branch="",
            token="",
            request_get=request_get,
        )
        self.assertFalse(result.enabled)
        request_get.assert_not_called()

    def test_missing_token_is_configuration_error_before_network(self) -> None:
        request_get = Mock(side_effect=AssertionError("network must not be called"))
        with self.assertRaises(ImageDeliveryError) as context:
            preflight_image_delivery(
                enabled=True,
                repository="owner/assets",
                branch="main",
                token="",
                request_get=request_get,
            )
        self.assertEqual(context.exception.kind, "assets_configuration")
        self.assertIn("ASSETS_REPO_TOKEN", str(context.exception))
        request_get.assert_not_called()

    def test_missing_and_invalid_repository_are_configuration_errors(self) -> None:
        cases = (
            ("", "both empty"),
            ("owner-only", "owner/repository"),
            ("owner/repo/extra", "owner/repository"),
        )
        for repository, message in cases:
            with self.subTest(repository=repository):
                with self.assertRaises(ImageDeliveryError) as context:
                    validate_local_configuration(
                        repository=repository,
                        branch="main",
                        token="dummy-token",
                    )
                self.assertEqual(context.exception.kind, "assets_configuration")
                self.assertIn(message, str(context.exception))

    def test_repository_404_is_classified_without_response_body(self) -> None:
        with self.assertRaises(ImageDeliveryError) as context:
            validate_remote_repository(
                repository="owner/does-not-exist",
                token="dummy-token",
                request_get=Mock(return_value=FakeResponse(404)),
            )
        self.assertEqual(context.exception.kind, "assets_repository_not_found")
        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("not found", str(context.exception))

    def test_repository_401_and_403_are_authentication_errors(self) -> None:
        for status_code in (401, 403):
            with self.subTest(status_code=status_code):
                with self.assertRaises(ImageDeliveryError) as context:
                    validate_remote_repository(
                        repository="owner/assets",
                        token="dummy-token",
                        request_get=Mock(return_value=FakeResponse(status_code)),
                    )
                self.assertEqual(context.exception.kind, "assets_authentication")
                self.assertEqual(context.exception.status_code, status_code)

    def test_request_error_redacts_token_value(self) -> None:
        secret = "image-secret-value-never-log"
        error = requests.RequestException(
            f"Authorization: {secret} access_token={secret}"
        )
        with (
            patch.dict(os.environ, {"ASSETS_REPO_TOKEN": secret}, clear=False),
            self.assertRaises(ImageDeliveryError) as context,
        ):
            validate_remote_repository(
                repository="owner/assets",
                token=secret,
                request_get=Mock(side_effect=error),
            )
        message = str(context.exception)
        self.assertNotIn(secret, message)
        self.assertIn("[REDACTED]", message)

    def test_preflight_failure_does_not_modify_local_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming.png"
            schedule = root / "schedule.yml"
            log = root / "assets.yml"
            incoming.write_bytes(b"original-image-bytes")
            schedule.write_text("status: draft\n", encoding="utf-8")
            log.write_text("[]\n", encoding="utf-8")
            before = {
                path.name: path.read_bytes()
                for path in (incoming, schedule, log)
            }

            with self.assertRaises(ImageDeliveryError):
                preflight_image_delivery(
                    enabled=True,
                    repository="owner/assets",
                    branch="main",
                    token="",
                )

            after = {
                path.name: path.read_bytes()
                for path in (incoming, schedule, log)
            }
            self.assertEqual(after, before)

    def test_workflow_runs_preflight_before_checkout_and_conversion(self) -> None:
        workflow = repo_path(".github", "workflows", "process-images.yml").read_text(
            encoding="utf-8"
        )
        preflight_position = workflow.index("Validate image repository access")
        checkout_position = workflow.index("Checkout public assets repository")
        conversion_position = workflow.index("Convert images and update schedules")
        self.assertLess(preflight_position, checkout_position)
        self.assertLess(preflight_position, conversion_position)
        self.assertIn("steps.image_preflight.outputs.enabled == 'true'", workflow)
        self.assertIn("steps.image_preflight.outputs.repository", workflow)
        self.assertIn("Do not paste the token value", workflow)
        self.assertNotIn("ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION", workflow)
