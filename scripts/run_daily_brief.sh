#!/bin/bash
# Daily job: refresh product/event/trend datasets, run audits, retrain RAG.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi
mkdir -p "$ROOT/data/processed/daily"
echo "[$(date -Iseconds)] starting daily refresh" >> "$ROOT/data/processed/daily/launchd.out.log"
"$PY" -m src.daily_brief --refresh
echo "[$(date -Iseconds)] daily refresh complete" >> "$ROOT/data/processed/daily/launchd.out.log"
