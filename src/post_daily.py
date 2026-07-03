"""Publish one scheduled Threads post and resume interrupted threads safely."""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from .github_checkpoint import checkpoint_file
from .schedule_store import ScheduleFile, load_schedule_for_date, save_schedule_file
from .scheduler import thread_delay_bounds
from .threads_api import ThreadsAPI
from .utils import (
    load_yaml,
    repo_path,
    require_env,
    save_yaml,
    timestamp_local,
    today_local_str,
)


class RandomLike(Protocol):
    def randint(self, a: int, b: int) -> int: ...


def find_post(
    schedule: list[dict[str, Any]],
    date: str,
    time_slot: str,
) -> dict[str, Any] | None:
    """Backward-compatible manual lookup by date and legacy time slot."""
    for item in schedule:
        if not isinstance(item, dict):
            continue
        if str(item.get("date")) != date:
            continue
        if str(item.get("time_slot")) != time_slot:
            continue
        if str(item.get("status", "")).lower() not in {"ready", "posting"}:
            continue
        return item
    return None


def normalize_thread_posts(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("thread_posts must be a list.")

    results: list[dict[str, Any]] = []
    for index, part in enumerate(raw, start=1):
        if isinstance(part, str):
            part = {"text": part}
        if not isinstance(part, dict):
            raise ValueError(f"thread_posts[{index}] must be a mapping or string.")
        text = str(part.get("text", "")).strip()
        image_url = str(part.get("image_url", "")).strip()
        alt = str(part.get("alt", "")).strip()
        if not text and not image_url:
            continue
        results.append(
            {
                "text": text,
                "image_url": image_url,
                "alt": alt,
                "index": index,
            }
        )
    return results


def publish_one(
    api: ThreadsAPI,
    text: str,
    image_url: str = "",
    alt: str = "",
    reply_to_id: str = "",
) -> dict[str, Any]:
    if image_url:
        return api.post_image(
            text,
            image_url,
            alt_text=alt,
            reply_to_id=reply_to_id,
        )
    return api.post_text(text, reply_to_id=reply_to_id)


def mark_error(item: dict[str, Any], message: str) -> None:
    item["status"] = "error"
    item["error"] = message[:500]
    item["error_at"] = timestamp_local()


def _log_path(custom_path: Path | None = None) -> Path:
    return custom_path or repo_path("posts", "posted_log.yml")


def _save_schedule_checkpoint(schedule_file: ScheduleFile, message: str) -> None:
    """Save locally and persist remotely before another API call is allowed."""
    save_schedule_file(schedule_file)
    checkpoint_file(schedule_file.path, message)


def _save_log_checkpoint(path: Path, message: str) -> None:
    checkpoint_file(path, message)


def append_post_log_once(
    *,
    post_id: str,
    schedule_id: str,
    scheduled_at: str,
    item: dict[str, Any],
    thread_index: int,
    thread_role: str,
    text: str,
    image_url: str,
    posted_at: str,
    reply_to_id: str = "",
    log_path: Path | None = None,
) -> bool:
    """Append one unique log record and return whether the file changed."""
    path = _log_path(log_path)
    records = load_yaml(path, default=[])
    if not isinstance(records, list):
        raise ValueError(f"YAML file is not a list: {path}")
    if any(
        isinstance(record, dict) and str(record.get("post_id")) == post_id
        for record in records
    ):
        return False
    record: dict[str, Any] = {
        "post_id": post_id,
        "schedule_id": schedule_id,
        "scheduled_at": scheduled_at,
        "category": item.get("category", ""),
        "series_id": item.get("series_id", item.get("series", "")),
        "thread_index": thread_index,
        "thread_role": thread_role,
        "text_head": text[:100],
        "image_url": image_url,
        "posted_at": posted_at,
    }
    if reply_to_id:
        record["reply_to_id"] = reply_to_id
    records.append(record)
    save_yaml(path, records)
    return True


def _progress(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("thread_progress")
    progress = dict(raw) if isinstance(raw, dict) else {}
    root_id = str(
        progress.get("root_post_id") or item.get("threads_post_id") or ""
    ).strip()
    raw_reply_ids = progress.get("reply_ids", item.get("thread_post_ids", []))
    reply_ids = (
        [str(value) for value in raw_reply_ids]
        if isinstance(raw_reply_ids, list)
        else []
    )
    completed = progress.get("completed_replies", len(reply_ids))
    try:
        completed_int = int(completed)
    except (TypeError, ValueError):
        completed_int = len(reply_ids)
    completed_int = max(completed_int, len(reply_ids))
    raw_reply_times = progress.get("reply_posted_at", [])
    reply_times = (
        [str(value) for value in raw_reply_times]
        if isinstance(raw_reply_times, list)
        else []
    )
    progress.update(
        {
            "root_post_id": root_id,
            "reply_ids": reply_ids,
            "reply_posted_at": reply_times,
            "completed_replies": completed_int,
            "updated_at": str(progress.get("updated_at", "")),
        }
    )
    return progress


def post_schedule_item(
    schedule_file: ScheduleFile,
    item: dict[str, Any],
    *,
    dry_run: bool = False,
    api: ThreadsAPI | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    rng: RandomLike | None = None,
    log_path: Path | None = None,
) -> int:
    """Publish or resume exactly one root post and its replies in this run."""
    status = str(item.get("status", "")).lower().strip()
    if status == "posted":
        print(f"Skipping already posted item: {item.get('id', '')}")
        return 0
    if status not in {"ready", "posting"}:
        print(f"Item is not publishable: status={status} id={item.get('id', '')}")
        return 0

    text = str(item.get("text", "")).strip()
    image_url = str(item.get("image_url", "")).strip()
    alt = str(item.get("alt", "")).strip()
    thread_posts = normalize_thread_posts(item.get("thread_posts", []))
    if not text:
        raise ValueError("Schedule item has no text.")

    print(
        "Target:",
        f"scheduled_at={item.get('scheduled_at', '')}",
        f"publish_after={item.get('publish_after', '')}",
        f"id={item.get('id', '')}",
    )
    print(text[:200])
    if dry_run:
        print("Dry run. No API call or YAML update was performed.")
        return 0

    item["status"] = "posting"
    item["error"] = ""
    progress = _progress(item)
    item["thread_progress"] = progress
    item["thread_post_ids"] = list(progress["reply_ids"])
    if progress["root_post_id"]:
        item["threads_post_id"] = progress["root_post_id"]
    _save_schedule_checkpoint(
        schedule_file,
        "chore: mark Threads post as posting",
    )

    rng = rng or random.SystemRandom()
    api_instance = api

    def get_api() -> ThreadsAPI:
        nonlocal api_instance
        if api_instance is None:
            api_instance = ThreadsAPI(
                access_token=require_env("THREADS_ACCESS_TOKEN"),
                user_id=require_env("THREADS_USER_ID"),
            )
        return api_instance

    root_id = str(progress.get("root_post_id", "")).strip()
    log_file = _log_path(log_path)

    if not root_id:
        root_result = publish_one(
            get_api(),
            text,
            image_url=image_url,
            alt=alt,
        )
        if "error" in root_result:
            mark_error(item, f"Root post failed: {root_result['error']}")
            _save_schedule_checkpoint(
                schedule_file,
                "chore: record Threads root failure",
            )
            print("Root post failed.")
            return 1
        root_id = str(root_result.get("id", "")).strip()
        if not root_id:
            mark_error(item, f"Root post returned no id: {root_result}")
            _save_schedule_checkpoint(
                schedule_file,
                "chore: record missing Threads root id",
            )
            return 1

        root_posted_at = timestamp_local()
        item["threads_post_id"] = root_id
        item["posted_at"] = root_posted_at
        progress.update(
            {
                "root_post_id": root_id,
                "root_posted_at": root_posted_at,
                "reply_ids": list(progress["reply_ids"]),
                "reply_posted_at": list(progress.get("reply_posted_at", [])),
                "completed_replies": len(progress["reply_ids"]),
                "updated_at": root_posted_at,
            }
        )
        item["thread_progress"] = progress
        _save_schedule_checkpoint(
            schedule_file,
            "chore: checkpoint Threads root post id",
        )
        if append_post_log_once(
            post_id=root_id,
            schedule_id=str(item.get("id", "")),
            scheduled_at=str(item.get("scheduled_at", "")),
            item=item,
            thread_index=1,
            thread_role="root",
            text=text,
            image_url=image_url,
            posted_at=root_posted_at,
            log_path=log_path,
        ):
            _save_log_checkpoint(
                log_file,
                "chore: record Threads root post log",
            )
        print(f"Posted root: {root_id}")
    else:
        known_root_time = str(
            progress.get("root_posted_at") or item.get("posted_at") or ""
        ).strip()
        if known_root_time and append_post_log_once(
            post_id=root_id,
            schedule_id=str(item.get("id", "")),
            scheduled_at=str(item.get("scheduled_at", "")),
            item=item,
            thread_index=1,
            thread_role="root",
            text=text,
            image_url=image_url,
            posted_at=known_root_time,
            log_path=log_path,
        ):
            _save_log_checkpoint(
                log_file,
                "chore: restore Threads root post log",
            )
        print(f"Resuming existing root: {root_id}")

    reply_ids = list(progress.get("reply_ids", []))
    reply_posted_times = list(progress.get("reply_posted_at", []))
    completed = max(int(progress.get("completed_replies", 0)), len(reply_ids))
    if completed > len(thread_posts):
        mark_error(item, "thread_progress exceeds configured thread_posts.")
        _save_schedule_checkpoint(
            schedule_file,
            "chore: record invalid Threads thread progress",
        )
        return 1

    for existing_index, existing_reply_id in enumerate(reply_ids):
        if (
            existing_index >= len(thread_posts)
            or existing_index >= len(reply_posted_times)
        ):
            continue
        existing_part = thread_posts[existing_index]
        previous_id = root_id if existing_index == 0 else reply_ids[existing_index - 1]
        if append_post_log_once(
            post_id=existing_reply_id,
            schedule_id=str(item.get("id", "")),
            scheduled_at=str(item.get("scheduled_at", "")),
            item=item,
            thread_index=existing_index + 2,
            thread_role="reply",
            text=str(existing_part.get("text", "")),
            image_url=str(existing_part.get("image_url", "")),
            posted_at=reply_posted_times[existing_index],
            reply_to_id=previous_id,
            log_path=log_path,
        ):
            _save_log_checkpoint(
                log_file,
                "chore: restore Threads reply post log",
            )

    parent_id = reply_ids[-1] if reply_ids else root_id
    minimum_seconds, maximum_seconds = thread_delay_bounds(item)

    for zero_index in range(completed, len(thread_posts)):
        part = thread_posts[zero_index]
        delay_seconds = rng.randint(minimum_seconds, maximum_seconds)
        print(f"Waiting {delay_seconds}s before thread reply {zero_index + 1}.")
        sleep_fn(delay_seconds)
        reply_to_id = parent_id
        result = publish_one(
            get_api(),
            str(part.get("text", "")).strip(),
            image_url=str(part.get("image_url", "")).strip(),
            alt=str(part.get("alt", "")).strip(),
            reply_to_id=reply_to_id,
        )
        if "error" in result:
            mark_error(
                item,
                f"Thread reply {zero_index + 1} failed: {result['error']}",
            )
            _save_schedule_checkpoint(
                schedule_file,
                f"chore: record Threads reply {zero_index + 1} failure",
            )
            print(f"Thread reply {zero_index + 1} failed.")
            return 1

        reply_id = str(result.get("id", "")).strip()
        if not reply_id:
            mark_error(item, f"Thread reply {zero_index + 1} returned no id: {result}")
            _save_schedule_checkpoint(
                schedule_file,
                f"chore: record missing Threads reply {zero_index + 1} id",
            )
            return 1

        reply_posted_at = timestamp_local()
        reply_ids.append(reply_id)
        reply_posted_times.append(reply_posted_at)
        parent_id = reply_id
        progress.update(
            {
                "root_post_id": root_id,
                "reply_ids": list(reply_ids),
                "reply_posted_at": list(reply_posted_times),
                "completed_replies": len(reply_ids),
                "updated_at": reply_posted_at,
            }
        )
        item["thread_post_ids"] = list(reply_ids)
        item["thread_progress"] = progress
        _save_schedule_checkpoint(
            schedule_file,
            f"chore: checkpoint Threads reply {zero_index + 1} id",
        )
        if append_post_log_once(
            post_id=reply_id,
            schedule_id=str(item.get("id", "")),
            scheduled_at=str(item.get("scheduled_at", "")),
            item=item,
            thread_index=zero_index + 2,
            thread_role="reply",
            text=str(part.get("text", "")),
            image_url=str(part.get("image_url", "")),
            posted_at=reply_posted_at,
            reply_to_id=reply_to_id,
            log_path=log_path,
        ):
            _save_log_checkpoint(
                log_file,
                f"chore: record Threads reply {zero_index + 1} log",
            )
        print(f"Posted reply {zero_index + 1}: {reply_id}")

    finished_at = timestamp_local()
    progress.update(
        {
            "root_post_id": root_id,
            "reply_ids": list(reply_ids),
            "reply_posted_at": list(reply_posted_times),
            "completed_replies": len(reply_ids),
            "updated_at": finished_at,
        }
    )
    item["thread_progress"] = progress
    item["thread_post_ids"] = list(reply_ids)
    item["thread_count"] = 1 + len(reply_ids)
    item["status"] = "posted"
    item["error"] = ""
    _save_schedule_checkpoint(
        schedule_file,
        "chore: mark Threads post as posted",
    )
    print(f"Posted thread root={root_id} replies={len(reply_ids)}")
    return 0


def post_daily(date: str, time_slot: str, dry_run: bool = False) -> int:
    """Backward-compatible manual entry point."""
    schedule_file = load_schedule_for_date(date)
    item = find_post(schedule_file.entries, date, time_slot)
    if not item:
        print(f"No ready or posting item found for date={date} time_slot={time_slot}.")
        return 0
    return post_schedule_item(schedule_file, item, dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=today_local_str())
    parser.add_argument("--time-slot", default="morning")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(post_daily(args.date, args.time_slot, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
