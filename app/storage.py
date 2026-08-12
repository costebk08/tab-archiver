"""Local JSON storage for archived tab history."""

from __future__ import annotations

import json
import re
import shutil
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".tab-archiver"
HISTORY_FILE = DATA_DIR / "history.json"
BACKUP_DIR = DATA_DIR / "backups"

_lock = threading.Lock()
_SAVE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,127}$")


class DuplicateSaveNameError(ValueError):
    pass


class InvalidSaveNameError(ValueError):
    pass


class ArchiveNotFoundError(ValueError):
    pass


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_default_save_name() -> str:
    return date.today().strftime("%Y_%m_%d")


def sanitize_save_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip())
    if not cleaned or not _SAVE_NAME_PATTERN.fullmatch(cleaned):
        raise InvalidSaveNameError(
            "Save name must be 1-128 characters and use letters, numbers, spaces, dots, dashes, or underscores."
        )
    return cleaned


def _load_history_raw() -> dict[str, Any]:
    _ensure_data_dir()
    if not HISTORY_FILE.exists():
        return {"archives": {}}

    try:
        with open(HISTORY_FILE, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"archives": {}}

    if not isinstance(data, dict):
        return {"archives": {}}
    data.setdefault("archives", {})
    return data


def _is_legacy_archive_entry(entry: dict[str, Any]) -> bool:
    return isinstance(entry, dict) and "date" in entry and "browsers" in entry


def _migrate_legacy_archives(data: dict[str, Any]) -> dict[str, Any]:
    archives = data.get("archives", {})
    if not isinstance(archives, dict):
        data["archives"] = {}
        return data

    migrated: dict[str, Any] = {}
    changed = False

    for key, entry in archives.items():
        if not _is_legacy_archive_entry(entry):
            migrated[key] = entry
            continue

        changed = True
        default_name = str(entry.get("date", key)).replace("-", "_")
        save_name = _next_available_default_name(default_name, set(migrated.keys()))
        browsers: dict[str, Any] = {}

        for browser_id, browser_entry in (entry.get("browsers") or {}).items():
            tabs = browser_entry.get("tabs") or []
            if not tabs and browser_entry.get("archives"):
                merged: dict[str, dict[str, str]] = {}
                for archive in browser_entry["archives"]:
                    for tab in archive.get("tabs", []):
                        merged[tab["url"]] = tab
                tabs = list(merged.values())

            browsers[browser_id] = {
                "browser_id": browser_entry.get("browser_id", browser_id),
                "browser_name": browser_entry.get("browser_name", browser_id),
                "browser_key": browser_entry.get("browser_key", "chrome"),
                "executable": browser_entry.get("executable"),
                "tabs": tabs,
            }

        migrated[save_name] = {
            "name": save_name,
            "created_at": entry.get("date", date.today().isoformat()),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "browsers": browsers,
        }

    if changed:
        data["archives"] = migrated
        _save_history(data)

    return data


def _save_history(data: dict[str, Any]) -> None:
    _ensure_data_dir()
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def _next_available_default_name(base_name: str, existing_names: set[str]) -> str:
    if base_name not in existing_names:
        return base_name

    index = 1
    while True:
        candidate = f"{base_name}_{index}"
        if candidate not in existing_names:
            return candidate
        index += 1


def resolve_save_name(requested_name: str, *, auto_serialize_default: bool = True) -> str:
    cleaned = sanitize_save_name(requested_name)
    default_name = get_default_save_name()

    with _lock:
        data = _migrate_legacy_archives(_load_history_raw())
        existing_names = set(data.get("archives", {}).keys())

        if cleaned not in existing_names:
            return cleaned

        if auto_serialize_default and cleaned == default_name:
            return _next_available_default_name(cleaned, existing_names)

        raise DuplicateSaveNameError(f'An archive named "{cleaned}" already exists. Choose a different name.')


def get_history() -> dict[str, Any]:
    with _lock:
        return _migrate_legacy_archives(_load_history_raw())


def archive_browser_tabs(
    *,
    save_name: str,
    browser_id: str,
    browser_name: str,
    browser_key: str,
    executable: str | None,
    tabs: list[dict[str, str]],
) -> dict[str, Any]:
    timestamp = datetime.now().isoformat(timespec="seconds")
    cleaned = sanitize_save_name(save_name)

    with _lock:
        data = _migrate_legacy_archives(_load_history_raw())
        archives = data.setdefault("archives", {})

        if cleaned not in archives:
            archives[cleaned] = {
                "name": cleaned,
                "created_at": timestamp,
                "updated_at": timestamp,
                "browsers": {},
            }

        save_entry = archives[cleaned]
        save_entry["updated_at"] = timestamp
        browsers = save_entry.setdefault("browsers", {})
        browsers[browser_id] = {
            "browser_id": browser_id,
            "browser_name": browser_name,
            "browser_key": browser_key,
            "executable": executable,
            "tabs": tabs,
        }
        _save_history(data)
        return save_entry


def delete_archive(save_name: str) -> None:
    cleaned = sanitize_save_name(save_name)

    with _lock:
        data = _migrate_legacy_archives(_load_history_raw())
        archives = data.get("archives", {})
        if cleaned not in archives:
            raise ArchiveNotFoundError(f'Archive "{cleaned}" was not found.')
        del archives[cleaned]
        _save_history(data)


def get_history_file_path() -> Path:
    return HISTORY_FILE


def export_history_backup() -> Path:
    with _lock:
        _ensure_data_dir()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = BACKUP_DIR / f"tab-archiver-backup-{timestamp}.json"

        history = _migrate_legacy_archives(_load_history_raw())
        with open(backup_path, "w", encoding="utf-8") as file:
            json.dump(history, file, indent=2)

        downloads_path = _copy_to_downloads(backup_path, timestamp)
        return downloads_path or backup_path


def _copy_to_downloads(source: Path, timestamp: str) -> Path | None:
    downloads_candidates = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
    ]
    for directory in downloads_candidates:
        if not directory.exists():
            continue
        destination = directory / f"tab-archiver-backup-{timestamp}.json"
        try:
            shutil.copy2(source, destination)
            return destination
        except OSError:
            continue
    return None


def get_latest_backup_path() -> Path | None:
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob("tab-archiver-backup-*.json"), reverse=True)
    return backups[0] if backups else None
