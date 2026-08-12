"""Parse Chromium SNSS session files to extract open tab URLs."""

from __future__ import annotations

import os
import re
import struct
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


class InvalidSNSSFileException(Exception):
    pass


TAB_CLOSED_COMMANDS = {3, 16}
WINDOW_CLOSED_COMMANDS = {4, 17}
NAVIGATION_COMMANDS = {5, 6, 15}
HTTP_URL_PATTERN = re.compile(rb"https?://[^\x00\r\n\t \"<>]{4,}")


@dataclass
class TabInfo:
    tab_id: int
    url: str
    title: str


class SNSSCommand:
    def __init__(self, command_id: int, content: bytes):
        self.id = command_id
        self.content = content


def parse_snss_file(path: Path) -> list[SNSSCommand]:
    commands: list[SNSSCommand] = []
    with open(path, "rb") as file:
        file.seek(0, os.SEEK_END)
        end = file.tell()
        file.seek(0, os.SEEK_SET)

        signature = struct.unpack("i", file.read(4))[0]
        if signature != 0x53534E53:
            raise InvalidSNSSFileException(f"Invalid SNSS file: {path}")

        struct.unpack("i", file.read(4))

        while end - file.tell() > 0:
            command_size = struct.unpack("H", file.read(2))[0]
            if command_size == 0:
                break
            command_id = struct.unpack("B", file.read(1))[0]
            content = file.read(command_size - 1)
            commands.append(SNSSCommand(command_id, content))

    return commands


def _read_uint32(content: bytes, offset: int = 0) -> int | None:
    if len(content) < offset + 4:
        return None
    return struct.unpack("I", content[offset : offset + 4])[0]


def _parse_update_tab_navigation(content: bytes) -> tuple[int, str, str] | None:
    stream = BytesIO(content)
    stream.seek(0, os.SEEK_END)
    pickle_size = stream.tell()
    stream.seek(0, os.SEEK_SET)

    if pickle_size < 12:
        return None

    struct.unpack("I", stream.read(4))
    tab_id = struct.unpack("I", stream.read(4))[0]
    struct.unpack("I", stream.read(4))

    def read_str8() -> str:
        str_length = struct.unpack("I", stream.read(4))[0]
        padding = 4 - (str_length % 4) if str_length % 4 else 0
        if str_length > pickle_size - stream.tell():
            return ""
        raw = stream.read(str_length + padding)[:str_length]
        return raw.decode("utf-8", errors="ignore")

    def read_str16() -> str:
        str_length = struct.unpack("I", stream.read(4))[0] * 2
        padding = 4 - (str_length % 4) if str_length % 4 else 0
        if str_length > pickle_size - stream.tell():
            return ""
        raw = stream.read(str_length + padding)[:str_length]
        return raw.decode("utf-16", errors="ignore")

    url = read_str8()
    title = read_str16()
    return tab_id, url, title


def _is_valid_web_url(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith(("chrome://", "edge://", "about:", "devtools://", "brave://")):
        return False
    return lowered.startswith(("http://", "https://", "file://"))


def _extract_urls_from_content(content: bytes) -> list[str]:
    urls: list[str] = []
    for match in HTTP_URL_PATTERN.finditer(content):
        url = match.group(0).decode("utf-8", errors="ignore").rstrip("\\")
        if _is_valid_web_url(url):
            urls.append(url)
    return urls


def _dedupe_tabs(tabs: list[TabInfo]) -> list[TabInfo]:
    seen: set[str] = set()
    unique: list[TabInfo] = []
    for tab in tabs:
        if tab.url in seen:
            continue
        seen.add(tab.url)
        unique.append(tab)
    return unique


def extract_tabs_from_commands(
    commands: list[SNSSCommand],
    *,
    respect_close_events: bool = True,
) -> list[TabInfo]:
    open_tabs: dict[int, TabInfo] = {}
    tab_to_window: dict[int, int] = {}
    window_tabs: dict[int, set[int]] = defaultdict(set)
    synthetic_id = 1_000_000

    for command in commands:
        if command.id == 0:
            tab_id = _read_uint32(command.content, 0)
            window_id = _read_uint32(command.content, 4)
            if tab_id is None or window_id is None:
                continue
            tab_to_window[tab_id] = window_id
            window_tabs[window_id].add(tab_id)
            continue

        if command.id in NAVIGATION_COMMANDS:
            parsed = _parse_update_tab_navigation(command.content)
            if parsed:
                tab_id, url, title = parsed
                if _is_valid_web_url(url):
                    open_tabs[tab_id] = TabInfo(tab_id=tab_id, url=url, title=title or url)
                else:
                    open_tabs.pop(tab_id, None)
            else:
                for url in _extract_urls_from_content(command.content):
                    open_tabs[synthetic_id] = TabInfo(
                        tab_id=synthetic_id,
                        url=url,
                        title=url,
                    )
                    synthetic_id += 1
            continue

        if not respect_close_events:
            continue

        if command.id in TAB_CLOSED_COMMANDS:
            tab_id = _read_uint32(command.content, 0)
            if tab_id is None:
                continue
            open_tabs.pop(tab_id, None)
            window_id = tab_to_window.pop(tab_id, None)
            if window_id is not None:
                window_tabs[window_id].discard(tab_id)
            continue

        if command.id in WINDOW_CLOSED_COMMANDS:
            window_id = _read_uint32(command.content, 0)
            if window_id is None:
                continue
            for tab_id in list(window_tabs.get(window_id, set())):
                open_tabs.pop(tab_id, None)
                tab_to_window.pop(tab_id, None)
            window_tabs.pop(window_id, None)

    return _dedupe_tabs(list(open_tabs.values()))


def extract_tabs_from_session_path(path: Path) -> list[TabInfo]:
    commands = parse_snss_file(path)
    for respect_close_events in (False, True):
        tabs = extract_tabs_from_commands(commands, respect_close_events=respect_close_events)
        if tabs:
            return tabs
    return []


def extract_tabs_from_session_commands(commands: list[SNSSCommand]) -> list[TabInfo]:
    if not commands:
        return []

    for respect_close_events in (False, True):
        tabs = extract_tabs_from_commands(commands, respect_close_events=respect_close_events)
        if tabs:
            return tabs
    return []
