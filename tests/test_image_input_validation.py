import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_images import (
    asset_subdirectory,
    validate_image_key,
    validate_unique_image_keys,
)


class ImageInputValidationTests(unittest.TestCase):
    def test_rejects_filename_with_space(self):
        with self.assertRaises(ValueError):
            validate_image_key("bad name")

    def test_rejects_duplicate_stems(self):
        with self.assertRaises(ValueError):
            validate_unique_image_keys([Path("same.png"), Path("same.jpg")])

    def test_rejects_absolute_output_path(self):
        with patch("src.process_images.get_config", return_value="/outside"):
            with self.assertRaises(ValueError):
                asset_subdirectory()


if __name__ == "__main__":
    unittest.main()
