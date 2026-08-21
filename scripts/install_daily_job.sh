#!/bin/bash
# Install a macOS launchd job that refreshes datasets, audits, RAG, and trends at 08:15.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.ragprediction.dailybrief"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$ROOT/data/processed/daily"
PYTHON="$(command -v python3)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${ROOT}/scripts/run_daily_brief.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>15</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${ROOT}/data/processed/daily/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/data/processed/daily/launchd.err.log</string>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed ${PLIST}"
echo "Runs daily at 08:15 (and once now). Refreshes products/events/trends, audits date changes, and retrains RAG."
echo "Output: ${ROOT}/data/processed/daily/"
