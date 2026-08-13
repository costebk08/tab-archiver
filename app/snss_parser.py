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


def _read_stream_uint32(stream: BytesIO, end: int) -> int | None:
    if stream.tell() + 4 > end:
        return None
    data = stream.read(4)
    if len(data) != 4:
        return None
    return struct.unpack("I", data)[0]


def _read_stream_str8(stream: BytesIO, end: int) -> str:
    str_length = _read_stream_uint32(stream, end)
    if str_length is None or str_length < 0:
        return ""
    padding = 4 - (str_length % 4) if str_length % 4 else 0
    if stream.tell() + str_length + padding > end:
        return ""
    raw = stream.read(str_length + padding)[:str_length]
    return raw.decode("utf-8", errors="ignore")


def _read_stream_str16(stream: BytesIO, end: int) -> str:
    str_units = _read_stream_uint32(stream, end)
    if str_units is None or str_units < 0:
        return ""
    str_length = str_units * 2
    padding = 4 - (str_length % 4) if str_length % 4 else 0
    if stream.tell() + str_length + padding > end:
        return ""
    raw = stream.read(str_length + padding)[:str_length]
    return raw.decode("utf-16", errors="ignore")


def _parse_update_tab_navigation(content: bytes) -> tuple[int, str, str] | None:
    try:
        stream = BytesIO(content)
        end = len(content)
        if end < 12:
            return None

        if _read_stream_uint32(stream, end) is None:
            return None
        tab_id = _read_stream_uint32(stream, end)
        if tab_id is None:
            return None
        if _read_stream_uint32(stream, end) is None:
            return None

        url = _read_stream_str8(stream, end)
        title = _read_stream_str16(stream, end)
        if not url:
            return None
        return tab_id, url, title or url
    except struct.error:
        return None


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
            try:
                parsed = _parse_update_tab_navigation(command.content)
            except (struct.error, ValueError, IndexError):
                parsed = None

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
