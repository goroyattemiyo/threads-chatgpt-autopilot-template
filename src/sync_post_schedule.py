from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

BEGIN_MARKER = "    # BEGIN AUTO-GENERATED POSTING SCHEDULE"
END_MARKER = "    # END AUTO-GENERATED POSTING SCHEDULE"
DEFAULT_CONFIG = Path("config/service.yml")
DEFAULT_WORKFLOW = Path(".github/workflows/post-due.yml")


def load_schedule_settings(config_path: Path) -> tuple[str, list[str], list[int]]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    timezone_name = str(data.get("service", {}).get("timezone", "Asia/Tokyo"))
    posting = data.get("posting", {})
    slots = posting.get("time_slots", {})
    offsets = posting.get("schedule_offsets_minutes", [-3, 2, 7])

    if not isinstance(slots, dict) or not slots:
        raise ValueError("posting.time_slots must contain at least one posting time")
    if not isinstance(offsets, list) or not offsets:
        raise ValueError("posting.schedule_offsets_minutes must contain at least one integer")

    times = []
    for name, value in slots.items():
        text = str(value)
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"Invalid posting time for {name}: {text}") from exc
        times.append(text)

    parsed_offsets = []
    for value in offsets:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("posting.schedule_offsets_minutes must contain integers only")
        parsed_offsets.append(value)

    ZoneInfo(timezone_name)
    return timezone_name, times, parsed_offsets


def build_cron_entries(timezone_name: str, times: list[str], offsets: list[int]) -> list[str]:
    timezone = ZoneInfo(timezone_name)
    base_date = datetime(2026, 1, 15, tzinfo=timezone)
    entries: set[tuple[int, int]] = set()

    for time_text in times:
        hour, minute = (int(part) for part in time_text.split(":"))
        local_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for offset in offsets:
            utc_time = (local_time + timedelta(minutes=offset)).astimezone(ZoneInfo("UTC"))
            entries.add((utc_time.hour, utc_time.minute))

    return [f"    - cron: '{minute} {hour} * * *'" for hour, minute in sorted(entries)]


def replace_generated_schedule(workflow_text: str, cron_lines: list[str]) -> str:
    if BEGIN_MARKER not in workflow_text or END_MARKER not in workflow_text:
        raise ValueError("Auto-generated schedule markers are missing from post-due workflow")

    before, remainder = workflow_text.split(BEGIN_MARKER, 1)
    _, after = remainder.split(END_MARKER, 1)
    generated = "\n".join([BEGIN_MARKER, *cron_lines, END_MARKER])
    return f"{before}{generated}{after}"


def sync(config_path: Path, workflow_path: Path, check: bool = False) -> bool:
    timezone_name, times, offsets = load_schedule_settings(config_path)
    cron_lines = build_cron_entries(timezone_name, times, offsets)
    current = workflow_path.read_text(encoding="utf-8")
    updated = replace_generated_schedule(current, cron_lines)

    changed = current != updated
    if check and changed:
        raise SystemExit("post-due.yml is out of sync with config/service.yml")
    if changed and not check:
        workflow_path.write_text(updated, encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync posting cron entries from service config")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    changed = sync(args.config, args.workflow, check=args.check)
    print("Posting schedule updated." if changed else "Posting schedule already synchronized.")


if __name__ == "__main__":
    main()
