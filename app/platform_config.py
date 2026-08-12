"""Cross-platform browser paths, process names, and executables."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrowserDefinition:
    key: str
    display_name: str
    process_names: frozenset[str]
    user_data_root: Path | None = None
    firefox_profiles_root: Path | None = None
    executable_candidates: tuple[Path, ...] = ()
    executable_commands: tuple[str, ...] = ()


def _home() -> Path:
    return Path.home()


def _windows_program_files() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value))
    return candidates


def _windows_chromium_definition(
    key: str,
    display_name: str,
    process_name: str,
    user_data_parts: tuple[str, ...],
    exe_parts: tuple[str, ...],
) -> BrowserDefinition:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    user_data_root = local_app_data.joinpath(*user_data_parts, "User Data")

    executable_candidates: list[Path] = []
    for root in _windows_program_files():
        executable_candidates.append(root.joinpath(*exe_parts))

    return BrowserDefinition(
        key=key,
        display_name=display_name,
        process_names=frozenset({process_name.lower()}),
        user_data_root=user_data_root,
        executable_candidates=tuple(executable_candidates),
        executable_commands=tuple(),
    )


def _mac_chromium_definition(
    key: str,
    display_name: str,
    process_name: str,
    support_parts: tuple[str, ...],
    app_name: str,
    binary_name: str,
) -> BrowserDefinition:
    user_data_root = _home() / "Library" / "Application Support" / Path(*support_parts)
    app_path = Path("/Applications") / f"{app_name}.app" / "Contents" / "MacOS" / binary_name

    return BrowserDefinition(
        key=key,
        display_name=display_name,
        process_names=frozenset({process_name.lower()}),
        user_data_root=user_data_root,
        executable_candidates=(app_path,),
        executable_commands=tuple(),
    )


def _linux_chromium_definition(
    key: str,
    display_name: str,
    process_names: tuple[str, ...],
    config_parts: tuple[str, ...],
    executable_commands: tuple[str, ...],
) -> BrowserDefinition:
    user_data_root = _home() / ".config" / Path(*config_parts)

    return BrowserDefinition(
        key=key,
        display_name=display_name,
        process_names=frozenset(name.lower() for name in process_names),
        user_data_root=user_data_root,
        executable_candidates=tuple(),
        executable_commands=executable_commands,
    )


def _firefox_definition(
    process_names: tuple[str, ...],
    profiles_root: Path,
    executable_candidates: tuple[Path, ...] = (),
    executable_commands: tuple[str, ...] = ("firefox",),
) -> BrowserDefinition:
    return BrowserDefinition(
        key="firefox",
        display_name="Firefox",
        process_names=frozenset(name.lower() for name in process_names),
        firefox_profiles_root=profiles_root,
        executable_candidates=executable_candidates,
        executable_commands=executable_commands,
    )


def get_browser_definitions() -> dict[str, BrowserDefinition]:
    if sys.platform == "win32":
        return {
            "chrome": _windows_chromium_definition(
                "chrome",
                "Chrome",
                "chrome.exe",
                ("Google", "Chrome"),
                ("Google", "Chrome", "Application", "chrome.exe"),
            ),
            "edge": _windows_chromium_definition(
                "edge",
                "Edge",
                "msedge.exe",
                ("Microsoft", "Edge"),
                ("Microsoft", "Edge", "Application", "msedge.exe"),
            ),
            "brave": _windows_chromium_definition(
                "brave",
                "Brave",
                "brave.exe",
                ("BraveSoftware", "Brave-Browser"),
                ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            ),
            "firefox": _firefox_definition(
                ("firefox.exe",),
                Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles",
                executable_candidates=(
                    Path(os.environ.get("PROGRAMFILES", "")) / "Mozilla Firefox" / "firefox.exe",
                    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Mozilla Firefox" / "firefox.exe",
                ),
            ),
        }

    if sys.platform == "darwin":
        return {
            "chrome": _mac_chromium_definition(
                "chrome",
                "Chrome",
                "Google Chrome",
                ("Google", "Chrome"),
                "Google Chrome",
                "Google Chrome",
            ),
            "edge": _mac_chromium_definition(
                "edge",
                "Edge",
                "Microsoft Edge",
                ("Microsoft Edge",),
                "Microsoft Edge",
                "Microsoft Edge",
            ),
            "brave": _mac_chromium_definition(
                "brave",
                "Brave",
                "Brave Browser",
                ("BraveSoftware", "Brave-Browser"),
                "Brave Browser",
                "Brave Browser",
            ),
            "firefox": _firefox_definition(
                ("firefox",),
                _home() / "Library" / "Application Support" / "Firefox" / "Profiles",
                executable_candidates=(
                    Path("/Applications/Firefox.app/Contents/MacOS/firefox"),
                ),
            ),
        }

    return {
        "chrome": _linux_chromium_definition(
            "chrome",
            "Chrome",
            ("chrome", "google-chrome", "google-chrome-stable"),
            ("google-chrome",),
            ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"),
        ),
        "edge": _linux_chromium_definition(
            "edge",
            "Edge",
            ("msedge", "microsoft-edge", "microsoft-edge-stable"),
            ("microsoft-edge",),
            ("microsoft-edge", "microsoft-edge-stable"),
        ),
        "brave": _linux_chromium_definition(
            "brave",
            "Brave",
            ("brave", "brave-browser"),
            ("BraveSoftware", "Brave-Browser"),
            ("brave-browser", "brave"),
        ),
        "firefox": _firefox_definition(
            ("firefox", "firefox-esr"),
            _home() / ".mozilla" / "firefox",
        ),
    }


def resolve_browser_executable(definition: BrowserDefinition) -> str | None:
    for candidate in definition.executable_candidates:
        if candidate.exists():
            return str(candidate)

    for command in definition.executable_commands:
        resolved = shutil.which(command)
        if resolved:
            return resolved

    return None


def local_state_path(user_data_root: Path) -> Path | None:
    for candidate in (user_data_root / "Local State", user_data_root.parent / "Local State"):
        if candidate.exists():
            return candidate
    return None
