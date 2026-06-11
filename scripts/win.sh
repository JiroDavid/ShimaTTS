#!/usr/bin/env bash
# Dev loop from WSL against the Windows-side checkout (no GitHub round-trip).
# Usage: scripts/win.sh <sync|deps|run|test|smoke|build> [args...]
set -euo pipefail

WIN_DIR="${SHIMA_WIN_DIR:-/mnt/c/Users/jirod/ShimaTTS}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WIN_PY="$WIN_DIR/.venv/Scripts/python.exe"

sync() {
  rsync -a --delete \
    --exclude .git --exclude .venv --exclude dist --exclude build \
    --exclude __pycache__ --exclude .pytest_cache \
    --exclude config.json --exclude ShimaTTS.log --exclude data \
    "$REPO_DIR/" "$WIN_DIR/"
  echo "synced -> $WIN_DIR"
}

require_venv() {
  if [ ! -f "$WIN_PY" ]; then
    echo "No Windows venv at $WIN_PY" >&2
    echo "Create it once from PowerShell:  py -3.11 -m venv C:\\Users\\jirod\\ShimaTTS\\.venv" >&2
    exit 1
  fi
}

cmd="${1:-}"
shift || true

case "$cmd" in
  sync)
    sync
    ;;
  deps)
    require_venv; sync
    cd "$WIN_DIR"
    "$WIN_PY" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
    "$WIN_PY" -m pip install f5-tts --no-deps
    "$WIN_PY" -m pip install -r requirements.txt -r requirements-dev.txt pyinstaller
    ;;
  run)
    require_venv; sync
    cd "$WIN_DIR"
    "$WIN_PY" -m src.main "$@"
    ;;
  test)
    require_venv; sync
    cd "$WIN_DIR"
    "$WIN_PY" -m pytest "$@"
    ;;
  smoke)
    require_venv; sync
    cd "$WIN_DIR"
    "$WIN_PY" -m src.main --smoke
    ;;
  build)
    require_venv; sync
    cd "$WIN_DIR"
    "$WIN_PY" -m PyInstaller --version >/dev/null 2>&1 || "$WIN_PY" -m pip install pyinstaller
    "$WIN_PY" build.py
    echo "exe: $WIN_DIR/dist/ShimaTTS/ShimaTTS.exe"
    ;;
  *)
    echo "Usage: scripts/win.sh <sync|deps|run|test|smoke|build> [args...]" >&2
    exit 1
    ;;
esac
