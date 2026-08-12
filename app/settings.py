"""Persistent user settings."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import SETTINGS_DIR

SETTINGS_FILE = SETTINGS_DIR / "settings.json"
_lock = threading.Lock()


def _default_settings() -> dict[str, Any]:
    return {
        "start_at_login": False,
    }


def get_settings() -> dict[str, Any]:
    with _lock:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        if not SETTINGS_FILE.exists():
            return _default_settings()
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as file:
                data = json.load(file)
            merged = _default_settings()
            merged.update(data)
            return merged
        except (OSError, json.JSONDecodeError):
            return _default_settings()


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        merged = _default_settings()
        merged.update(settings)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
            json.dump(merged, file, indent=2)
        return merged
