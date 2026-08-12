@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo Python 3.10 or newer is required but was not found on your PATH.
        echo Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    py -3 launch.py
) else (
    python launch.py
)

exit /b %ERRORLEVEL%
