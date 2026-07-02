"""Helpers for weekly and legacy schedule YAML files."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .utils import load_yaml, repo_path, save_yaml, today_local_str

LEGACY_SCHEDULE_PATH = repo_path("posts", "schedule.yml")
SCHEDULES_DIR = repo_path("posts", "schedules")
SCHEDULE_FILE_RE = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2})_to_(?P<end>\d{4}-\d{2}-\d{2})\.ya?ml$"
)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class ScheduleFile:
    path: Path
    start: date
    end: date
    entries: list[dict[str, Any]]
    legacy: bool = False

    def contains(self, target: date) -> bool:
        return self.start <= target <= self.end

    def is_past(self, today: date) -> bool:
        return self.end < today


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def week_bounds(target: date) -> tuple[date, date]:
    start = target - timedelta(days=target.weekday())
    return start, start + timedelta(days=6)


def schedule_filename(start: date, end: date) -> str:
    return f"{start.isoformat()}_to_{end.isoformat()}.yml"


def schedule_path_for_date(target: str | date) -> Path:
    start, end = week_bounds(parse_date(target))
    return SCHEDULES_DIR / schedule_filename(start, end)


def parse_schedule_file(path: Path) -> ScheduleFile | None:
    match = SCHEDULE_FILE_RE.match(path.name)
    if not match:
        return None
    start = parse_date(match.group("start"))
    end = parse_date(match.group("end"))
    entries = load_yaml(path, default=[])
    if not isinstance(entries, list):
        raise ValueError(f"Schedule file must be a YAML list: {path}")
    return ScheduleFile(path=path, start=start, end=end, entries=entries)


def weekly_schedule_files(
    include_past: bool = False,
    today: str | date | None = None,
) -> list[ScheduleFile]:
    if not SCHEDULES_DIR.exists():
        return []

    today_date = parse_date(today or today_local_str())
    results: list[ScheduleFile] = []
    for path in sorted(SCHEDULES_DIR.glob("*.yml")):
        parsed = parse_schedule_file(path)
        if parsed is None:
            continue
        if not include_past and parsed.is_past(today_date):
            continue
        results.append(parsed)
    return results


def has_weekly_schedules() -> bool:
    return bool(list(SCHEDULES_DIR.glob("*.yml"))) if SCHEDULES_DIR.exists() else False


def legacy_schedule_file() -> ScheduleFile:
    entries = load_yaml(LEGACY_SCHEDULE_PATH, default=[])
    if not isinstance(entries, list):
        raise ValueError("posts/schedule.yml must be a YAML list.")

    dates = [
        parse_date(str(item.get("date")))
        for item in entries
        if isinstance(item, dict) and item.get("date")
    ]
    if dates:
        start, end = min(dates), max(dates)
    else:
        start = end = parse_date(today_local_str())
    return ScheduleFile(
        path=LEGACY_SCHEDULE_PATH,
        start=start,
        end=end,
        entries=entries,
        legacy=True,
    )


def load_schedule_for_date(target: str | date) -> ScheduleFile:
    target_date = parse_date(target)
    if has_weekly_schedules():
        path = schedule_path_for_date(target_date)
        if path.exists():
            parsed = parse_schedule_file(path)
            if parsed is None:
                raise ValueError(f"Invalid schedule filename: {path.name}")
            return parsed
        start, end = week_bounds(target_date)
        return ScheduleFile(path=path, start=start, end=end, entries=[])
    return legacy_schedule_file()


def save_schedule_file(schedule_file: ScheduleFile) -> None:
    save_yaml(schedule_file.path, schedule_file.entries)


def load_active_schedule_files(include_past: bool = False) -> list[ScheduleFile]:
    if has_weekly_schedules():
        return weekly_schedule_files(include_past=include_past)
    return [legacy_schedule_file()]


def extract_dates_from_text(value: str) -> set[date]:
    return {parse_date(raw) for raw in DATE_RE.findall(value)}


def load_schedule_files_for_dates(dates: Iterable[str | date]) -> list[ScheduleFile]:
    unique_dates = sorted({parse_date(item) for item in dates})
    if not unique_dates:
        return []
    if not has_weekly_schedules():
        return [legacy_schedule_file()]

    files_by_path: dict[Path, ScheduleFile] = {}
    for target in unique_dates:
        schedule_file = load_schedule_for_date(target)
        files_by_path[schedule_file.path] = schedule_file
    return [files_by_path[path] for path in sorted(files_by_path)]
