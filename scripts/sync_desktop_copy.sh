#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${DESKTOP_COPY:-$HOME/Desktop/RAGPredictionGameProject}"
ZIP="${DEST}.zip"

if [[ "$ROOT" == "$DEST" ]]; then
  echo "Workspace is already the Desktop copy; skip."
  exit 0
fi

mkdir -p "$DEST"
rsync -a --delete \
  --exclude '.venv/' \
  --exclude 'build/' \
  --exclude 'dist/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '.DS_Store' \
  "$ROOT/" "$DEST/"

ditto -c -k --sequesterRsrc --keepParent "$DEST" "$ZIP"
echo "Mirrored $ROOT → $DEST"
echo "Zip $ZIP"
