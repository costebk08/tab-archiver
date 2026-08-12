"""Tab Archiver - local web app for archiving and reopening browser tabs."""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.autostart import is_start_at_login_enabled, set_start_at_login
from app.browser_detection import archive_all_open_browsers, discover_open_browsers, get_browser_by_id
from app.browser_launcher import open_urls_in_browser
from app.config import APP_VERSION, RELEASES_PAGE_URL, STATIC_DIR, get_install_root
from app.settings import get_settings, save_settings
from app.storage import (
    ArchiveNotFoundError,
    DuplicateSaveNameError,
    InvalidSaveNameError,
    archive_browser_tabs,
    delete_archive,
    export_history_backup,
    get_default_save_name,
    get_history,
    get_history_file_path,
    get_latest_backup_path,
    resolve_save_name,
)
from app.updater import check_for_updates

BASE_DIR = get_install_root()

app = FastAPI(title="Tab Archiver", version=APP_VERSION)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ArchiveRequest(BaseModel):
    browser_id: str
    save_name: str
    tabs: list[dict[str, str]] = Field(default_factory=list)


class ArchiveAllRequest(BaseModel):
    save_name: str


class OpenAllRequest(BaseModel):
    browser_key: str
    executable: str | None = None
    urls: list[str]


class SettingsRequest(BaseModel):
    start_at_login: bool


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/browsers")
def list_browsers():
    browsers = discover_open_browsers()
    return {
        "browsers": [
            {
                "id": browser.id,
                "display_name": browser.display_name,
                "browser_key": browser.browser_key,
                "tab_count": len(browser.tabs),
            }
            for browser in browsers
        ]
    }


@app.get("/api/browsers/{browser_id}/tabs")
def list_browser_tabs(browser_id: str):
    browser = get_browser_by_id(browser_id)
    if not browser:
        raise HTTPException(status_code=404, detail="Browser not found or no longer running")

    return {
        "browser": {
            "id": browser.id,
            "display_name": browser.display_name,
            "browser_key": browser.browser_key,
            "executable": browser.executable,
        },
        "tabs": [
            {"url": tab.url, "title": tab.title}
            for tab in browser.tabs
        ],
    }


@app.get("/api/archive-name/default")
def default_archive_name():
    return {"save_name": get_default_save_name()}


@app.post("/api/archive")
def create_archive(payload: ArchiveRequest):
    browser = get_browser_by_id(payload.browser_id)
    if not browser:
        raise HTTPException(status_code=404, detail="Browser not found or no longer running")

    if not payload.tabs:
        raise HTTPException(status_code=400, detail="No tabs selected for archive")

    try:
        save_name = resolve_save_name(payload.save_name)
    except InvalidSaveNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DuplicateSaveNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    save_entry = archive_browser_tabs(
        save_name=save_name,
        browser_id=browser.id,
        browser_name=browser.display_name,
        browser_key=browser.browser_key,
        executable=browser.executable,
        tabs=payload.tabs,
    )

    return {"success": True, "save_name": save_name, "updated_at": save_entry["updated_at"]}


@app.post("/api/archive-all")
def create_archive_all(payload: ArchiveAllRequest):
    try:
        save_name = resolve_save_name(payload.save_name)
    except InvalidSaveNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DuplicateSaveNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    result = archive_all_open_browsers(save_name)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="No open browsers with detectable tabs were found")

    backup_path = export_history_backup()
    result["backup_path"] = str(backup_path)
    result["backup_filename"] = backup_path.name
    return result


@app.post("/api/export-backup")
def create_export_backup():
    if not get_history_file_path().exists():
        raise HTTPException(status_code=404, detail="No archive history exists yet")

    backup_path = export_history_backup()
    return {
        "success": True,
        "backup_path": str(backup_path),
        "backup_filename": backup_path.name,
    }


@app.get("/api/export-backup/download")
def download_export_backup():
    history_path = get_history_file_path()
    if not history_path.exists():
        raise HTTPException(status_code=404, detail="No archive history exists yet")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return FileResponse(
        history_path,
        media_type="application/json",
        filename=f"tab-archiver-backup-{timestamp}.json",
    )


@app.delete("/api/archives/{save_name}")
def remove_archive(save_name: str):
    try:
        delete_archive(save_name)
    except InvalidSaveNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ArchiveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"success": True, "save_name": save_name}


@app.get("/api/history")
def history():
    return get_history()


@app.get("/api/settings")
def read_settings():
    settings = get_settings()
    return {
        "start_at_login": settings.get("start_at_login", False),
        "start_at_login_active": is_start_at_login_enabled(),
        "version": APP_VERSION,
        "releases_page_url": RELEASES_PAGE_URL,
        "history_file": str(get_history_file_path()),
        "latest_backup_path": str(get_latest_backup_path() or ""),
    }


@app.post("/api/settings")
def write_settings(payload: SettingsRequest):
    save_settings({"start_at_login": payload.start_at_login})
    set_start_at_login(payload.start_at_login)
    return {
        "success": True,
        "start_at_login": payload.start_at_login,
        "start_at_login_active": is_start_at_login_enabled(),
    }


@app.get("/api/update")
def update_status():
    update = check_for_updates()
    if not update:
        return {
            "update_available": False,
            "current_version": APP_VERSION,
            "releases_page_url": RELEASES_PAGE_URL,
        }
    return update


@app.post("/api/open-all")
def open_all(payload: OpenAllRequest):
    if not payload.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")

    try:
        open_urls_in_browser(
            browser_key=payload.browser_key,
            urls=payload.urls,
            executable=payload.executable,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"success": True, "opened": len(payload.urls)}


DEFAULT_PORT = 8765
MAX_PORT = 8775
MIN_FEATURE_VERSION = (1, 1, 0)


def parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in str(version).lstrip("v").split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            break
    return tuple(parts or [0])


def version_at_least(version: str, minimum: tuple[int, ...]) -> bool:
    current = parse_version(version)
    length = max(len(current), len(minimum))
    current = current + (0,) * (length - len(current))
    minimum = minimum + (0,) * (length - len(minimum))
    return current >= minimum


def is_tab_archiver_running(port: int) -> bool:
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/history", timeout=1) as response:
            data = json.loads(response.read().decode("utf-8"))
            return isinstance(data, dict) and "archives" in data
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return False


def get_server_settings(port: int) -> dict | None:
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/settings", timeout=1) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None


def find_stale_instances() -> list[tuple[int, str]]:
    stale: list[tuple[int, str]] = []
    for port in range(DEFAULT_PORT, MAX_PORT + 1):
        if not is_tab_archiver_running(port):
            continue
        settings = get_server_settings(port)
        version = str((settings or {}).get("version") or "unknown")
        if not version_at_least(version, MIN_FEATURE_VERSION):
            stale.append((port, version))
    return stale


def is_port_free(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def find_running_instance() -> int | None:
    for port in range(DEFAULT_PORT, MAX_PORT + 1):
        if not is_tab_archiver_running(port):
            continue
        settings = get_server_settings(port)
        version = str((settings or {}).get("version") or "0")
        if version_at_least(version, MIN_FEATURE_VERSION):
            return port
    return None


def find_available_port() -> int | None:
    for port in range(DEFAULT_PORT, MAX_PORT + 1):
        if is_port_free(port):
            return port
    return None


def print_update_notice() -> None:
    update = check_for_updates()
    if not update:
        return
    print(
        f"A new version is available: {update['latest_version']} "
        f"(you have {APP_VERSION})."
    )
    print(f"Download: {update['release_page_url']}")


def main() -> None:
    import sys
    import threading
    import time
    import webbrowser

    import uvicorn

    os.chdir(BASE_DIR)
    print_update_notice()

    for stale_port, stale_version in find_stale_instances():
        print(
            f"Warning: Tab Archiver v{stale_version} is still running on port {stale_port}. "
            "Close that window so Archive All and Export Backup work correctly."
        )

    running_port = find_running_instance()
    if running_port is not None:
        webbrowser.open(f"http://127.0.0.1:{running_port}")
        print(
            f"Tab Archiver is already running on port {running_port}. "
            "Opened it in your browser."
        )
        return

    port = find_available_port()
    if port is None:
        print(
            f"Could not find an open port between {DEFAULT_PORT} and {MAX_PORT}. "
            "Close other Tab Archiver windows or restart your computer."
        )
        sys.exit(1)

    app_url = f"http://127.0.0.1:{port}"

    def open_browser() -> None:
        time.sleep(1.2)
        webbrowser.open(app_url)

    if port != DEFAULT_PORT:
        print(f"Port {DEFAULT_PORT} is in use. Starting Tab Archiver on port {port} instead.")

    print(f"Tab Archiver {APP_VERSION} running at {app_url}")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
