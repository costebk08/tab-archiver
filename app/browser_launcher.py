"""Launch URLs in the appropriate browser."""

from __future__ import annotations

import shutil
import subprocess
import sys

from app.platform_config import get_browser_definitions, resolve_browser_executable


def open_urls_in_browser(
    browser_key: str,
    urls: list[str],
    executable: str | None,
) -> None:
    if not urls:
        return

    exe = executable
    if not exe:
        definition = get_browser_definitions().get(browser_key)
        if definition:
            exe = resolve_browser_executable(definition)

    if not exe:
        if sys.platform.startswith("linux"):
            for url in urls:
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return
        raise RuntimeError(f"Could not find executable for {browser_key}")

    subprocess.Popen(
        [exe, *urls],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
