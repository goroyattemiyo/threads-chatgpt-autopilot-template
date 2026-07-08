"""Read-only post history and similarity search utilities."""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .utils import load_yaml, repo_path

POSTED_LOG_PATH = repo_path("posts", "posted_log.yml")
SCHEDULES_DIR = repo_path("posts", "schedules")


def normalize_text(value: Any) -> str:
    """Normalize Japanese and Latin text for stable comparisons."""
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(char for char in normalized if char.isalnum())


def parse_iso_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _bool_filter(value: str | None) -> bool | None:
    if value in (None, "", "any"):
        return None
    if value == "yes":
        return True
    if value == "no":
        return False
    raise ValueError(f"Unsupported boolean filter: {value}")


def load_posted_history(path: Path = POSTED_LOG_PATH) -> list[dict[str, Any]]:
    """Load posted history and enrich each row with thread/image flags."""
    raw_entries = load_yaml(path, default=[])
    if not isinstance(raw_entries, list):
        raise ValueError(f"Posted log must be a YAML list: {path}")

    schedule_counts = Counter(
        str(entry.get("schedule_id", ""))
        for entry in raw_entries
        if isinstance(entry, dict) and entry.get("schedule_id")
    )
    results: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        schedule_id = str(item.get("schedule_id", ""))
        item["has_image"] = bool(str(item.get("image_url", "")).strip())
        item["is_thread"] = schedule_counts.get(schedule_id, 0) > 1
        item["thread_count"] = schedule_counts.get(schedule_id, 1)
        results.append(item)
    return results


def search_history(
    entries: Iterable[dict[str, Any]],
    *,
    query: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    category: str = "",
    has_image: str | None = None,
    is_thread: str | None = None,
    role: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Filter posted history by text, date, category, image and thread type."""
    query_norm = normalize_text(query)
    start = date.fromisoformat(date_from) if date_from else None
    end = date.fromisoformat(date_to) if date_to else None
    image_filter = _bool_filter(has_image)
    thread_filter = _bool_filter(is_thread)
    category_norm = normalize_text(category)
    role_norm = normalize_text(role)

    results: list[dict[str, Any]] = []
    for entry in entries:
        posted_date = parse_iso_date(entry.get("posted_at"))
        if start and (posted_date is None or posted_date < start):
            continue
        if end and (posted_date is None or posted_date > end):
            continue
        if category_norm and normalize_text(entry.get("category")) != category_norm:
            continue
        if role_norm and normalize_text(entry.get("thread_role")) != role_norm:
            continue
        if image_filter is not None and bool(entry.get("has_image")) != image_filter:
            continue
        if thread_filter is not None and bool(entry.get("is_thread")) != thread_filter:
            continue

        searchable = " ".join(
            str(entry.get(key, ""))
            for key in (
                "post_id",
                "schedule_id",
                "category",
                "series_id",
                "thread_role",
                "text_head",
            )
        )
        if query_norm and query_norm not in normalize_text(searchable):
            continue
        results.append(dict(entry))

    results.sort(key=lambda item: str(item.get("posted_at", "")), reverse=True)
    return results[: max(limit, 0)]


def load_schedule_texts(schedules_dir: Path = SCHEDULES_DIR) -> list[dict[str, Any]]:
    """Load root and reply text segments from every weekly schedule file."""
    if not schedules_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for path in sorted(schedules_dir.glob("*.yml")):
        entries = load_yaml(path, default=[])
        if not isinstance(entries, list):
            raise ValueError(f"Schedule file must be a YAML list: {path}")
        for item in entries:
            if not isinstance(item, dict):
                continue
            common = {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
                "category": str(item.get("category", "")),
                "status": str(item.get("status", "")),
                "scheduled_at": str(item.get("scheduled_at", "")),
                "source_file": path.name,
            }
            root_text = str(item.get("text", ""))
            if root_text.strip():
                results.append(
                    {
                        **common,
                        "segment_index": 1,
                        "segment_role": "root",
                        "text": root_text,
                    }
                )
            thread_posts = item.get("thread_posts", [])
            if not isinstance(thread_posts, list):
                continue
            for index, reply in enumerate(thread_posts, start=2):
                if not isinstance(reply, dict):
                    continue
                reply_text = str(reply.get("text", ""))
                if not reply_text.strip():
                    continue
                results.append(
                    {
                        **common,
                        "segment_index": index,
                        "segment_role": "reply",
                        "text": reply_text,
                    }
                )
    return results


def similarity_score(left: str, right: str) -> float:
    """Return a normalized character-level similarity score from 0 to 1."""
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm, autojunk=False).ratio()


def search_similar(
    candidate_text: str,
    records: Iterable[dict[str, Any]],
    *,
    threshold: float = 0.55,
    limit: int = 20,
    exclude_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Rank schedule text segments that are similar to candidate_text."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    excluded = {str(item) for item in exclude_ids}
    results: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("id", "")) in excluded:
            continue
        score = similarity_score(candidate_text, str(record.get("text", "")))
        if score < threshold:
            continue
        results.append({**record, "similarity": round(score, 4)})

    results.sort(
        key=lambda item: (
            float(item.get("similarity", 0.0)),
            str(item.get("scheduled_at", "")),
        ),
        reverse=True,
    )
    return results[: max(limit, 0)]


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    history = subparsers.add_parser("history", help="Search posts/posted_log.yml")
    history.add_argument("--query", default="")
    history.add_argument("--date-from")
    history.add_argument("--date-to")
    history.add_argument("--category", default="")
    history.add_argument("--has-image", choices=("any", "yes", "no"), default="any")
    history.add_argument("--thread", choices=("any", "yes", "no"), default="any")
    history.add_argument("--role", choices=("", "root", "reply"), default="")
    history.add_argument("--limit", type=int, default=50)

    similar = subparsers.add_parser("similar", help="Search all schedule texts")
    similar.add_argument("--text", required=True)
    similar.add_argument("--threshold", type=float, default=0.55)
    similar.add_argument("--limit", type=int, default=20)
    similar.add_argument("--exclude-id", action="append", default=[])

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "history":
        results = search_history(
            load_posted_history(),
            query=args.query,
            date_from=args.date_from,
            date_to=args.date_to,
            category=args.category,
            has_image=args.has_image,
            is_thread=args.thread,
            role=args.role,
            limit=args.limit,
        )
        _print_json(results)
        return 0

    if args.command == "similar":
        results = search_similar(
            args.text,
            load_schedule_texts(),
            threshold=args.threshold,
            limit=args.limit,
            exclude_ids=args.exclude_id,
        )
        _print_json(results)
        return 0

    raise AssertionError(f"Unexpected command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
