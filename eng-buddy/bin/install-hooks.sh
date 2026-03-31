#!/bin/bash
# install-hooks.sh
# One-shot installer for eng-buddy hooks + learning capture wiring.
#
# Installs hooks to all relevant locations:
# 1) $CLAUDE_HOME/hooks                (Claude runtime hooks, parent)
# 2) $CLAUDE_HOME/skills/eng-buddy/hooks (skill package hooks, child)
# 3) $CLAUDE_HOME/eng-buddy/hooks      (runtime workspace hooks, child)
#
# Also syncs learning runtime files and patches settings.json with:
# - UserPromptSubmit -> auto-log
# - PostToolUse      -> learning-capture
# - SessionEnd       -> snapshot then session-end

set -euo pipefail

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_HOOKS_DIR="$SKILL_DIR/hooks"
SOURCE_BIN_DIR="$SKILL_DIR/bin"
SOURCE_DASHBOARD_DIR="$SKILL_DIR/dashboard"

SETTINGS_FILE="$CLAUDE_HOME/settings.json"

if [ ! -d "$SOURCE_HOOKS_DIR" ]; then
  echo "ERROR: source hooks dir missing: $SOURCE_HOOKS_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_BIN_DIR/brain.py" ]; then
  echo "ERROR: brain.py missing at $SOURCE_BIN_DIR/brain.py" >&2
  exit 1
fi

DEST_PARENT_HOOKS="$CLAUDE_HOME/hooks"
DEST_SKILL_HOOKS="$CLAUDE_HOME/skills/eng-buddy/hooks"
DEST_RUNTIME_HOOKS="$CLAUDE_HOME/eng-buddy/hooks"

DEST_RUNTIME_BIN="$CLAUDE_HOME/eng-buddy/bin"
DEST_RUNTIME_DASHBOARD="$CLAUDE_HOME/eng-buddy/dashboard"

mkdir -p "$DEST_PARENT_HOOKS" "$DEST_SKILL_HOOKS" "$DEST_RUNTIME_HOOKS"
mkdir -p "$DEST_RUNTIME_BIN" "$DEST_RUNTIME_DASHBOARD"

copy_hooks_to() {
  local target="$1"
  local src_real target_real
  src_real="$(cd "$SOURCE_HOOKS_DIR" && pwd)"
  target_real="$(cd "$target" && pwd)"
  if [ "$src_real" = "$target_real" ]; then
    chmod +x "$target"/eng-buddy-*.sh
    return 0
  fi
  cp "$SOURCE_HOOKS_DIR"/eng-buddy-*.sh "$target"/
  chmod +x "$target"/eng-buddy-*.sh
}

copy_hooks_to "$DEST_PARENT_HOOKS"
copy_hooks_to "$DEST_SKILL_HOOKS"
copy_hooks_to "$DEST_RUNTIME_HOOKS"

sync_runtime_dashboard() {
  mkdir -p "$DEST_RUNTIME_DASHBOARD"
  rsync -a --delete \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '*.pyc' \
    "$SOURCE_DASHBOARD_DIR/" "$DEST_RUNTIME_DASHBOARD/"
  chmod +x "$DEST_RUNTIME_DASHBOARD/start.sh"
}

# Sync learning engine runtime files needed by hooks and the dashboard runtime mirror.
cp "$SOURCE_BIN_DIR/brain.py" "$DEST_RUNTIME_BIN/brain.py"
sync_runtime_dashboard

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: python3 is required to patch settings.json" >&2
  exit 1
fi

if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  printf '{"hooks":{}}\n' > "$SETTINGS_FILE"
fi

"$PYTHON_BIN" - "$SETTINGS_FILE" "$DEST_PARENT_HOOKS" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
hooks_dir = Path(sys.argv[2])

with settings_path.open('r', encoding='utf-8') as f:
    data = json.load(f)

hooks = data.setdefault('hooks', {})

def ensure_event_structure(event_name):
    event = hooks.get(event_name)
    if not isinstance(event, list) or not event:
        event = [{"hooks": []}]
    first = event[0]
    if not isinstance(first, dict):
        first = {"hooks": []}
    first_hooks = first.get("hooks")
    if not isinstance(first_hooks, list):
        first_hooks = []
    first["hooks"] = first_hooks
    event[0] = first
    hooks[event_name] = event
    return first_hooks


def ensure_command(event_name, command_path):
    entries = ensure_event_structure(event_name)
    normalized = str(Path(command_path))
    for item in entries:
        if isinstance(item, dict) and item.get("type") == "command" and item.get("command") == normalized:
            return
    entries.append({"type": "command", "command": normalized})


auto_log = hooks_dir / "eng-buddy-auto-log.sh"
learning = hooks_dir / "eng-buddy-learning-capture.sh"
snapshot = hooks_dir / "eng-buddy-session-snapshot.sh"
session_end = hooks_dir / "eng-buddy-session-end.sh"

ensure_command("UserPromptSubmit", auto_log)
ensure_command("PostToolUse", learning)

# SessionEnd must keep snapshot before session-end.
entries = ensure_event_structure("SessionEnd")
keep = []
for item in entries:
    if not isinstance(item, dict):
        continue
    if item.get("type") != "command":
        keep.append(item)
        continue
    cmd = item.get("command")
    if cmd in {str(snapshot), str(session_end)}:
        continue
    keep.append(item)
entries[:] = keep
entries.append({"type": "command", "command": str(snapshot)})
entries.append({"type": "command", "command": str(session_end)})

with settings_path.open('w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

# Ensure runtime DB has learning tables available.
if [ -f "$DEST_RUNTIME_DASHBOARD/migrate.py" ]; then
  "$PYTHON_BIN" "$DEST_RUNTIME_DASHBOARD/migrate.py" >/dev/null 2>&1 || true
fi

echo "Installed eng-buddy hooks to:"
echo "- $DEST_PARENT_HOOKS"
echo "- $DEST_SKILL_HOOKS"
echo "- $DEST_RUNTIME_HOOKS"
echo "Synced learning runtime files to:"
echo "- $DEST_RUNTIME_BIN/brain.py"
echo "- $DEST_RUNTIME_DASHBOARD/ (full dashboard mirror)"
echo "Patched hooks config in: $SETTINGS_FILE"
echo "Done."
