"""Initialize schedules, publish one due post, and preserve recovery metadata."""
from __future__ import annotations

import argparse
import copy
from typing import Any

from .config_loader import get_config, service_timezone
from .error_recovery import (
    apply_error_metadata,
    clear_error_metadata,
    recovery_action,
    sanitize_error,
)
from .github_checkpoint import CheckpointError, checkpoint_file
from .post_daily import post_schedule_item
from .schedule_store import ScheduleFile, load_active_schedule_files, save_schedule_file
from .scheduler import ensure_timing_fields, overdue_ready_items, select_candidate
from .text_limits import validate_post_item_texts
from .utils import now_local, timestamp_local


def configured_threads_enabled() -> bool:
    value: Any = get_config("posting", "enable_threads", default=False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _item_has_image(item: dict[str, Any]) -> bool:
    if str(item.get("image_url", "")).strip():
        return True
    thread_posts = item.get("thread_posts", [])
    return isinstance(thread_posts, list) and any(
        isinstance(part, dict) and str(part.get("image_url", "")).strip()
        for part in thread_posts
    )


def _record_checkpoint_failure(
    schedule_file: ScheduleFile,
    item: dict[str, Any],
    exc: Exception,
) -> None:
    """Save a local snapshot and print non-secret reconciliation identifiers."""
    item["checkpoint_error"] = sanitize_error(exc)
    item["checkpoint_failed_at"] = timestamp_local()
    item["recovery_action"] = recovery_action("checkpoint")
    save_schedule_file(schedule_file)

    reply_ids = item.get("thread_post_ids", [])
    if not isinstance(reply_ids, list):
        reply_ids = []
    print("CRITICAL_CHECKPOINT_FAILURE")
    print(f"schedule_id={item.get('id', '')}")
    print(f"root_post_id={item.get('threads_post_id', '')}")
    print(f"reply_post_ids={','.join(str(value) for value in reply_ids)}")
    print(f"checkpoint_error={sanitize_error(exc)}")
    print("Do not rerun until Threads, the Actions log, and the recovery artifact are reconciled.")


def _persist_failure(
    schedule_file: ScheduleFile,
    item: dict[str, Any],
    value: Any,
    *,
    kind_override: str = "",
) -> str:
    kind = apply_error_metadata(
        item,
        value,
        has_image=_item_has_image(item),
        kind_override=kind_override,
    )
    save_schedule_file(schedule_file)
    try:
        checkpoint_file(
            schedule_file.path,
            f"chore: classify Threads {kind} failure",
        )
    except CheckpointError as exc:
        _record_checkpoint_failure(schedule_file, item, exc)
        raise
    print(f"Recorded recoverable error: kind={kind} id={item.get('id', '')}")
    return kind


def _clear_recovered_error(schedule_file: ScheduleFile, item: dict[str, Any]) -> None:
    if not clear_error_metadata(item):
        return
    save_schedule_file(schedule_file)
    try:
        checkpoint_file(
            schedule_file.path,
            "chore: clear recovered Threads error metadata",
        )
    except CheckpointError as exc:
        _record_checkpoint_failure(schedule_file, item, exc)
        raise


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
    """Initialize scheduling fields once and persist them before posting."""
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
            checkpoint_file(
                schedule_file.path,
                "chore: initialize Threads posting schedule",
            )
    return working_files


def audit_overdue() -> int:
    """List overdue ready posts without treating findings as workflow failure."""
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
    return 0


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

    text_errors = validate_post_item_texts(candidate.item)
    if text_errors:
        print("Threads text validation failed before API call:")
        for error in text_errors:
            print(f"- {error}")
        return 1

    print(
        "Selected one candidate:",
        f"id={candidate.item.get('id', '')}",
        f"status={candidate.item.get('status', '')}",
        f"publish_after={candidate.item.get('publish_after', '')}",
    )
    try:
        result = post_schedule_item(
            candidate.schedule_file,
            candidate.item,
            dry_run=dry_run,
        )
    except CheckpointError as exc:
        _record_checkpoint_failure(candidate.schedule_file, candidate.item, exc)
        raise
    except RuntimeError as exc:
        message = sanitize_error(exc)
        if (
            "Required environment variable is missing" in message
            or "Threads user_id is required" in message
        ):
            _persist_failure(
                candidate.schedule_file,
                candidate.item,
                message,
                kind_override="configuration",
            )
            print("Posting configuration failed before an API request could complete.")
            return 1
        raise

    if result != 0:
        _persist_failure(
            candidate.schedule_file,
            candidate.item,
            candidate.item.get("error", "Unknown Threads posting error."),
        )
    elif str(candidate.item.get("status", "")).lower() == "posted":
        _clear_recovered_error(candidate.schedule_file, candidate.item)
    return result


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
