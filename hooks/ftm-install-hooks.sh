#!/bin/bash
# ftm-install-hooks.sh
# Installs all ftm-*.sh hooks into ~/.claude/hooks/ and updates settings.json
#
# Usage: bash hooks/ftm-install-hooks.sh [--dry-run]
#
# What it does:
#   1. Copies all ftm-*.sh hooks to ~/.claude/hooks/
#   2. Makes all hooks executable
#   3. Updates ~/.claude/settings.json with correct hook entries
#      - Removes old eng-buddy hook entries
#      - Adds ftm- prefixed hook entries
#      - Ensures SessionEnd hooks are in SEPARATE matcher entries
#        (ftm-session-snapshot.sh first, ftm-session-end.sh second)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DEST="$HOME/.claude/hooks"
SETTINGS_FILE="$HOME/.claude/settings.json"
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
  esac
done

log() { echo "[ftm-install-hooks] $*"; }
dry() { echo "[DRY RUN] $*"; }

# --- Step 1: Copy hooks ---
log "Copying ftm-*.sh hooks to $HOOKS_DEST"
mkdir -p "$HOOKS_DEST"

for hook in "$SCRIPT_DIR"/ftm-*.sh; do
  name="$(basename "$hook")"
  dest="$HOOKS_DEST/$name"
  if [ "$DRY_RUN" = true ]; then
    dry "cp $hook -> $dest"
  else
    cp "$hook" "$dest"
    chmod +x "$dest"
    log "  installed $name"
  fi
done

# Also install non-sh ftm hooks if present (e.g., .mjs)
for hook in "$SCRIPT_DIR"/ftm-*.mjs; do
  [ -f "$hook" ] || continue
  name="$(basename "$hook")"
  dest="$HOOKS_DEST/$name"
  if [ "$DRY_RUN" = true ]; then
    dry "cp $hook -> $dest"
  else
    cp "$hook" "$dest"
    log "  installed $name"
  fi
done

# --- Step 2: Update settings.json ---
if [ ! -f "$SETTINGS_FILE" ]; then
  log "ERROR: $SETTINGS_FILE not found — cannot update hook entries"
  exit 1
fi

log "Updating $SETTINGS_FILE hook entries"

if [ "$DRY_RUN" = true ]; then
  dry "Would update settings.json:"
  dry "  - Remove eng-buddy hook entries"
  dry "  - Add ftm-auto-log.sh to UserPromptSubmit"
  dry "  - Add ftm-pre-compaction.sh to UserPromptSubmit"
  dry "  - Add ftm-post-compaction.sh to UserPromptSubmit"
  dry "  - Add ftm-learning-capture.sh to PostToolUse"
  dry "  - Add ftm-session-snapshot.sh to SessionEnd (matcher entry 1)"
  dry "  - Add ftm-session-end.sh to SessionEnd (matcher entry 2, separate)"
  exit 0
fi

python3 - "$SETTINGS_FILE" << 'PYEOF'
import json, sys, copy
from pathlib import Path

settings_path = sys.argv[1]
hooks_dir = str(Path.home() / ".claude/hooks")

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})

# Helper: remove hooks by command substring
def remove_hook_commands(hook_list, substrings):
    """Remove hook entries whose command contains any of the given substrings."""
    result = []
    for entry in hook_list:
        hooks_in_entry = entry.get("hooks", [])
        filtered = [
            h for h in hooks_in_entry
            if not any(s in h.get("command", "") for s in substrings)
        ]
        if filtered:
            entry = dict(entry)
            entry["hooks"] = filtered
            result.append(entry)
    return result

ENG_BUDDY_HOOKS = [
    "eng-buddy-auto-log",
    "eng-buddy-draft-enforcer",
    "eng-buddy-learning-capture",
    "eng-buddy-session-snapshot",
    "eng-buddy-session-end",
    "eng-buddy-pre-compaction",
    "eng-buddy-post-compaction",
    "eng-buddy-task-sync",
    "eng-buddy-session-manager",
]

# --- Clean eng-buddy entries from all hook events ---
for event in list(hooks.keys()):
    hooks[event] = remove_hook_commands(hooks[event], ENG_BUDDY_HOOKS)

# --- UserPromptSubmit: add ftm hooks to existing matcher-less entry (or create one) ---
ups_hooks = hooks.setdefault("UserPromptSubmit", [])

FTM_UPS_COMMANDS = [
    f"{hooks_dir}/ftm-auto-log.sh",
    f"{hooks_dir}/ftm-pre-compaction.sh",
    f"{hooks_dir}/ftm-post-compaction.sh",
]

# Find the first matcher-less (global) entry
global_entry = None
for entry in ups_hooks:
    if not entry.get("matcher"):
        global_entry = entry
        break

if global_entry is None:
    global_entry = {"hooks": []}
    ups_hooks.insert(0, global_entry)

existing_cmds = {h["command"] for h in global_entry["hooks"]}
for cmd in FTM_UPS_COMMANDS:
    if cmd not in existing_cmds:
        global_entry["hooks"].append({"type": "command", "command": cmd})

# --- PostToolUse: add ftm-learning-capture to existing global entry ---
ptu_hooks = hooks.setdefault("PostToolUse", [])

FTM_PTU_COMMANDS = [
    f"{hooks_dir}/ftm-learning-capture.sh",
]

# Find global (no matcher or empty matcher) PostToolUse entry
ptu_global = None
for entry in ptu_hooks:
    matcher = entry.get("matcher", "")
    if not matcher:
        ptu_global = entry
        break

if ptu_global is None:
    ptu_global = {"hooks": []}
    ptu_hooks.insert(0, ptu_global)

existing_ptu_cmds = {h["command"] for h in ptu_global["hooks"]}
for cmd in FTM_PTU_COMMANDS:
    if cmd not in existing_ptu_cmds:
        ptu_global["hooks"].insert(0, {"type": "command", "command": cmd})

# --- SessionEnd: ensure snapshot and end are in SEPARATE matcher entries ---
# Snapshot must complete before end (snapshot reads context.json status; end modifies it)
se_hooks = hooks.setdefault("SessionEnd", [])

SNAPSHOT_CMD = f"{hooks_dir}/ftm-session-snapshot.sh"
END_CMD = f"{hooks_dir}/ftm-session-end.sh"

# Check if already present
has_snapshot = any(
    any(h.get("command") == SNAPSHOT_CMD for h in e.get("hooks", []))
    for e in se_hooks
)
has_end = any(
    any(h.get("command") == END_CMD for h in e.get("hooks", []))
    for e in se_hooks
)

# Remove any combined entry that has both (shouldn't happen but clean up if so)
cleaned_se = []
for entry in se_hooks:
    cmds = [h.get("command", "") for h in entry.get("hooks", [])]
    if SNAPSHOT_CMD in cmds and END_CMD in cmds:
        # Split into two separate entries
        snap_hooks = [h for h in entry["hooks"] if h.get("command") != END_CMD]
        end_hooks = [h for h in entry["hooks"] if h.get("command") == END_CMD]
        other_hooks = [h for h in entry["hooks"] if h.get("command") not in (SNAPSHOT_CMD, END_CMD)]
        if snap_hooks or other_hooks:
            cleaned_se.append({"hooks": snap_hooks + other_hooks})
        if end_hooks:
            cleaned_se.append({"hooks": end_hooks})
        has_snapshot = True
        has_end = True
    else:
        cleaned_se.append(entry)
se_hooks[:] = cleaned_se

# Add snapshot entry (first)
if not has_snapshot:
    se_hooks.insert(0, {"hooks": [{"type": "command", "command": SNAPSHOT_CMD}]})

# Add end entry (separate, after snapshot)
if not has_end:
    # Find position of snapshot entry and insert end after it
    snap_idx = next(
        (i for i, e in enumerate(se_hooks)
         if any(h.get("command") == SNAPSHOT_CMD for h in e.get("hooks", []))),
        -1
    )
    insert_pos = snap_idx + 1 if snap_idx >= 0 else len(se_hooks)
    se_hooks.insert(insert_pos, {"hooks": [{"type": "command", "command": END_CMD}]})

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("settings.json updated successfully")
PYEOF

log "Hook installation complete."
log ""
log "Installed hooks:"
for hook in "$HOOKS_DEST"/ftm-*.sh; do
  [ -f "$hook" ] || continue
  echo "  $(basename "$hook")"
done
log ""
log "Verify with: ls $HOOKS_DEST/ftm-*.sh | wc -l"
