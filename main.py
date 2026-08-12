"""Tab Archiver - local web app for archiving and reopening browser tabs."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.autostart import is_start_at_login_enabled, set_start_at_login
from app.browser_detection import discover_open_browsers, get_browser_by_id
from app.browser_launcher import open_urls_in_browser
from app.config import APP_VERSION, RELEASES_PAGE_URL, STATIC_DIR, get_install_root
from app.settings import get_settings, save_settings
from app.storage import archive_tabs, get_history
from app.updater import check_for_updates

BASE_DIR = get_install_root()

app = FastAPI(title="Tab Archiver", version=APP_VERSION)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ArchiveRequest(BaseModel):
    browser_id: str
    tabs: list[dict[str, str]] = Field(default_factory=list)


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


@app.post("/api/archive")
def create_archive(payload: ArchiveRequest):
    browser = get_browser_by_id(payload.browser_id)
    if not browser:
        raise HTTPException(status_code=404, detail="Browser not found or no longer running")

    if not payload.tabs:
        raise HTTPException(status_code=400, detail="No tabs selected for archive")

    day_entry = archive_tabs(
        browser_id=browser.id,
        browser_name=browser.display_name,
        browser_key=browser.browser_key,
        executable=browser.executable,
        tabs=payload.tabs,
    )

    return {"success": True, "date": day_entry["date"]}


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
        if is_tab_archiver_running(port):
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
