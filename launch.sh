#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 launch.py
fi

if command -v python >/dev/null 2>&1; then
  exec python launch.py
fi

echo "Python 3.10 or newer is required but was not found on your PATH."
exit 1
