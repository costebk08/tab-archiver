"""Start at login helpers for Windows, macOS, and Linux."""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

from app.config import APP_NAME, is_frozen


def _launch_target() -> tuple[str, list[str]]:
    if is_frozen():
        return sys.executable, []
    project_root = Path(__file__).resolve().parent.parent
    launcher = project_root / "launch.py"
    return sys.executable, [str(launcher)]


def is_start_at_login_enabled() -> bool:
    if sys.platform == "win32":
        return _windows_shortcut_path().exists()
    if sys.platform == "darwin":
        return _macos_plist_path().exists()
    return _linux_desktop_path().exists()


def set_start_at_login(enabled: bool) -> None:
    if enabled:
        _enable_start_at_login()
    else:
        _disable_start_at_login()


def _enable_start_at_login() -> None:
    if sys.platform == "win32":
        _enable_windows()
        return
    if sys.platform == "darwin":
        _enable_macos()
        return
    _enable_linux()


def _disable_start_at_login() -> None:
    if sys.platform == "win32":
        path = _windows_shortcut_path()
        if path.exists():
            path.unlink()
        return
    if sys.platform == "darwin":
        path = _macos_plist_path()
        if path.exists():
            path.unlink()
        return
    path = _linux_desktop_path()
    if path.exists():
        path.unlink()


def _windows_shortcut_path() -> Path:
    startup = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    return startup / f"{APP_NAME}.bat"


def _enable_windows() -> None:
    shortcut = _windows_shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    executable, arguments = _launch_target()
    if arguments:
        command = f'"{executable}" {" ".join(arguments)}'
    else:
        command = f'"{executable}"'
    shortcut.write_text(f'@echo off\r\nstart "" {command}\r\n', encoding="utf-8")


def _macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.tabarchiver.app.plist"


def _enable_macos() -> None:
    executable, arguments = _launch_target()
    plist_path = _macos_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    program_args = [executable, *arguments]
    payload = {
        "Label": "com.tabarchiver.app",
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        "KeepAlive": False,
    }
    with open(plist_path, "wb") as file:
        plistlib.dump(payload, file)


def _linux_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / "tab-archiver.desktop"


def _enable_linux() -> None:
    executable, arguments = _launch_target()
    desktop_path = _linux_desktop_path()
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join([executable, *arguments])
    desktop_path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={APP_NAME}",
                f"Exec={exec_line}",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
