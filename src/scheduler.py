"""Minute-level scheduling and stable candidate selection."""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Protocol
from zoneinfo import ZoneInfo

from .config_loader import get_config
from .schedule_store import ScheduleFile

LEGACY_SLOT_TIMES: dict[str, str] = {
    "morning": "07:00",
    "noon": "12:00",
    "afternoon": "15:00",
    "evening": "17:00",
    "night": "20:00",
    "summary": "21:00",
}
ACTIVE_STATUSES = {"ready", "posting"}


class RandomLike(Protocol):
    def randint(self, a: int, b: int) -> int: ...


@dataclass(frozen=True)
class Candidate:
    schedule_file: ScheduleFile
    item: dict[str, Any]
    publish_after: datetime
    scheduled_at: datetime


def parse_datetime(value: Any, timezone: ZoneInfo) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("datetime value is empty.")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO 8601 datetime: {raw}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def legacy_scheduled_at(item: dict[str, Any], timezone: ZoneInfo) -> datetime:
    date_text = str(item.get("date", "")).strip()
    slot_name = str(item.get("time_slot", "")).strip()
    if not date_text:
        raise ValueError(f"Post {item.get('id', '')} has no scheduled_at or date.")
    if slot_name not in LEGACY_SLOT_TIMES:
        raise ValueError(
            f"Post {item.get('id', '')} uses unsupported legacy time_slot: {slot_name}"
        )
    try:
        target_date = date.fromisoformat(date_text)
        hour_text, minute_text = LEGACY_SLOT_TIMES[slot_name].split(":", maxsplit=1)
        target_time = time(hour=int(hour_text), minute=int(minute_text))
    except ValueError as exc:
        raise ValueError(
            f"Post {item.get('id', '')} has invalid legacy schedule data."
        ) from exc
    return datetime.combine(target_date, target_time, tzinfo=timezone)


def scheduled_at_for(item: dict[str, Any], timezone: ZoneInfo) -> datetime:
    raw = str(item.get("scheduled_at", "")).strip()
    return parse_datetime(raw, timezone) if raw else legacy_scheduled_at(item, timezone)


def _int_setting(item: dict[str, Any], key: str, config_key: str, default: int) -> int:
    raw = item.get(key)
    if raw in (None, ""):
        raw = get_config("posting", config_key, default=default)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer.") from exc


def delay_bounds(item: dict[str, Any]) -> tuple[int, int]:
    minimum = _int_setting(item, "delay_min_minutes", "default_delay_min_minutes", 2)
    maximum = _int_setting(item, "delay_max_minutes", "default_delay_max_minutes", 14)
    if minimum < 0 or maximum < minimum or maximum > 1440:
        raise ValueError("delay minute bounds must satisfy 0 <= min <= max <= 1440.")
    return minimum, maximum


def thread_delay_bounds(item: dict[str, Any]) -> tuple[int, int]:
    minimum = _int_setting(
        item,
        "thread_delay_min_seconds",
        "default_thread_delay_min_seconds",
        8,
    )
    maximum = _int_setting(
        item,
        "thread_delay_max_seconds",
        "default_thread_delay_max_seconds",
        25,
    )
    if minimum < 0 or maximum < minimum or maximum > 3600:
        raise ValueError("thread delay bounds must satisfy 0 <= min <= max <= 3600.")
    return minimum, maximum


def ensure_timing_fields(
    item: dict[str, Any],
    timezone: ZoneInfo,
    *,
    rng: RandomLike | None = None,
    mutate: bool = True,
) -> tuple[dict[str, Any], bool]:
    """Set scheduled_at/delay/publish_after once and never slide publish_after."""
    target = item if mutate else copy.deepcopy(item)
    changed = False
    rng = rng or random.SystemRandom()

    scheduled_raw = str(target.get("scheduled_at", "")).strip()
    if scheduled_raw:
        scheduled = parse_datetime(scheduled_raw, timezone)
    else:
        scheduled = legacy_scheduled_at(target, timezone)
        target["scheduled_at"] = format_datetime(scheduled)
        changed = True

    minimum, maximum = delay_bounds(target)
    if target.get("delay_min_minutes") in (None, ""):
        target["delay_min_minutes"] = minimum
        changed = True
    if target.get("delay_max_minutes") in (None, ""):
        target["delay_max_minutes"] = maximum
        changed = True

    publish_raw = str(target.get("publish_after", "")).strip()
    delay_raw = target.get("delay_minutes")

    if publish_raw:
        publish_after = parse_datetime(publish_raw, timezone)
        if delay_raw in (None, ""):
            delta_minutes = int((publish_after - scheduled).total_seconds() // 60)
            target["delay_minutes"] = delta_minutes
            changed = True
        else:
            int(delay_raw)
        return target, changed

    if delay_raw not in (None, ""):
        try:
            delay_minutes = int(delay_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("delay_minutes must be an integer.") from exc
        if delay_minutes < 0:
            raise ValueError("delay_minutes must be zero or greater.")
    else:
        delay_minutes = rng.randint(minimum, maximum)
        target["delay_minutes"] = delay_minutes
        changed = True

    target["publish_after"] = format_datetime(
        scheduled + timedelta(minutes=delay_minutes)
    )
    changed = True
    return target, changed


def boolean_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def series_key(item: dict[str, Any]) -> str:
    return str(item.get("series_id") or item.get("series") or "").strip()


def item_order_key(item: dict[str, Any], timezone: ZoneInfo) -> tuple[datetime, str]:
    return scheduled_at_for(item, timezone), str(item.get("id", ""))


def blocked_by_later_posted(
    candidate: dict[str, Any],
    all_items: Iterable[dict[str, Any]],
    timezone: ZoneInfo,
) -> bool:
    if str(candidate.get("status", "")).lower() == "posting":
        return False
    if boolean_value(candidate.get("allow_out_of_order", False)):
        return False
    key = series_key(candidate)
    if not key:
        return False
    candidate_key = item_order_key(candidate, timezone)
    for other in all_items:
        if other is candidate:
            continue
        if str(other.get("status", "")).lower() != "posted":
            continue
        if series_key(other) != key:
            continue
        if item_order_key(other, timezone) > candidate_key:
            return True
    return False


def select_candidate(
    schedule_files: Iterable[ScheduleFile],
    now: datetime,
    timezone: ZoneInfo,
    *,
    allow_out_of_order: bool = False,
    post_id: str = "",
) -> Candidate | None:
    files = list(schedule_files)
    all_items = [item for sf in files for item in sf.entries if isinstance(item, dict)]
    candidates: list[Candidate] = []

    for schedule_file in files:
        for item in schedule_file.entries:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).lower().strip()
            if status not in ACTIVE_STATUSES:
                continue
            item_id = str(item.get("id", "")).strip()
            if post_id and item_id != post_id:
                continue
            scheduled = scheduled_at_for(item, timezone)
            publish_after = parse_datetime(item.get("publish_after"), timezone)
            manual_exact = bool(post_id and item_id == post_id)
            if not manual_exact and publish_after > now:
                continue
            if (
                not manual_exact
                and not allow_out_of_order
                and blocked_by_later_posted(item, all_items, timezone)
            ):
                continue
            candidates.append(
                Candidate(schedule_file, item, publish_after, scheduled)
            )

    if post_id and not candidates:
        return None
    candidates.sort(
        key=lambda candidate: (
            0 if str(candidate.item.get("status", "")).lower() == "posting" else 1,
            candidate.publish_after,
            candidate.scheduled_at,
            str(candidate.item.get("id", "")),
        )
    )
    return candidates[0] if candidates else None


def overdue_ready_items(
    schedule_files: Iterable[ScheduleFile],
    now: datetime,
    timezone: ZoneInfo,
) -> list[dict[str, str]]:
    """List ready posts that need review without mutating YAML."""
    results: list[dict[str, str]] = []
    for schedule_file in schedule_files:
        for item in schedule_file.entries:
            if not isinstance(item, dict):
                continue
            if str(item.get("status", "")).lower().strip() != "ready":
                continue
            try:
                scheduled = scheduled_at_for(item, timezone)
                publish_raw = str(item.get("publish_after", "")).strip()
                effective = parse_datetime(publish_raw, timezone) if publish_raw else scheduled
            except ValueError as exc:
                results.append(
                    {
                        "id": str(item.get("id", "")),
                        "file": str(schedule_file.path),
                        "classification": "review_required",
                        "reason": str(exc),
                    }
                )
                continue
            if effective <= now:
                results.append(
                    {
                        "id": str(item.get("id", "")),
                        "file": str(schedule_file.path),
                        "classification": "review_required",
                        "reason": "publish time has passed",
                    }
                )
    return results
