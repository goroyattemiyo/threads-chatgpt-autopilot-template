"""Validate image repository configuration before checkout or file conversion."""
from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

from .config_loader import get_config
from .error_recovery import sanitize_error
from .utils import optional_env

REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")
GITHUB_API = "https://api.github.com"


class ImageDeliveryError(RuntimeError):
    """A safe, operator-facing image repository preflight failure."""

    def __init__(self, kind: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


@dataclass(frozen=True)
class ImageDeliveryConfig:
    enabled: bool
    repository: str = ""
    branch: str = "main"


def configured_images_enabled() -> bool:
    value: Any = get_config("posting", "enable_images", default=False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def configured_repository() -> str:
    configured = str(get_config("assets", "repository", default="")).strip()
    environment = optional_env("ASSETS_REPO_FULL_NAME")
    return environment or configured


def configured_branch() -> str:
    configured = str(get_config("assets", "branch", default="main")).strip() or "main"
    environment = optional_env("ASSETS_REPO_BRANCH")
    return environment or configured


def _validate_branch(branch: str) -> None:
    if (
        not BRANCH_PATTERN.fullmatch(branch)
        or branch.startswith("/")
        or branch.endswith("/")
        or ".." in branch.split("/")
    ):
        raise ImageDeliveryError(
            "assets_configuration",
            "ASSETS_REPO_BRANCH is invalid.",
        )


def validate_local_configuration(
    *,
    repository: str,
    branch: str,
    token: str,
) -> None:
    if not token:
        raise ImageDeliveryError(
            "assets_configuration",
            "ASSETS_REPO_TOKEN is not configured in GitHub Secrets.",
        )
    if not repository:
        raise ImageDeliveryError(
            "assets_configuration",
            "ASSETS_REPO_FULL_NAME and assets.repository are both empty.",
        )
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ImageDeliveryError(
            "assets_configuration",
            "The image repository must use owner/repository format.",
        )
    _validate_branch(branch)


def validate_remote_repository(
    *,
    repository: str,
    token: str,
    request_get: Callable[..., Any] = requests.get,
) -> None:
    encoded_repository = quote(repository, safe="/")
    url = f"{GITHUB_API}/repos/{encoded_repository}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        response = request_get(url, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise ImageDeliveryError(
            "assets_api",
            f"Could not verify the image repository: {sanitize_error(exc)}",
        ) from exc

    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code == 200:
        return
    if status_code in {401, 403}:
        raise ImageDeliveryError(
            "assets_authentication",
            "The image repository token is invalid, expired, or lacks required access.",
            status_code=status_code,
        )
    if status_code == 404:
        raise ImageDeliveryError(
            "assets_repository_not_found",
            "The image repository was not found, or the token cannot access it.",
            status_code=status_code,
        )
    raise ImageDeliveryError(
        "assets_api",
        f"GitHub repository verification failed with HTTP {status_code or 'unknown'}.",
        status_code=status_code or None,
    )


def preflight_image_delivery(
    *,
    enabled: bool | None = None,
    repository: str | None = None,
    branch: str | None = None,
    token: str | None = None,
    request_get: Callable[..., Any] = requests.get,
) -> ImageDeliveryConfig:
    is_enabled = configured_images_enabled() if enabled is None else enabled
    if not is_enabled:
        return ImageDeliveryConfig(enabled=False)

    selected_repository = configured_repository() if repository is None else repository.strip()
    selected_branch = configured_branch() if branch is None else branch.strip()
    selected_token = optional_env("ASSETS_REPO_TOKEN") if token is None else token

    validate_local_configuration(
        repository=selected_repository,
        branch=selected_branch,
        token=selected_token,
    )
    validate_remote_repository(
        repository=selected_repository,
        token=selected_token,
        request_get=request_get,
    )
    return ImageDeliveryConfig(
        enabled=True,
        repository=selected_repository,
        branch=selected_branch,
    )


def _write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def run_preflight() -> int:
    try:
        result = preflight_image_delivery()
    except ImageDeliveryError as exc:
        _write_output("enabled", "true")
        _write_output("error_kind", exc.kind)
        if exc.status_code is not None:
            _write_output("status_code", str(exc.status_code))
        print(
            "IMAGE_DELIVERY_ERROR "
            f"kind={exc.kind} message={sanitize_error(exc)}"
        )
        print("Do not paste ASSETS_REPO_TOKEN into logs, Issues, chat, or email.")
        return 1

    if not result.enabled:
        _write_output("enabled", "false")
        print("Image processing is disabled. Repository checkout was not started.")
        return 0

    _write_output("enabled", "true")
    _write_output("repository", result.repository)
    _write_output("branch", result.branch)
    print(
        "IMAGE_DELIVERY_PREFLIGHT_OK "
        f"repository={result.repository} branch={result.branch}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    raise SystemExit(run_preflight())


if __name__ == "__main__":
    main()
