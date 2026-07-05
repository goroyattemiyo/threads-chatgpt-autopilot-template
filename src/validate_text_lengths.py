"""Validate root and thread reply text against the tested Threads limit."""
from __future__ import annotations

from typing import Any

from .schedule_store import load_active_schedule_files

MAX_TEXT_CHARACTERS = 500


def text_length_error(text: str, label: str) -> str | None:
    length = len(text)
    if length <= MAX_TEXT_CHARACTERS:
        return None
    return (
        f"{label} exceeds the Threads text limit: "
        f"{length}/{MAX_TEXT_CHARACTERS} characters."
    )


def validate_text_lengths() -> list[str]:
    errors: list[str] = []
    for schedule_file in load_active_schedule_files(include_past=True):
        for index, item in enumerate(schedule_file.entries, start=1):
            if not isinstance(item, dict):
                continue
            location = f"{schedule_file.path}:{index}"
            text = str(item.get("text", "")).strip()
            if text:
                error = text_length_error(text, f"{location} text")
                if error:
                    errors.append(error)

            thread_posts: Any = item.get("thread_posts", [])
            if not isinstance(thread_posts, list):
                continue
            for reply_index, reply in enumerate(thread_posts, start=1):
                if isinstance(reply, str):
                    reply_text = reply.strip()
                elif isinstance(reply, dict):
                    reply_text = str(reply.get("text", "")).strip()
                else:
                    continue
                if not reply_text:
                    continue
                error = text_length_error(
                    reply_text,
                    f"{location} thread_posts[{reply_index}] text",
                )
                if error:
                    errors.append(error)
    return errors


def main() -> None:
    errors = validate_text_lengths()
    if errors:
        print("Threads text length validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Threads text length validation passed.")


if __name__ == "__main__":
    main()
