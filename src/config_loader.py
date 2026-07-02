"""Load non-secret customer configuration from config/service.yml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "service.yml"


@lru_cache(maxsize=1)
def load_service_config() -> dict[str, Any]:
    """Return the service configuration as a dictionary."""
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Configuration file was not found: {CONFIG_PATH}")

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config/service.yml must contain a YAML mapping.")
    return data


def get_config(*keys: str, default: Any = None) -> Any:
    """Read a nested configuration value."""
    value: Any = load_service_config()
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def service_timezone() -> ZoneInfo:
    """Return the configured IANA timezone."""
    name = str(get_config("service", "timezone", default="Asia/Tokyo")).strip() or "Asia/Tokyo"
    try:
        return ZoneInfo(name)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid service.timezone: {name}") from exc
