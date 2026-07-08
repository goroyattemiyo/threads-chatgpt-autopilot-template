"""Error classification, redaction, and recovery guidance for posting failures."""
from __future__ import annotations

import re
from typing import Any

from .utils import optional_env, timestamp_local

_SECRET_ENV_NAMES = (
    "THREADS_ACCESS_TOKEN",
    "ASSETS_REPO_TOKEN",
    "GITHUB_TOKEN",
)

_RECOVERY_ACTIONS = {
    "configuration": (
        "Register the named GitHub Secret yourself, then change the item from "
        "error to ready and rerun the exact post_id."
    ),
    "authentication": (
        "Refresh or reissue the Threads token yourself, update the GitHub Secret, "
        "then change the item from error to ready and rerun the exact post_id."
    ),
    "image_url": (
        "Confirm the image URL is public and returns an image without authentication, "
        "replace it if needed, then change the item from error to ready and rerun the exact post_id."
    ),
    "checkpoint": (
        "Do not rerun. Compare Threads with the Actions log and recovery artifact, "
        "restore any posted IDs to the schedule, then resume only the unfinished part."
    ),
    "api": (
        "Review the sanitized API error and the Threads account status. Do not rerun "
        "until the cause and whether a post was created are confirmed."
    ),
}


def sanitize_error(value: Any) -> str:
    """Return a bounded error string with known and token-shaped values redacted."""
    text = str(value)
    for name in _SECRET_ENV_NAMES:
        secret = optional_env(name)
        if secret:
            text = text.replace(secret, "[REDACTED]")

    text = re.sub(
        r"(?i)(bearer)\s+[A-Za-z0-9._~+\-/=]+",
        r"\1 [REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)(access[_-]?token|authorization|token)\s*([:=])\s*"
        r"(['\"]?)[^\s,;\}\]'\"]+\3",
        r"\1\2[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)(access_token=)[^&\s]+",
        r"\1[REDACTED]",
        text,
    )
    return text[:500]


def sanitize_error_value(value: Any) -> Any:
    """Recursively sanitize an API error payload without changing its shape."""
    if isinstance(value, dict):
        return {str(key): sanitize_error_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_error_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_error_value(item) for item in value)
    if isinstance(value, str):
        return sanitize_error(value)
    return value


def _nested_error(value: Any) -> Any:
    if isinstance(value, dict) and "error" in value:
        return value.get("error")
    return value


def error_code(value: Any) -> str:
    error = _nested_error(value)
    if isinstance(error, dict):
        code = error.get("code", "")
        return str(code) if code not in (None, "") else ""
    match = re.search(r"['\"]?code['\"]?\s*[:=]\s*['\"]?(\d+)", str(error))
    return match.group(1) if match else ""


def error_message(value: Any) -> str:
    error = _nested_error(value)
    if isinstance(error, dict):
        message = error.get("message") or error.get("error_user_msg") or error
        return sanitize_error(message)
    return sanitize_error(error)


def classify_error(value: Any, *, has_image: bool = False) -> str:
    """Classify an error into an operator-facing recovery category."""
    code = error_code(value)
    message = error_message(value).casefold()

    if "required environment variable is missing" in message:
        return "configuration"
    if code == "190" or any(
        phrase in message
        for phrase in (
            "oauth",
            "access token",
            "token has expired",
            "session has expired",
            "invalid token",
            "error validating access token",
        )
    ):
        return "authentication"
    if has_image and any(
        phrase in message
        for phrase in (
            "image url",
            "image_url",
            "could not be downloaded",
            "failed to download",
            "unsupported image",
            "media url",
            "invalid url",
        )
    ):
        return "image_url"
    return "api"


def recovery_action(kind: str) -> str:
    return _RECOVERY_ACTIONS.get(kind, _RECOVERY_ACTIONS["api"])


def apply_error_metadata(
    item: dict[str, Any],
    value: Any,
    *,
    has_image: bool = False,
    kind_override: str = "",
) -> str:
    """Store sanitized error metadata and return the selected error kind."""
    kind = kind_override or classify_error(value, has_image=has_image)
    code = error_code(value)
    item["status"] = "error"
    item["error"] = error_message(value)
    item["error_kind"] = kind
    if code:
        item["error_code"] = code
    else:
        item.pop("error_code", None)
    item["error_at"] = timestamp_local()
    item["recovery_action"] = recovery_action(kind)
    return kind


def clear_error_metadata(item: dict[str, Any]) -> bool:
    """Remove stale recovery metadata after a successful retry."""
    changed = False
    for key in (
        "error_kind",
        "error_code",
        "error_at",
        "recovery_action",
        "checkpoint_error",
        "checkpoint_failed_at",
    ):
        if key in item:
            item.pop(key, None)
            changed = True
    return changed
