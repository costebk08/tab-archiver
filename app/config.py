"""Application metadata and portable path resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Tab Archiver"
APP_VERSION = "1.2.1"
GITHUB_REPO = os.environ.get("TAB_ARCHIVER_GITHUB_REPO", "costebk08/tab-archiver")
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_install_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", get_install_root()))
    return Path(__file__).resolve().parent.parent


STATIC_DIR = get_resource_root() / "static"
SETTINGS_DIR = Path.home() / ".tab-archiver"
