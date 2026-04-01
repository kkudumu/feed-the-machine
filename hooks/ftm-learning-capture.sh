#!/bin/bash
# ftm-learning-capture.sh
# Hook: Capture write/task completions into learning engine DB
# Trigger: PostToolUse
#
# Behavior:
# - Runs only for active ftm sessions (context.json has non-completed task)
# - Captures Write/Edit/Bash/task-style MCP completions into learning events
# - Routes known categories into knowledge files via brain.py if available
# - If category mapping is unknown, asks Claude to confirm category expansion

set -euo pipefail

FTM_STATE="$HOME/.claude/ftm-state"
CONTEXT_JSON="$FTM_STATE/blackboard/context.json"

PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
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

# Session gating: check if context.json has an active (non-completed) session
IS_FTM_ACTIVE=$(python3 -c "
import json, sys
try:
    with open('$CONTEXT_JSON') as f:
        d = json.load(f)
    task = d.get('current_task', {})
    status = task.get('status', '')
    print('1' if status not in ('', 'completed', 'none') else '0')
except Exception:
    print('0')
" 2>/dev/null)

if [ "$IS_FTM_ACTIVE" != "1" ]; then
  exit 0
fi

# Attempt brain.py capture if available (ftm skill may ship its own brain.py)
BRAIN_PY="$HOME/.claude/skills/ftm/bin/brain.py"
if [ ! -f "$BRAIN_PY" ]; then
  BRAIN_PY="$HOME/.claude/ftm-state/brain.py"
fi

if [ -f "$BRAIN_PY" ]; then
  RESULT=$(printf '%s' "$PAYLOAD" | python3 "$BRAIN_PY" --capture-post-tool 2>/dev/null || echo '{"recorded": false}')

  NEEDS_EXPANSION=$(printf '%s' "$RESULT" | python3 -c '
import json, sys
try:
    print("1" if json.load(sys.stdin).get("needs_category_expansion") else "0")
except Exception:
    print("0")
' 2>/dev/null)

  if [ "$NEEDS_EXPANSION" = "1" ]; then
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
    echo "[Learning Engine] Captured a completion event that does not match an existing learning category."
    echo "Before wrapping up, ask the user:"
    echo "\"Should we add learning category '$SAFE_PROPOSED' so future ftm completions route cleanly?\""
    echo ""
  fi
fi

# --- Feed Playbook Tracer if active trace exists ---
ACTIVE_TRACE_FILE="$FTM_STATE/.active-trace-id"
if [ -f "$ACTIVE_TRACE_FILE" ] && [ -f "$BRAIN_PY" ]; then
    TRACE_ID=$(cat "$ACTIVE_TRACE_FILE")
    printf '%s' "$PAYLOAD" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tool_name = d.get('tool_name', '')
if tool_name:
    event = {'trace_id': '$TRACE_ID', 'event': {'type': 'tool_call', 'tool': tool_name, 'params': d.get('tool_input', {})}}
    json.dump(event, sys.stdout)
" 2>/dev/null | python3 "$BRAIN_PY" --playbook-trace-event 2>/dev/null
fi

exit 0
