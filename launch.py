#!/usr/bin/env python3
"""Portable cross-platform launcher for Tab Archiver."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    if sys.platform == "win32":
        return PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    return PROJECT_ROOT / ".venv" / "bin" / "python"


def _find_python() -> str:
    if sys.executable:
        return sys.executable
    for candidate in ("python3", "python"):
        resolved = shutil_which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("Python 3.10 or newer is required but was not found on your PATH.")


def shutil_which(command: str) -> str | None:
    import shutil

    return shutil.which(command)


def _ensure_environment() -> Path:
    os.chdir(PROJECT_ROOT)
    venv_python = _venv_python()

    if venv_python.exists():
        return venv_python

    bootstrap_python = _find_python()
    print("Setting up Tab Archiver for the first time...")
    subprocess.check_call([bootstrap_python, "-m", "venv", str(PROJECT_ROOT / ".venv")])
    subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"])
    return venv_python


def main() -> int:
    try:
        venv_python = _ensure_environment()
    except RuntimeError as error:
        print(error)
        if sys.platform == "win32":
            input("Press Enter to exit...")
        return 1
    except subprocess.CalledProcessError:
        print("Failed to set up Tab Archiver.")
        if sys.platform == "win32":
            input("Press Enter to exit...")
        return 1

    print("Starting Tab Archiver...")
    print("Leave this window open while using the app. Close it to stop the server.")
    print("If you see a message that the app is already running, you can close this window.")
    print()

    result = subprocess.call([str(venv_python), "main.py"], cwd=PROJECT_ROOT)
    if result != 0 and sys.platform == "win32":
        print()
        print("Tab Archiver stopped with an error.")
        input("Press Enter to exit...")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
