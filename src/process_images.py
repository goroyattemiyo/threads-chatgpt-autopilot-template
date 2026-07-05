"""Convert incoming images to WebP and update matching schedule items."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml
from PIL import Image

from .config_loader import get_config
from .schedule_store import load_active_schedule_files, save_schedule_file
from .utils import optional_env, repo_path, timestamp_local

INCOMING_DIR = repo_path("incoming", "images")
ASSET_REPO_DIR = repo_path("assets-repo")
ASSET_LOG_PATH = repo_path("posts", "assets.yml")
SUPPORTED_EXTS = {".webp", ".png", ".jpg", ".jpeg"}
SUPPORTED_IMAGE_FORMATS = {"WEBP", "PNG", "JPEG"}
IMAGE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PATH_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def configured_images_enabled() -> bool:
    """Return whether non-dry-run image processing is explicitly enabled."""
    value: Any = get_config("posting", "enable_images", default=False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def asset_subdirectory() -> Path:
    raw = str(
        get_config("assets", "public_subdirectory", default="assets/webp")
    ).strip().replace("\\", "/")
    if not raw:
        raise ValueError("assets.public_subdirectory is empty.")
    path = Path(raw)
    if path.is_absolute():
        raise ValueError("assets.public_subdirectory must be a relative path.")
    for part in path.parts:
        if part in {"", ".", ".."} or not PATH_SEGMENT_PATTERN.fullmatch(part):
            raise ValueError(
                "assets.public_subdirectory contains an unsafe path segment."
            )
    return path


def webp_quality() -> int:
    value = int(get_config("assets", "webp_quality", default=86))
    if not 1 <= value <= 100:
        raise ValueError("assets.webp_quality must be between 1 and 100.")
    return value


def assets_repository() -> str:
    configured = str(get_config("assets", "repository", default="")).strip()
    value = optional_env("ASSETS_REPO_FULL_NAME", configured)
    if not value or not REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError(
            "Set assets.repository or ASSETS_REPO_FULL_NAME as owner/repository."
        )
    return value


def assets_branch() -> str:
    configured = str(get_config("assets", "branch", default="main")).strip() or "main"
    return optional_env("ASSETS_REPO_BRANCH", configured) or "main"


def validate_image_key(image_key: str) -> None:
    if not IMAGE_KEY_PATTERN.fullmatch(image_key):
        raise ValueError(
            "Image filename stem must use 1-80 lowercase ASCII letters, "
            "numbers, hyphens, or underscores, and must start with a letter or number."
        )


def iter_images() -> list[Path]:
    if not INCOMING_DIR.exists():
        return []
    return [
        path
        for path in sorted(INCOMING_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    ]


def validate_unique_image_keys(images: list[Path]) -> None:
    seen: dict[str, str] = {}
    for image_path in images:
        image_key = image_path.stem
        validate_image_key(image_key)
        previous = seen.get(image_key)
        if previous:
            raise ValueError(
                f"Duplicate image_key={image_key}: {previous} and {image_path.name}"
            )
        seen[image_key] = image_path.name


def inspect_image(source_path: Path) -> tuple[str, int, int, int]:
    with Image.open(source_path) as image:
        image_format = str(image.format or "").upper()
        width, height = image.size
        image.verify()
    if image_format not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError(f"Unsupported image content format: {image_format or 'unknown'}")
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be greater than zero.")
    return image_format, width, height, source_path.stat().st_size


def convert_to_webp(source_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}.webp"

    with Image.open(source_path) as image:
        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")
        image.save(
            output_path,
            "WEBP",
            quality=webp_quality(),
            method=6,
        )
    return output_path


def raw_url(asset_relative_path: str) -> str:
    encoded_path = quote(asset_relative_path.replace("\\", "/"), safe="/")
    return (
        f"https://raw.githubusercontent.com/"
        f"{assets_repository()}/{assets_branch()}/{encoded_path}"
    )


def load_asset_log() -> list[dict[str, Any]]:
    if not ASSET_LOG_PATH.exists():
        return []
    data = yaml.safe_load(ASSET_LOG_PATH.read_text(encoding="utf-8"))
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("posts/assets.yml must be a YAML list.")
    return [item for item in data if isinstance(item, dict)]


def save_asset_log(records: list[dict[str, Any]]) -> None:
    ASSET_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ASSET_LOG_PATH.write_text(
        yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def upsert_asset_log(
    image_key: str,
    source_path: Path,
    url: str,
    asset_path: str,
    schedule_matches: int,
) -> None:
    record = {
        "image_key": image_key,
        "source_filename": source_path.name,
        "source_ext": source_path.suffix.lower(),
        "image_url": url,
        "asset_path": asset_path,
        "uploaded_at": timestamp_local(),
        "schedule_matches": schedule_matches,
    }
    records = load_asset_log()
    for index, item in enumerate(records):
        if str(item.get("image_key", "")).strip() == image_key:
            records[index] = record
            break
    else:
        records.append(record)
    save_asset_log(records)


def update_part_with_url(
    part: dict[str, Any],
    image_key: str,
    url: str,
    asset_path: str,
) -> bool:
    if str(part.get("image_key", "")).strip() != image_key:
        return False
    part["image_url"] = url
    part["local_webp"] = asset_path
    part["image_uploaded_at"] = timestamp_local()
    part["error"] = ""
    return True


def update_schedules(image_key: str, url: str, asset_path: str) -> int:
    """Attach the public URL without changing a post's approval status."""
    updated_count = 0
    for schedule_file in load_active_schedule_files(include_past=True):
        file_changed = False
        for item in schedule_file.entries:
            if not isinstance(item, dict):
                continue

            if update_part_with_url(item, image_key, url, asset_path):
                updated_count += 1
                file_changed = True

            thread_posts = item.get("thread_posts", [])
            if isinstance(thread_posts, list):
                for part in thread_posts:
                    if isinstance(part, dict) and update_part_with_url(
                        part,
                        image_key,
                        url,
                        asset_path,
                    ):
                        updated_count += 1
                        file_changed = True

        if file_changed:
            save_schedule_file(schedule_file)
    return updated_count


def process_images(dry_run: bool = False) -> int:
    if not dry_run and not configured_images_enabled():
        print(
            "Image processing is disabled by "
            "config/service.yml posting.enable_images."
        )
        return 0

    images = iter_images()
    if not images:
        print("No incoming images found.")
        return 0

    try:
        validate_unique_image_keys(images)
    except ValueError as exc:
        print(f"Image validation failed: {exc}")
        return 1

    output_dir: Path | None = None
    if not dry_run:
        if not ASSET_REPO_DIR.exists():
            raise RuntimeError(
                "The assets repository checkout was not found at assets-repo/."
            )
        output_dir = ASSET_REPO_DIR / asset_subdirectory()

    failures = 0
    for image_path in images:
        image_key = image_path.stem
        print(f"Processing image_key={image_key}")
        try:
            image_format, width, height, size_bytes = inspect_image(image_path)
            print(
                f"Validated image: format={image_format} "
                f"size={width}x{height} bytes={size_bytes}"
            )
            if dry_run:
                print("Dry run. No file or YAML was changed.")
                continue

            if output_dir is None:
                raise RuntimeError("Public image output directory is unavailable.")
            webp_path = convert_to_webp(image_path, output_dir)
            relative_path = str(
                asset_subdirectory() / webp_path.name
            ).replace("\\", "/")
            url = raw_url(relative_path)
            matches = update_schedules(image_key, url, relative_path)
            upsert_asset_log(
                image_key,
                image_path,
                url,
                relative_path,
                matches,
            )
            print(f"Created: assets-repo/{relative_path}")
            print(f"Schedule matches: {matches}")
            print("Post status was not changed. Approval remains manual.")
            image_path.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"Image processing failed for {image_path.name}: {exc}")

    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(process_images(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
