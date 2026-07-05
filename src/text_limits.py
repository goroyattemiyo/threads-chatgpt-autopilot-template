"""Shared Threads text-length checks used before API posting."""
from __future__ import annotations

from typing import Any

MAX_TEXT_CHARACTERS = 500


def _length_error(text: str, label: str) -> str | None:
    length = len(text)
    if length <= MAX_TEXT_CHARACTERS:
        return None
    return (
        f"{label} exceeds the Threads text limit: "
        f"{length}/{MAX_TEXT_CHARACTERS} characters."
    )


def validate_post_item_texts(item: dict[str, Any]) -> list[str]:
    """Return root/reply text-length errors without mutating the item."""
    errors: list[str] = []

    root_text = str(item.get("text", "")).strip()
    if root_text:
        error = _length_error(root_text, "root text")
        if error:
            errors.append(error)

    raw_replies = item.get("thread_posts", [])
    if not isinstance(raw_replies, list):
        return errors

    for index, reply in enumerate(raw_replies, start=1):
        if isinstance(reply, str):
            reply_text = reply.strip()
        elif isinstance(reply, dict):
            reply_text = str(reply.get("text", "")).strip()
        else:
            continue
        if not reply_text:
            continue
        error = _length_error(reply_text, f"thread reply {index} text")
        if error:
            errors.append(error)

    return errors
