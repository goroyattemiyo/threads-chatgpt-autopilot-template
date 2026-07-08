from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.search_posts import (
    load_posted_history,
    load_schedule_texts,
    search_history,
    search_similar,
    similarity_score,
)
from src.utils import save_yaml


class PostSearchTests(TestCase):
    def test_history_filters_text_date_category_image_and_thread(self) -> None:
        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "posted_log.yml"
            save_yaml(
                log_path,
                [
                    {
                        "post_id": "root-001",
                        "schedule_id": "thread-001",
                        "category": "validation",
                        "thread_index": 1,
                        "thread_role": "root",
                        "text_head": "Threads自動投稿ツールのツリー投稿テストです。",
                        "image_url": "",
                        "posted_at": "2026-07-08T10:00:00+09:00",
                    },
                    {
                        "post_id": "reply-001",
                        "schedule_id": "thread-001",
                        "category": "validation",
                        "thread_index": 2,
                        "thread_role": "reply",
                        "text_head": "返信投稿を確認しています。",
                        "image_url": "",
                        "posted_at": "2026-07-08T10:01:00+09:00",
                    },
                    {
                        "post_id": "image-001",
                        "schedule_id": "image-schedule-001",
                        "category": "campaign",
                        "thread_index": 1,
                        "thread_role": "root",
                        "text_head": "夏の画像付き投稿です。",
                        "image_url": "https://example.com/image.webp",
                        "posted_at": "2026-07-05T12:00:00+09:00",
                    },
                ],
            )

            entries = load_posted_history(log_path)
            thread_hits = search_history(
                entries,
                query="返信投稿",
                date_from="2026-07-08",
                date_to="2026-07-08",
                category="validation",
                has_image="no",
                is_thread="yes",
                role="reply",
            )
            self.assertEqual([item["post_id"] for item in thread_hits], ["reply-001"])
            self.assertTrue(thread_hits[0]["is_thread"])
            self.assertEqual(thread_hits[0]["thread_count"], 2)

            image_hits = search_history(entries, has_image="yes", is_thread="no")
            self.assertEqual([item["post_id"] for item in image_hits], ["image-001"])
            self.assertTrue(image_hits[0]["has_image"])

    def test_schedule_loader_and_similarity_search(self) -> None:
        with TemporaryDirectory() as temp_dir:
            schedules_dir = Path(temp_dir) / "schedules"
            schedules_dir.mkdir()
            save_yaml(
                schedules_dir / "2026-07-06_to_2026-07-12.yml",
                [
                    {
                        "id": "post-url-001",
                        "title": "URL投稿",
                        "category": "validation",
                        "scheduled_at": "2026-07-05T12:00:00+09:00",
                        "status": "posted",
                        "text": "Threads自動投稿ツールのURL投稿テストです。",
                    },
                    {
                        "id": "thread-001",
                        "title": "ツリー投稿",
                        "category": "validation",
                        "scheduled_at": "2026-07-08T15:00:00+09:00",
                        "status": "posted",
                        "text": "親投稿を確認しています。",
                        "thread_posts": [
                            {"text": "返信投稿を確認しています。"},
                            {"text": "投稿順と履歴を検証します。"},
                        ],
                    },
                    {
                        "id": "unrelated-001",
                        "title": "別内容",
                        "category": "other",
                        "scheduled_at": "2026-07-09T12:00:00+09:00",
                        "status": "draft",
                        "text": "今日は天気について話します。",
                    },
                ],
            )

            records = load_schedule_texts(schedules_dir)
            self.assertEqual(len(records), 5)
            self.assertEqual(
                [item["segment_role"] for item in records if item["id"] == "thread-001"],
                ["root", "reply", "reply"],
            )

            exact_hits = search_similar(
                "Threads自動投稿ツールのURL投稿テストです。",
                records,
                threshold=0.9,
            )
            self.assertEqual(exact_hits[0]["id"], "post-url-001")
            self.assertEqual(exact_hits[0]["similarity"], 1.0)

            near_hits = search_similar(
                "Threads自動投稿ツールのURL投稿をテストしています。",
                records,
                threshold=0.55,
            )
            self.assertEqual(near_hits[0]["id"], "post-url-001")
            self.assertGreaterEqual(near_hits[0]["similarity"], 0.55)

            excluded = search_similar(
                "Threads自動投稿ツールのURL投稿テストです。",
                records,
                threshold=0.9,
                exclude_ids=["post-url-001"],
            )
            self.assertEqual(excluded, [])

    def test_similarity_normalizes_width_case_spaces_and_punctuation(self) -> None:
        score = similarity_score(
            "ＡＢＣ Threads 投稿 テスト！",
            "abc threads投稿テスト",
        )
        self.assertEqual(score, 1.0)

    def test_invalid_similarity_threshold_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            search_similar("test", [], threshold=1.1)
