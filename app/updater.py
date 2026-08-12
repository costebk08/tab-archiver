"""Check GitHub Releases for newer versions."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from app.config import APP_VERSION, GITHUB_REPO, RELEASES_PAGE_URL


def _parse_version(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lstrip("v")
    parts: list[int] = []
    for piece in cleaned.split("."):
        match = re.match(r"(\d+)", piece)
        parts.append(int(match.group(1)) if match else 0)
    return tuple(parts)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _pick_asset_url(release: dict[str, Any]) -> str | None:
    assets = release.get("assets") or []
    preferred_names = (
        "Tab-Archiver-Windows.zip",
        "Tab-Archiver-macOS.dmg",
        "Tab-Archiver-Linux.tar.gz",
    )
    for preferred in preferred_names:
        for asset in assets:
            if asset.get("name") == preferred:
                return asset.get("browser_download_url")
    if assets:
        return assets[0].get("browser_download_url")
    return release.get("html_url")


def check_for_updates(timeout: float = 4.0) -> dict[str, Any] | None:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "TabArchiver",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            release = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None

    latest_version = str(release.get("tag_name", "")).lstrip("v")
    if not latest_version or not _is_newer(latest_version, APP_VERSION):
        return None

    return {
        "update_available": True,
        "current_version": APP_VERSION,
        "latest_version": latest_version,
        "release_page_url": release.get("html_url") or RELEASES_PAGE_URL,
        "download_url": _pick_asset_url(release) or RELEASES_PAGE_URL,
        "release_notes": release.get("body") or "",
    }
