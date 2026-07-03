"""Persist critical posting state directly to GitHub during Actions runs."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from urllib.parse import quote

import requests

from .utils import REPO_ROOT, optional_env, require_env


class CheckpointError(RuntimeError):
    """Raised when posting state could not be persisted to GitHub."""


def checkpoint_enabled() -> bool:
    """Return true only inside GitHub Actions with checkpointing enabled."""
    return (
        optional_env("GITHUB_ACTIONS").lower() == "true"
        and optional_env("ENABLE_GITHUB_CHECKPOINTS", "true").lower()
        in {"1", "true", "yes", "on"}
    )


def checkpoint_file(path: Path, message: str, retries: int = 3) -> None:
    """Commit one local file through the GitHub Contents API.

    Outside GitHub Actions this is intentionally a no-op so local tests and
    development do not require repository credentials.
    """
    if not checkpoint_enabled():
        return

    token = require_env("GITHUB_TOKEN")
    repository = require_env("GITHUB_REPOSITORY")
    branch = optional_env("GITHUB_REF_NAME", "main") or "main"

    resolved = path.resolve()
    try:
        relative_path = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise CheckpointError("Checkpoint path is outside the repository.") from exc

    url = (
        f"https://api.github.com/repos/{repository}/contents/"
        f"{quote(relative_path, safe='/')}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    encoded_content = base64.b64encode(path.read_bytes()).decode("ascii")
    last_status = 0

    for attempt in range(1, retries + 1):
        current = requests.get(
            url,
            headers=headers,
            params={"ref": branch},
            timeout=30,
        )
        if current.status_code == 200:
            current_sha = str(current.json().get("sha", "")).strip()
            if not current_sha:
                raise CheckpointError(
                    f"GitHub returned no file SHA for {relative_path}."
                )
        elif current.status_code == 404:
            current_sha = ""
        else:
            raise CheckpointError(
                f"Could not read checkpoint target {relative_path} "
                f"(HTTP {current.status_code})."
            )

        payload: dict[str, str] = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if current_sha:
            payload["sha"] = current_sha

        result = requests.put(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        last_status = result.status_code
        if result.status_code in {200, 201}:
            print(f"Checkpoint saved: {relative_path}")
            return

        if result.status_code in {409, 422} and attempt < retries:
            time.sleep(attempt)
            continue
        break

    raise CheckpointError(
        f"Could not save checkpoint {relative_path} (HTTP {last_status})."
    )
