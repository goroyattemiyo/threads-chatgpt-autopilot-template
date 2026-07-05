from __future__ import annotations

import unittest

from src.text_limits import validate_post_item_texts


class TextLimitTests(unittest.TestCase):
    def test_accepts_500_character_root(self) -> None:
        self.assertEqual(validate_post_item_texts({"text": "あ" * 500}), [])

    def test_rejects_501_character_root(self) -> None:
        errors = validate_post_item_texts({"text": "あ" * 501})
        self.assertEqual(len(errors), 1)
        self.assertIn("501/500", errors[0])

    def test_rejects_overlong_thread_reply(self) -> None:
        errors = validate_post_item_texts(
            {"text": "root", "thread_posts": [{"text": "あ" * 501}]}
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("thread reply 1", errors[0])


if __name__ == "__main__":
    unittest.main()
