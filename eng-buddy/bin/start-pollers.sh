#!/bin/bash
# eng-buddy poller launcher
# Syncs poller scripts to runtime dir, installs LaunchAgents with correct PATH,
# loads them if not running, and triggers an initial poll of each.

set -euo pipefail

# Prevent "nested session" errors when launched from Claude Code
unset CLAUDECODE

SKILLS_BIN="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$HOME/.claude/eng-buddy"
RUNTIME_BIN="$RUNTIME_DIR/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PYTHON="$(which python3)"
CLAUDE_DIR="$(dirname "$(which claude 2>/dev/null || echo "/usr/local/bin/claude")")"
COMBINED_PATH="$CLAUDE_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p "$RUNTIME_BIN" "$LAUNCH_AGENTS_DIR"

# --- Sync poller scripts + brain.py to runtime ---
for f in slack-poller.py gmail-poller.py calendar-poller.py jira-poller.py freshservice-enrichment.py brain.py tasks_db.py; do
    if [ -f "$SKILLS_BIN/$f" ]; then
        cp "$SKILLS_BIN/$f" "$RUNTIME_BIN/$f"
    fi
done

# --- Poller definitions: label, script, interval_seconds ---
declare -a POLLERS=(
    "com.engbuddy.slackpoller|slack-poller.py|300"
    "com.engbuddy.gmailpoller|gmail-poller.py|600"
    "com.engbuddy.calendarpoller|calendar-poller.py|1800"
    "com.engbuddy.jirapoller|jira-poller.py|300"
    "com.engbuddy.freshservice-enrichment|freshservice-enrichment.py|300"
)

CHANGED=0

for entry in "${POLLERS[@]}"; do
    IFS='|' read -r LABEL SCRIPT INTERVAL <<< "$entry"
    PLIST="$LAUNCH_AGENTS_DIR/$LABEL.plist"
    LOGFILE="$RUNTIME_DIR/${SCRIPT%.py}.log"

    # Generate plist with correct PATH
    cat > "$PLIST.tmp" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$RUNTIME_BIN/$SCRIPT</string>
    </array>
    <key>StartInterval</key>
    <integer>$INTERVAL</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOGFILE</string>
    <key>StandardErrorPath</key>
    <string>$LOGFILE</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$COMBINED_PATH</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>
</dict>
</plist>
PLISTEOF

    # Only reload if plist changed or agent not loaded
    if ! cmp -s "$PLIST.tmp" "$PLIST" 2>/dev/null; then
        mv "$PLIST.tmp" "$PLIST"
        CHANGED=1
        # Unload old version if loaded
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || \
            launchctl load "$PLIST" 2>/dev/null || true
        echo "  Installed + loaded: $LABEL (every ${INTERVAL}s)"
    else
        rm "$PLIST.tmp"
        # Check if loaded
        if ! launchctl list "$LABEL" &>/dev/null; then
            launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || \
                launchctl load "$PLIST" 2>/dev/null || true
            echo "  Loaded: $LABEL (every ${INTERVAL}s)"
        else
            echo "  Already running: $LABEL"
        fi
    fi
done

# --- Initial poll of each (in background, skip if recently polled) ---
echo "  Running initial polls..."
for entry in "${POLLERS[@]}"; do
    IFS='|' read -r LABEL SCRIPT INTERVAL <<< "$entry"
    (
        cd "$RUNTIME_BIN"
        PATH="$COMBINED_PATH" "$PYTHON" "$SCRIPT" >> "$RUNTIME_DIR/${SCRIPT%.py}.log" 2>&1 &
    )
done

echo "POLLERS_OK"
