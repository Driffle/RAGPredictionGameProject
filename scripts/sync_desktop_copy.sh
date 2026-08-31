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
  --exclude 'data/processed/rag/tfidf_index.joblib' \
  --exclude 'data/processed/rag/corpus.jsonl' \
  --exclude 'data/processed/rag/corpus.jsonl.gz' \
  --exclude 'data/processed/promotion_calendar.csv' \
  --exclude 'data/processed/promotion_calendar.csv.gz' \
  --exclude 'data/raw/game_products.csv' \
  "$ROOT/" "$DEST/"

ditto -c -k --sequesterRsrc --keepParent "$DEST" "$ZIP"
echo "Mirrored $ROOT → $DEST"
echo "Zip $ZIP"
