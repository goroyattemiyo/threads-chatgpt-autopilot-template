"""Initialize minute-level schedules and publish one due root post per run."""
from __future__ import annotations

import argparse
import copy
from typing import Any

from .config_loader import get_config, service_timezone
from .post_daily import post_schedule_item
from .schedule_store import ScheduleFile, load_active_schedule_files, save_schedule_file
from .scheduler import ensure_timing_fields, overdue_ready_items, select_candidate
from .utils import now_local


def configured_threads_enabled() -> bool:
    value: Any = get_config("posting", "enable_threads", default=False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _copy_schedule_files(schedule_files: list[ScheduleFile]) -> list[ScheduleFile]:
    return [
        ScheduleFile(
            path=schedule_file.path,
            start=schedule_file.start,
            end=schedule_file.end,
            entries=copy.deepcopy(schedule_file.entries),
            legacy=schedule_file.legacy,
        )
        for schedule_file in schedule_files
    ]


def initialize_active_timings(
    schedule_files: list[ScheduleFile],
    *,
    dry_run: bool,
) -> list[ScheduleFile]:
    timezone = service_timezone()
    working_files = _copy_schedule_files(schedule_files) if dry_run else schedule_files
    for schedule_file in working_files:
        changed = False
        for item in schedule_file.entries:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).lower().strip()
            if status not in {"ready", "posting"}:
                continue
            _, item_changed = ensure_timing_fields(item, timezone, mutate=True)
            changed = changed or item_changed
        if changed and not dry_run:
            save_schedule_file(schedule_file)
    return working_files


def audit_overdue() -> int:
    timezone = service_timezone()
    now = now_local()
    schedule_files = load_active_schedule_files(include_past=True)
    results = overdue_ready_items(schedule_files, now, timezone)
    if not results:
        print("No overdue ready posts found.")
        return 0
    print("Overdue ready posts require classification before enabling posting:")
    for result in results:
        print(
            f"- id={result['id']} file={result['file']} "
            f"classification={result['classification']} reason={result['reason']}"
        )
    return 2


def post_due(
    *,
    dry_run: bool = False,
    allow_out_of_order: bool = False,
    post_id: str = "",
) -> int:
    if not dry_run and not configured_threads_enabled():
        print(
            "Threads posting is disabled by "
            "config/service.yml posting.enable_threads."
        )
        return 0

    timezone = service_timezone()
    now = now_local()
    schedule_files = load_active_schedule_files(include_past=True)
    working_files = initialize_active_timings(schedule_files, dry_run=dry_run)
    candidate = select_candidate(
        working_files,
        now,
        timezone,
        allow_out_of_order=allow_out_of_order,
        post_id=post_id,
    )
    if candidate is None:
        if post_id:
            print(f"No publishable item found for post_id={post_id}.")
        else:
            print(f"No due posts at {now.isoformat(timespec='minutes')}.")
        return 0

    print(
        "Selected one candidate:",
        f"id={candidate.item.get('id', '')}",
        f"status={candidate.item.get('status', '')}",
        f"publish_after={candidate.item.get('publish_after', '')}",
    )
    return post_schedule_item(
        candidate.schedule_file,
        candidate.item,
        dry_run=dry_run,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-out-of-order", action="store_true")
    parser.add_argument("--post-id", default="")
    parser.add_argument("--audit-overdue", action="store_true")
    args = parser.parse_args()
    if args.audit_overdue:
        raise SystemExit(audit_overdue())
    raise SystemExit(
        post_due(
            dry_run=args.dry_run,
            allow_out_of_order=args.allow_out_of_order,
            post_id=args.post_id.strip(),
        )
    )


if __name__ == "__main__":
    main()
