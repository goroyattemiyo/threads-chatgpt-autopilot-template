"""Post one ready schedule entry to Threads."""
from __future__ import annotations

import argparse
import sys
from typing import Any

from .schedule_store import load_schedule_for_date, save_schedule_file
from .threads_api import ThreadsAPI
from .utils import (
    append_yaml_list,
    repo_path,
    require_env,
    timestamp_local,
    today_local_str,
)


def find_post(
    schedule: list[dict[str, Any]],
    date: str,
    time_slot: str,
) -> dict[str, Any] | None:
    """Find one ready, not-yet-posted item."""
    for item in schedule:
        if not isinstance(item, dict):
            continue
        if str(item.get("date")) != date:
            continue
        if str(item.get("time_slot")) != time_slot:
            continue
        if str(item.get("status", "")).lower() != "ready":
            continue
        if str(item.get("threads_post_id", "")).strip():
            continue
        return item
    return None


def normalize_thread_posts(raw: Any) -> list[dict[str, Any]]:
    """Normalize reply items into dictionaries."""
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


def append_post_log(
    *,
    post_id: str,
    date: str,
    time_slot: str,
    item: dict[str, Any],
    thread_index: int,
    thread_role: str,
    text: str,
    image_url: str,
    posted_at: str,
    reply_to_id: str = "",
) -> None:
    record: dict[str, Any] = {
        "post_id": post_id,
        "schedule_id": item.get("id", ""),
        "date": date,
        "time_slot": time_slot,
        "category": item.get("category", ""),
        "thread_index": thread_index,
        "thread_role": thread_role,
        "text_head": text[:100],
        "image_url": image_url,
        "posted_at": posted_at,
    }
    if reply_to_id:
        record["reply_to_id"] = reply_to_id
    append_yaml_list(repo_path("posts", "posted_log.yml"), record)


def post_daily(date: str, time_slot: str, dry_run: bool = False) -> int:
    schedule_file = load_schedule_for_date(date)
    item = find_post(schedule_file.entries, date, time_slot)
    if not item:
        print(f"No ready post found for date={date} time_slot={time_slot}.")
        return 0

    text = str(item.get("text", "")).strip()
    image_url = str(item.get("image_url", "")).strip()
    alt = str(item.get("alt", "")).strip()
    thread_posts = normalize_thread_posts(item.get("thread_posts", []))

    if not text:
        raise ValueError("Schedule item has no text.")

    print(
        "Target:",
        f"date={date}",
        f"time_slot={time_slot}",
        f"id={item.get('id', '')}",
    )
    print(text[:200])
    if image_url:
        print(f"root image_url={image_url}")
    if thread_posts:
        print(f"thread replies={len(thread_posts)}")

    if dry_run:
        print("Dry run. No post was published.")
        return 0

    api = ThreadsAPI(
        access_token=require_env("THREADS_ACCESS_TOKEN"),
        user_id=require_env("THREADS_USER_ID"),
    )

    root_result = publish_one(api, text, image_url=image_url, alt=alt)
    if "error" in root_result:
        mark_error(item, str(root_result["error"]))
        save_schedule_file(schedule_file)
        print("Root post failed.")
        return 1

    root_post_id = str(root_result.get("id", ""))
    if not root_post_id:
        mark_error(item, f"No post id in result: {root_result}")
        save_schedule_file(schedule_file)
        print("Root post returned no post id.")
        return 1

    posted_at = timestamp_local()
    item["threads_post_id"] = root_post_id
    item["posted_at"] = posted_at
    item["error"] = ""
    append_post_log(
        post_id=root_post_id,
        date=date,
        time_slot=time_slot,
        item=item,
        thread_index=1,
        thread_role="root",
        text=text,
        image_url=image_url,
        posted_at=posted_at,
    )
    save_schedule_file(schedule_file)
    print(f"Posted root: {root_post_id}")

    reply_ids: list[str] = []
    parent_id = root_post_id
    for part in thread_posts:
        reply_to_id = parent_id
        result = publish_one(
            api,
            str(part.get("text", "")).strip(),
            image_url=str(part.get("image_url", "")).strip(),
            alt=str(part.get("alt", "")).strip(),
            reply_to_id=reply_to_id,
        )
        if "error" in result:
            mark_error(
                item,
                f"Thread reply {part['index']} failed: {result['error']}",
            )
            item["thread_post_ids"] = reply_ids
            save_schedule_file(schedule_file)
            print(f"Thread reply {part['index']} failed.")
            return 1

        reply_id = str(result.get("id", ""))
        if not reply_id:
            mark_error(item, f"No reply post id in result: {result}")
            item["thread_post_ids"] = reply_ids
            save_schedule_file(schedule_file)
            print(f"Thread reply {part['index']} returned no post id.")
            return 1

        reply_ids.append(reply_id)
        parent_id = reply_id
        reply_posted_at = timestamp_local()
        append_post_log(
            post_id=reply_id,
            date=date,
            time_slot=time_slot,
            item=item,
            thread_index=int(part["index"]) + 1,
            thread_role="reply",
            text=str(part.get("text", "")),
            image_url=str(part.get("image_url", "")),
            posted_at=reply_posted_at,
            reply_to_id=reply_to_id,
        )
        item["thread_post_ids"] = reply_ids
        save_schedule_file(schedule_file)
        print(f"Posted reply {part['index']}: {reply_id}")

    item["status"] = "posted"
    item["thread_post_ids"] = reply_ids
    item["thread_count"] = 1 + len(reply_ids)
    item["error"] = ""
    save_schedule_file(schedule_file)
    print(f"Posted thread root={root_post_id} replies={len(reply_ids)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=today_local_str())
    parser.add_argument("--time-slot", default="morning")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(post_daily(args.date, args.time_slot, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
