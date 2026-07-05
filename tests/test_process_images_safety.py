import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.process_images import process_images, update_schedules


class ProcessImagesSafetyTests(unittest.TestCase):
    def test_disabled_processing_stops_before_scan(self):
        with patch("src.process_images.configured_images_enabled", return_value=False), patch("src.process_images.iter_images") as scan:
            self.assertEqual(process_images(dry_run=False), 0)
            scan.assert_not_called()

    def test_image_url_does_not_approve_draft(self):
        item = {
            "id": "image-post-1",
            "status": "draft",
            "text": "test",
            "image_key": "sample-image",
            "image_url": "",
        }
        schedule_file = SimpleNamespace(entries=[item])
        with patch("src.process_images.load_active_schedule_files", return_value=[schedule_file]), patch("src.process_images.save_schedule_file") as save:
            matches = update_schedules(
                "sample-image",
                "https://example.invalid/sample-image.webp",
                "assets/webp/sample-image.webp",
            )

        self.assertEqual(matches, 1)
        self.assertEqual(item["status"], "draft")
        self.assertTrue(item["image_url"].endswith("sample-image.webp"))
        save.assert_called_once_with(schedule_file)


if __name__ == "__main__":
    unittest.main()
