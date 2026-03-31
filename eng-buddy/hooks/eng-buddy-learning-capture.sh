#!/bin/bash
# eng-buddy-learning-capture.sh
# Hook: Capture write/task completions into learning engine DB
# Trigger: PostToolUse
#
# Behavior:
# - Runs only for eng-buddy sessions (explicit /eng-buddy marker or dashboard-opened sessions)
# - Captures Write/Edit/Bash/task-style MCP completions into inbox.db learning_events
# - Routes known categories into markdown knowledge files via bin/brain.py
# - If category mapping is unknown, asks Claude to confirm category expansion with the user

set -euo pipefail

ENG_BUDDY_ROOT="$HOME/.claude/eng-buddy"
SESSION_MARKER="$ENG_BUDDY_ROOT/.session-active"
BRAIN_PY="$ENG_BUDDY_ROOT/bin/brain.py"

PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
  exit 0
fi

if [ ! -f "$BRAIN_PY" ]; then
  exit 0
fi

HOOK_EVENT=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("hook_event_name", ""))
except Exception:
    print("")
' 2>/dev/null)

if [ "$HOOK_EVENT" != "PostToolUse" ]; then
  exit 0
fi

TOOL_NAME=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("tool_name", ""))
except Exception:
    print("")
' 2>/dev/null)

case "$TOOL_NAME" in
  Write|Edit|MultiEdit|NotebookEdit|Bash|Task|mcp__*) ;;
  *) exit 0 ;;
esac

# Session gating:
# 1) explicit eng-buddy session marker from /eng-buddy
# 2) dashboard session context in transcript (open-session/open-task-session)
IS_ENG_BUDDY=false
if [ -f "$SESSION_MARKER" ]; then
  IS_ENG_BUDDY=true
fi

if [ "$IS_ENG_BUDDY" = false ]; then
  TRANSCRIPT_PATH=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("transcript_path", ""))
except Exception:
    print("")
' 2>/dev/null)

  if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    if grep -Eiq "eng-buddy task|eng-buddy task from tasks tab|you are eng-buddy" "$TRANSCRIPT_PATH"; then
      IS_ENG_BUDDY=true
    fi
  fi
fi

if [ "$IS_ENG_BUDDY" = false ]; then
  exit 0
fi

RESULT=$(printf '%s' "$PAYLOAD" | python3 "$BRAIN_PY" --capture-post-tool 2>/dev/null || echo '{"recorded": false}')

NEEDS_EXPANSION=$(printf '%s' "$RESULT" | python3 -c '
import json, sys
try:
    print("1" if json.load(sys.stdin).get("needs_category_expansion") else "0")
except Exception:
    print("0")
' 2>/dev/null)

if [ "$NEEDS_EXPANSION" != "1" ]; then
  exit 0
fi

PROPOSED_CATEGORY=$(printf '%s' "$RESULT" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("proposed_category", "new-category"))
except Exception:
    print("new-category")
' 2>/dev/null)

SAFE_PROPOSED=$(printf '%s' "$PROPOSED_CATEGORY" | tr -cd '[:alnum:]-_')
if [ -z "$SAFE_PROPOSED" ]; then
  SAFE_PROPOSED="new-category"
fi

echo ""
echo "🧠 [Learning Engine] Captured a completion event that does not match an existing learning category."
echo "Before wrapping up, ask the user:"
echo "\"Should we add learning category '$SAFE_PROPOSED' so future eng-buddy completions route cleanly?\""
echo "If user confirms, run:"
echo "python3 ~/.claude/eng-buddy/bin/brain.py --register-learning-category \"$SAFE_PROPOSED\" --description \"Captured from PostToolUse completion events\""
echo ""

# --- Feed Playbook Tracer ---
# If there's an active trace (ticket context), also record in tracer
# Uses a single Python invocation to avoid repeated JSON parsing
ACTIVE_TRACE_FILE="$HOME/.claude/eng-buddy/.active-trace-id"
if [ -f "$ACTIVE_TRACE_FILE" ]; then
    TRACE_ID=$(cat "$ACTIVE_TRACE_FILE")
    printf '%s' "$PAYLOAD" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tool_name = d.get('tool_name', '')
if tool_name:
    event = {'trace_id': '$TRACE_ID', 'event': {'type': 'tool_call', 'tool': tool_name, 'params': d.get('tool_input', {})}}
    json.dump(event, sys.stdout)
" 2>/dev/null | python3 "$HOME/.claude/eng-buddy/bin/brain.py" --playbook-trace-event 2>/dev/null
fi

exit 0
