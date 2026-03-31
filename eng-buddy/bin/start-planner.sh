#!/bin/bash
# Start the planner background worker as a LaunchAgent
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$HOME/.claude/eng-buddy"
PLIST_NAME="com.eng-buddy.planner"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

mkdir -p "$RUNTIME_DIR"

# Copy planner module to runtime
cp -r "$SKILL_DIR/bin/planner/" "$RUNTIME_DIR/planner/"
cp -r "$SKILL_DIR/bin/playbook_engine/" "$RUNTIME_DIR/playbook_engine/"

PYTHON3="$(which python3)"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON3}</string>
        <string>${RUNTIME_DIR}/planner/worker.py</string>
        <string>--interval</string>
        <string>30</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${RUNTIME_DIR}/planner.log</string>
    <key>StandardErrorPath</key>
    <string>${RUNTIME_DIR}/planner.log</string>
    <key>WorkingDirectory</key>
    <string>${RUNTIME_DIR}</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Planner worker started (interval=30s)"
echo "Logs: $RUNTIME_DIR/planner.log"
