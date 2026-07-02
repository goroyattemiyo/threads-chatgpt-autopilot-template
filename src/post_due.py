"""Publish posts whose configured time slot is currently due."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Any

from .config_loader import get_config
from .post_daily import post_daily
from .utils import now_local


def configured_slots() -> dict[str, str]:
    raw: Any = get_config("posting", "time_slots", default={})
    if not isinstance(raw, dict) or not raw:
        raise ValueError("posting.time_slots must contain at least one slot.")
    return {str(name): str(value) for name, value in raw.items()}


def configured_window_minutes() -> int:
    value = int(get_config("posting", "due_window_minutes", default=30))
    if value < 1 or value > 120:
        raise ValueError("posting.due_window_minutes must be between 1 and 120.")
    return value


def parse_slot_time(base: datetime, value: str) -> datetime:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid time slot value: {value}. Use HH:MM.") from exc

    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"Invalid time slot value: {value}. Use HH:MM.")
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def due_targets(now: datetime, window_minutes: int) -> list[tuple[str, str]]:
    if window_minutes < 1 or window_minutes > 120:
        raise ValueError("window_minutes must be between 1 and 120.")

    results: list[tuple[str, str]] = []
    window = timedelta(minutes=window_minutes)

    # Check both today and yesterday so a late 23:xx run can be recovered after midnight.
    for day_offset in (0, -1):
        base = now + timedelta(days=day_offset)
        for slot_name, slot_value in configured_slots().items():
            scheduled = parse_slot_time(base, slot_value)
            if scheduled <= now < scheduled + window:
                results.append((scheduled.strftime("%Y-%m-%d"), slot_name))
    return results


def post_due(
    dry_run: bool = False,
    window_minutes: int | None = None,
) -> int:
    now = now_local()
    effective_window = (
        configured_window_minutes()
        if window_minutes is None
        else window_minutes
    )
    targets = due_targets(now, effective_window)
    if not targets:
        print(f"No due slots at {now.isoformat(timespec='minutes')}.")
        return 0

    failures = 0
    for date, slot in targets:
        print(f"Checking due slot: {date} {slot}")
        result = post_daily(date, slot, dry_run=dry_run)
        if result != 0:
            failures += 1
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--window-minutes", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(
        post_due(
            dry_run=args.dry_run,
            window_minutes=args.window_minutes,
        )
    )


if __name__ == "__main__":
    main()
