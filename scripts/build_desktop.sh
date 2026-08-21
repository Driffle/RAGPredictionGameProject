#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
"$PY" -m pip install -q fastapi uvicorn pywebview pyinstaller
"$PY" -m PyInstaller packaging/floorbrief.spec --noconfirm
echo "Built native app in dist/"
echo "macOS: open dist/FloorBrief.app"
