"""Validate configuration and posting data without using any secrets."""
from __future__ import annotations

import re
from typing import Any

from .config_loader import get_config, service_timezone
from .schedule_store import load_active_schedule_files

TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_STATUSES = {"draft", "ready", "posted", "error", "cancelled"}


def validate_config() -> list[str]:
    errors: list[str] = []
    try:
        service_timezone()
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    slots: Any = get_config("posting", "time_slots", default={})
    if not isinstance(slots, dict) or not slots:
        errors.append("posting.time_slots must contain at least one slot.")
    else:
        for name, value in slots.items():
            if not str(name).strip():
                errors.append("A time slot has an empty name.")
            if not TIME_RE.match(str(value)):
                errors.append(f"Invalid time for slot {name}: {value}")
    return errors


def validate_schedules() -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    configured_slots = get_config("posting", "time_slots", default={})
    slot_names = set(configured_slots) if isinstance(configured_slots, dict) else set()

    for schedule_file in load_active_schedule_files(include_past=True):
        for index, item in enumerate(schedule_file.entries, start=1):
            location = f"{schedule_file.path}:{index}"
            if not isinstance(item, dict):
                errors.append(f"{location} must be a YAML mapping.")
                continue

            item_id = str(item.get("id", "")).strip()
            if item_id:
                if item_id in ids:
                    errors.append(f"Duplicate post id: {item_id}")
                ids.add(item_id)

            date = str(item.get("date", "")).strip()
            if not DATE_RE.match(date):
                errors.append(f"{location} has invalid date: {date}")

            slot = str(item.get("time_slot", "")).strip()
            if slot not in slot_names:
                errors.append(f"{location} uses undefined time_slot: {slot}")

            status = str(item.get("status", "")).lower().strip()
            if status not in ALLOWED_STATUSES:
                errors.append(f"{location} has invalid status: {status}")

            text = str(item.get("text", "")).strip()
            if not text:
                errors.append(f"{location} has no text.")

            if status == "ready":
                image_key = str(item.get("image_key", "")).strip()
                image_url = str(item.get("image_url", "")).strip()
                if image_key and not image_url:
                    errors.append(f"{location} is ready but image_url is empty.")

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
                            if reply_key and not reply_url:
                                errors.append(
                                    f"{location} reply {reply_index} has no image_url."
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
