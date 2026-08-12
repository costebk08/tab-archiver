"""Detect running browsers and extract open tabs."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from app.platform_config import (
    BrowserDefinition,
    get_browser_definitions,
    local_state_path,
    resolve_browser_executable,
)
from app.snss_parser import TabInfo, extract_tabs_from_session_path


@dataclass
class BrowserInstance:
    id: str
    display_name: str
    browser_key: str
    profile_path: Path | None
    executable: str | None = None
    tabs: list[TabInfo] = field(default_factory=list)


def _get_process_command_line(process: psutil.Process) -> str:
    try:
        return " ".join(process.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return ""


def _process_name_matches(process_name: str, allowed_names: set[str]) -> bool:
    return process_name.lower() in allowed_names


def _is_private_browsing_process(command_line: str, browser_key: str) -> bool:
    lowered = command_line.lower()
    if browser_key == "edge":
        return "--inprivate" in lowered
    if browser_key in {"chrome", "brave"}:
        return "--incognito" in lowered
    if browser_key == "firefox":
        return "-private-window" in lowered or "-private" in lowered
    return False


def _has_regular_browser_process(browser_key: str, definition: BrowserDefinition) -> bool:
    allowed_names = set(definition.process_names)
    for process in psutil.process_iter(["name", "cmdline"]):
        name = process.info.get("name") or ""
        if not _process_name_matches(name, allowed_names):
            continue
        cmdline = _get_process_command_line(process)
        if not _is_private_browsing_process(cmdline, browser_key):
            return True
    return False


def _load_profile_info(user_data_root: Path) -> dict[str, str]:
    state_path = local_state_path(user_data_root)
    if not state_path:
        return {}

    try:
        with open(state_path, encoding="utf-8") as file:
            data = json.load(file)
        info_cache = data.get("profile", {}).get("info_cache", {})
        return {name: profile.get("name", name) for name, profile in info_cache.items()}
    except (OSError, json.JSONDecodeError):
        return {}


def _copy_session_file(source: Path) -> Path | None:
    if not source.exists():
        return None

    temp_dir = Path(tempfile.gettempdir()) / "tab-archiver-sessions"
    temp_dir.mkdir(parents=True, exist_ok=True)
    destination = temp_dir / f"{source.name}-{os.getpid()}.copy"

    try:
        shutil.copy2(source, destination)
        return destination
    except OSError:
        return None


def _extract_chromium_tabs(profile_path: Path) -> list[TabInfo]:
    sessions_dir = profile_path / "Sessions"
    if not sessions_dir.exists():
        return []

    session_candidates = [
        sessions_dir / "Current Tabs",
        sessions_dir / "Current Session",
    ]

    for session_file in session_candidates:
        copied = _copy_session_file(session_file)
        if not copied:
            continue
        try:
            tabs = extract_tabs_from_session_path(copied)
            if tabs:
                return tabs
        except Exception:
            continue

    return []


def _extract_recent_history_tabs(profile_path: Path, limit: int = 40) -> list[TabInfo]:
    """Legacy fallback kept for diagnostics; not used in normal tab discovery."""
    history_file = profile_path / "History"
    copied = _copy_session_file(history_file)
    if not copied:
        return []

    tabs: list[TabInfo] = []
    try:
        connection = sqlite3.connect(f"file:{copied}?mode=ro", uri=True)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT DISTINCT urls.url, urls.title
            FROM urls
            INNER JOIN visits ON urls.id = visits.url
            ORDER BY visits.visit_time DESC
            LIMIT ?
            """,
            (limit,),
        )
        for index, (url, title) in enumerate(cursor.fetchall(), start=1):
            if url and not url.startswith(("chrome://", "edge://", "about:", "devtools://")):
                tabs.append(TabInfo(tab_id=index, url=url, title=title or url))
        connection.close()
    except sqlite3.Error:
        return []

    return tabs


def _extract_firefox_tabs(profiles_root: Path) -> list[TabInfo]:
    if not profiles_root.exists():
        return []

    tabs: dict[str, TabInfo] = {}
    for profile_dir in profiles_root.iterdir():
        if not profile_dir.is_dir():
            continue

        session_file = profile_dir / "sessionstore.jsonlz4"
        if session_file.exists():
            extracted = _parse_firefox_session(session_file)
            for tab in extracted:
                tabs[tab.url] = tab
            continue

        recovery_file = profile_dir / "sessionstore-backups" / "recovery.jsonlz4"
        if recovery_file.exists():
            extracted = _parse_firefox_session(recovery_file)
            for tab in extracted:
                tabs[tab.url] = tab

    return list(tabs.values())


def _parse_firefox_session(path: Path) -> list[TabInfo]:
    try:
        import lz4.block
    except ImportError:
        return _parse_firefox_session_plain(path)

    try:
        raw = path.read_bytes()
        if raw[:8] != b"mozLz40\0":
            return []
        decompressed = lz4.block.decompress(raw[8:])
        data = json.loads(decompressed.decode("utf-8"))
    except Exception:
        return []

    return _walk_firefox_windows(data.get("windows", []))


def _parse_firefox_session_plain(path: Path) -> list[TabInfo]:
    try:
        raw = path.read_bytes()
        if raw[:8] != b"mozLz40\0":
            return []
        text = raw[8:].decode("utf-8", errors="ignore")
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return []
        data = json.loads(text[start : end + 1])
    except Exception:
        return []

    return _walk_firefox_windows(data.get("windows", []))


def _walk_firefox_windows(windows: list) -> list[TabInfo]:
    tabs: list[TabInfo] = []
    tab_id = 0

    for window in windows:
        if bool(window.get("isPrivate")):
            continue

        for entry in window.get("tabs", []):
            entries = entry.get("entries", [])
            if not entries:
                continue
            last = entries[-1]
            url = last.get("url", "")
            title = last.get("title") or url
            if url and not url.startswith("about:"):
                tab_id += 1
                tabs.append(TabInfo(tab_id=tab_id, url=url, title=title))

    return tabs


def _discover_chromium_profiles(
    browser_key: str,
    definition: BrowserDefinition,
) -> list[tuple[str, Path]]:
    user_data_root = definition.user_data_root
    if not user_data_root or not user_data_root.exists():
        return []

    profile_names = _load_profile_info(user_data_root)
    running_profiles: set[str] = set()
    allowed_names = set(definition.process_names)

    for process in psutil.process_iter(["name", "cmdline"]):
        name = process.info.get("name") or ""
        if not _process_name_matches(name, allowed_names):
            continue

        cmdline = _get_process_command_line(process)
        if _is_private_browsing_process(cmdline, browser_key):
            continue

        profile_dir = "Default"
        match = re.search(r'--profile-directory=(?:["\'])?([^"\']+)', cmdline)
        if match:
            profile_dir = match.group(1).strip()
        running_profiles.add(profile_dir)

    if not running_profiles:
        return []

    candidate_dirs = set(running_profiles)
    for profile_dir in profile_names:
        if (user_data_root / profile_dir / "Sessions").exists():
            candidate_dirs.add(profile_dir)
    for profile_path in user_data_root.iterdir():
        if profile_path.is_dir() and (profile_path / "Sessions").exists():
            candidate_dirs.add(profile_path.name)

    discovered: list[tuple[str, Path]] = []
    for profile_dir in sorted(candidate_dirs):
        profile_path = user_data_root / profile_dir
        if not profile_path.exists():
            continue
        label = profile_names.get(profile_dir, profile_dir)
        discovered.append((label, profile_path))

    return discovered


def _build_display_name(base_name: str, profile_label: str) -> str:
    if profile_label and profile_label.lower() not in {"default", base_name.lower()}:
        return f"{base_name} ({profile_label})"
    return base_name


def _make_browser_id(browser_key: str, profile_label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", profile_label.lower()).strip("-")
    parts = [browser_key]
    if slug and slug != "default":
        parts.append(slug)
    return "-".join(parts)


def discover_open_browsers() -> list[BrowserInstance]:
    browsers: list[BrowserInstance] = []

    for browser_key, definition in get_browser_definitions().items():
        if not _has_regular_browser_process(browser_key, definition):
            continue

        executable = resolve_browser_executable(definition)

        if browser_key == "firefox":
            profiles_root = definition.firefox_profiles_root
            if not profiles_root:
                continue
            tabs = _extract_firefox_tabs(profiles_root)
            if not tabs:
                continue
            display_name = _build_display_name(definition.display_name, "Default")
            browsers.append(
                BrowserInstance(
                    id=_make_browser_id(browser_key, "Default"),
                    display_name=display_name,
                    browser_key=browser_key,
                    profile_path=None,
                    executable=executable,
                    tabs=tabs,
                )
            )
            continue

        for profile_label, profile_path in _discover_chromium_profiles(browser_key, definition):
            tabs = _extract_chromium_tabs(profile_path)
            if not tabs:
                continue

            display_name = _build_display_name(definition.display_name, profile_label)
            browsers.append(
                BrowserInstance(
                    id=_make_browser_id(browser_key, profile_label),
                    display_name=display_name,
                    browser_key=browser_key,
                    profile_path=profile_path,
                    executable=executable,
                    tabs=tabs,
                )
            )

    return browsers


def get_browser_by_id(browser_id: str) -> BrowserInstance | None:
    for browser in discover_open_browsers():
        if browser.id == browser_id:
            return browser
    return None


def archive_all_open_browsers() -> dict[str, object]:
    from app.storage import archive_tabs

    browsers = discover_open_browsers()
    archived: list[dict[str, object]] = []
    total_tabs = 0
    date_value = ""

    for browser in browsers:
        tab_payload = [{"url": tab.url, "title": tab.title} for tab in browser.tabs]
        if not tab_payload:
            continue
        day_entry = archive_tabs(
            browser_id=browser.id,
            browser_name=browser.display_name,
            browser_key=browser.browser_key,
            executable=browser.executable,
            tabs=tab_payload,
        )
        date_value = day_entry["date"]
        total_tabs += len(tab_payload)
        archived.append(
            {
                "browser_id": browser.id,
                "browser_name": browser.display_name,
                "tab_count": len(tab_payload),
            }
        )

    return {
        "success": bool(archived),
        "date": date_value,
        "browser_count": len(archived),
        "total_tabs": total_tabs,
        "browsers": archived,
    }
