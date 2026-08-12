"""Local JSON storage for archived tab history."""

from __future__ import annotations

import json
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".tab-archiver"
HISTORY_FILE = DATA_DIR / "history.json"

_lock = threading.Lock()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_history() -> dict[str, Any]:
    _ensure_data_dir()
    if not HISTORY_FILE.exists():
        return {"archives": {}}

    try:
        with open(HISTORY_FILE, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"archives": {}}


def _save_history(data: dict[str, Any]) -> None:
    _ensure_data_dir()
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def get_history() -> dict[str, Any]:
    with _lock:
        return _load_history()


def archive_tabs(
    browser_id: str,
    browser_name: str,
    browser_key: str,
    executable: str | None,
    tabs: list[dict[str, str]],
) -> dict[str, Any]:
    today = date.today().isoformat()
    timestamp = datetime.now().isoformat(timespec="seconds")

    with _lock:
        data = _load_history()
        archives = data.setdefault("archives", {})
        day_entry = archives.setdefault(
            today,
            {"date": today, "browsers": {}},
        )
        browsers = day_entry.setdefault("browsers", {})

        existing = browsers.get(browser_id, {
            "browser_id": browser_id,
            "browser_name": browser_name,
            "browser_key": browser_key,
            "executable": executable,
            "archives": [],
        })

        existing["browser_name"] = browser_name
        existing["browser_key"] = browser_key
        existing["executable"] = executable
        existing.setdefault("archives", []).append(
            {
                "archived_at": timestamp,
                "tabs": tabs,
            }
        )

        merged_tabs: dict[str, dict[str, str]] = {}
        for archive in existing["archives"]:
            for tab in archive.get("tabs", []):
                merged_tabs[tab["url"]] = tab

        existing["tabs"] = list(merged_tabs.values())
        browsers[browser_id] = existing
        _save_history(data)

        return day_entry
