"""Parse Chromium SNSS session files to extract open tab URLs."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


class InvalidSNSSFileException(Exception):
    pass


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


def extract_tabs_from_commands(commands: list[SNSSCommand]) -> list[TabInfo]:
    tabs_by_id: dict[int, TabInfo] = {}

    for command in commands:
        if command.id != 6:
            continue

        content = BytesIO(command.content)
        content.seek(0, os.SEEK_END)
        pickle_size = content.tell()
        content.seek(0, os.SEEK_SET)

        struct.unpack("I", content.read(4))
        tab_id = struct.unpack("I", content.read(4))[0]
        struct.unpack("I", content.read(4))

        def read_str8() -> str:
            str_length = struct.unpack("I", content.read(4))[0]
            padding = 4 - (str_length % 4) if str_length % 4 else 0
            if str_length > pickle_size - content.tell():
                return ""
            raw = content.read(str_length + padding)[:str_length]
            return raw.decode("utf-8", errors="ignore")

        def read_str16() -> str:
            str_length = struct.unpack("I", content.read(4))[0] * 2
            padding = 4 - (str_length % 4) if str_length % 4 else 0
            if str_length > pickle_size - content.tell():
                return ""
            raw = content.read(str_length + padding)[:str_length]
            return raw.decode("utf-16", errors="ignore")

        url = read_str8()
        title = read_str16()

        if url and not url.startswith(("chrome://", "edge://", "about:", "devtools://")):
            tabs_by_id[tab_id] = TabInfo(tab_id=tab_id, url=url, title=title or url)

    return list(tabs_by_id.values())


def extract_tabs_from_session_path(path: Path) -> list[TabInfo]:
    commands = parse_snss_file(path)
    return extract_tabs_from_commands(commands)
