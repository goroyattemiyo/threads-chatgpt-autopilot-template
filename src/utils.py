"""Common utilities for the Threads autopilot template."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .config_loader import service_timezone

REPO_ROOT = Path(__file__).resolve().parents[1]


def now_local() -> datetime:
    """Return the current datetime in the configured timezone."""
    return datetime.now(service_timezone())


def today_local_str() -> str:
    """Return the configured local date as YYYY-MM-DD."""
    return now_local().strftime("%Y-%m-%d")


def timestamp_local() -> str:
    """Return an ISO timestamp in the configured timezone."""
    return now_local().isoformat(timespec="seconds")


def require_env(name: str) -> str:
    """Read an environment variable or fail without printing its value."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def optional_env(name: str, default: str = "") -> str:
    """Read an optional environment variable."""
    return os.environ.get(name, default).strip()


def repo_path(*parts: str) -> Path:
    """Build a path under the repository root."""
    return REPO_ROOT.joinpath(*parts)


def load_yaml(path: Path, default: Any = None) -> Any:
    """Load YAML and return default when the file is missing or empty."""
    if default is None:
        default = []
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return default
    data = yaml.safe_load(text)
    return default if data is None else data


def save_yaml(path: Path, data: Any) -> None:
    """Save YAML with stable UTF-8 output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def append_yaml_list(path: Path, item: dict[str, Any]) -> None:
    """Append an item to a YAML list file."""
    data = load_yaml(path, default=[])
    if not isinstance(data, list):
        raise ValueError(f"YAML file is not a list: {path}")
    data.append(item)
    save_yaml(path, data)
