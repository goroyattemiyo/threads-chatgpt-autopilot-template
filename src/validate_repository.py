"""Validate configuration and posting data without using any secrets."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config_loader import get_config, service_timezone
from .schedule_store import load_active_schedule_files
from .scheduler import (
    LEGACY_SLOT_TIMES,
    delay_bounds,
    legacy_scheduled_at,
    parse_datetime,
    thread_delay_bounds,
)

ALLOWED_STATUSES = {"draft", "ready", "posting", "posted", "error", "cancelled"}


def _aware_iso(value: Any, label: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return f"{label} is not valid ISO 8601: {raw}"
    if parsed.tzinfo is None:
        return f"{label} must include a UTC offset: {raw}"
    return None


def validate_config() -> list[str]:
    errors: list[str] = []
    try:
        service_timezone()
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    slots: Any = get_config("posting", "time_slots", default={})
    if not isinstance(slots, dict):
        errors.append("posting.time_slots must be a mapping.")
    else:
        for name, required_time in LEGACY_SLOT_TIMES.items():
            if str(slots.get(name, "")) != required_time:
                errors.append(
                    f"posting.time_slots.{name} must be {required_time} for backward compatibility."
                )

    for minimum_key, maximum_key, default_min, default_max, upper in (
        ("default_delay_min_minutes", "default_delay_max_minutes", 2, 14, 1440),
        (
            "default_thread_delay_min_seconds",
            "default_thread_delay_max_seconds",
            8,
            25,
            3600,
        ),
    ):
        try:
            minimum = int(get_config("posting", minimum_key, default=default_min))
            maximum = int(get_config("posting", maximum_key, default=default_max))
            if minimum < 0 or maximum < minimum or maximum > upper:
                errors.append(
                    f"posting {minimum_key}/{maximum_key} must satisfy 0 <= min <= max <= {upper}."
                )
        except (TypeError, ValueError):
            errors.append(f"posting {minimum_key}/{maximum_key} must be integers.")
    return errors


def validate_schedules() -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    timezone = service_timezone()

    for schedule_file in load_active_schedule_files(include_past=True):
        for index, item in enumerate(schedule_file.entries, start=1):
            location = f"{schedule_file.path}:{index}"
            if not isinstance(item, dict):
                errors.append(f"{location} must be a YAML mapping.")
                continue

            item_id = str(item.get("id", "")).strip()
            if not item_id:
                errors.append(f"{location} has no id.")
            elif item_id in ids:
                errors.append(f"Duplicate post id: {item_id}")
            ids.add(item_id)

            status = str(item.get("status", "")).lower().strip()
            if status not in ALLOWED_STATUSES:
                errors.append(f"{location} has invalid status: {status}")

            text = str(item.get("text", "")).strip()
            if not text:
                errors.append(f"{location} has no text.")

            scheduled_raw = str(item.get("scheduled_at", "")).strip()
            if scheduled_raw:
                error = _aware_iso(scheduled_raw, f"{location} scheduled_at")
                if error:
                    errors.append(error)
            elif status in {"ready", "posting", "posted", "error"}:
                try:
                    legacy_scheduled_at(item, timezone)
                except ValueError as exc:
                    errors.append(f"{location}: {exc}")

            publish_raw = str(item.get("publish_after", "")).strip()
            if publish_raw:
                error = _aware_iso(publish_raw, f"{location} publish_after")
                if error:
                    errors.append(error)

            try:
                minimum, maximum = delay_bounds(item)
                if item.get("delay_minutes") not in (None, ""):
                    delay = int(item["delay_minutes"])
                    if delay < 0:
                        errors.append(f"{location} delay_minutes must be zero or greater.")
                    if publish_raw and scheduled_raw:
                        scheduled = parse_datetime(scheduled_raw, timezone)
                        publish_after = parse_datetime(publish_raw, timezone)
                        expected_seconds = delay * 60
                        actual_seconds = int((publish_after - scheduled).total_seconds())
                        if actual_seconds != expected_seconds:
                            errors.append(
                                f"{location} publish_after does not match delay_minutes."
                            )
                    if delay < minimum or delay > maximum:
                        errors.append(
                            f"{location} delay_minutes is outside delay_min/max bounds."
                        )
            except (TypeError, ValueError) as exc:
                errors.append(f"{location}: {exc}")

            try:
                thread_delay_bounds(item)
            except ValueError as exc:
                errors.append(f"{location}: {exc}")

            if status in {"ready", "posting"}:
                image_key = str(item.get("image_key", "")).strip()
                image_url = str(item.get("image_url", "")).strip()
                if image_key and not image_url:
                    errors.append(f"{location} is ready/posting but image_url is empty.")

            thread_posts = item.get("thread_posts", [])
            if thread_posts and not isinstance(thread_posts, list):
                errors.append(f"{location} thread_posts must be a list.")
            elif isinstance(thread_posts, list):
                for reply_index, reply in enumerate(thread_posts, start=1):
                    if not isinstance(reply, (dict, str)):
                        errors.append(
                            f"{location} thread_posts[{reply_index}] is invalid."
                        )
                        continue
                    if isinstance(reply, dict):
                        reply_key = str(reply.get("image_key", "")).strip()
                        reply_url = str(reply.get("image_url", "")).strip()
                        if status in {"ready", "posting"} and reply_key and not reply_url:
                            errors.append(
                                f"{location} reply {reply_index} has no image_url."
                            )

            progress = item.get("thread_progress")
            if progress is not None and not isinstance(progress, dict):
                errors.append(f"{location} thread_progress must be a mapping.")
            elif isinstance(progress, dict):
                reply_ids = progress.get("reply_ids", [])
                completed = progress.get("completed_replies", 0)
                if not isinstance(reply_ids, list):
                    errors.append(f"{location} thread_progress.reply_ids must be a list.")
                try:
                    completed_int = int(completed)
                    if isinstance(reply_ids, list) and completed_int < len(reply_ids):
                        errors.append(
                            f"{location} completed_replies is smaller than reply_ids."
                        )
                except (TypeError, ValueError):
                    errors.append(
                        f"{location} thread_progress.completed_replies must be an integer."
                    )
    return errors


def main() -> None:
    errors = validate_config() + validate_schedules()
    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Repository validation passed.")


if __name__ == "__main__":
    main()
