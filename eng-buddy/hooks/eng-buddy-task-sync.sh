#!/bin/bash
# eng-buddy-task-sync.sh
# Hook: Auto-sync TaskCreate/TaskUpdate calls to tasks.db
# Trigger: PostToolUse (fires after TaskCreate or TaskUpdate)
#
# When Claude creates or updates a task, this hook automatically calls
# brain.py to keep tasks.db in sync — no manual discipline required.

set -euo pipefail

ENG_BUDDY_ROOT="$HOME/.claude/eng-buddy"
SESSION_MARKER="$ENG_BUDDY_ROOT/.session-active"
BRAIN="$HOME/.claude/skills/eng-buddy/bin/brain.py"

# Only fire during eng-buddy sessions
if [ ! -f "$SESSION_MARKER" ]; then
  exit 0
fi

# brain.py must exist
if [ ! -f "$BRAIN" ]; then
  exit 0
fi

PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
  exit 0
fi

# Parse tool_name from the PostToolUse payload
TOOL_NAME=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try: print(json.load(sys.stdin).get("tool_name", ""))
except: print("")
' 2>/dev/null)

# Only care about TaskUpdate and TaskCreate
if [ "$TOOL_NAME" != "TaskUpdate" ] && [ "$TOOL_NAME" != "TaskCreate" ]; then
  exit 0
fi

# --- TaskUpdate: sync status/priority changes to tasks.db ---
if [ "$TOOL_NAME" = "TaskUpdate" ]; then
  # Extract fields from tool_input
  read -r TASK_ID STATUS SUBJECT <<< "$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    inp = d.get("tool_input", {})
    print(inp.get("taskId", ""), inp.get("status", ""), inp.get("subject", ""))
except:
    print("  ")
' 2>/dev/null)"

  if [ -z "$TASK_ID" ]; then
    exit 0
  fi

  # Extract the legacy task number from subject (e.g., "#7 - Something" -> 7)
  DB_ID=""
  if [ -n "$SUBJECT" ]; then
    DB_ID=$(echo "$SUBJECT" | python3 -c '
import sys, re
s = sys.stdin.read().strip()
m = re.match(r"#(\d+)\s*-", s)
if m: print(m.group(1))
else: print("")
' 2>/dev/null)
  fi

  # If we couldn't get DB_ID from subject, try to look it up
  if [ -z "$DB_ID" ]; then
    # Fall back: read subject from tool_response to get the task number
    DB_ID=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys, re
try:
    d = json.load(sys.stdin)
    resp = str(d.get("tool_response", ""))
    # Try to find #N in response
    m = re.search(r"#(\d+)\b", resp)
    if m: print(m.group(1))
    else: print("")
except:
    print("")
' 2>/dev/null)
  fi

  if [ -z "$DB_ID" ]; then
    exit 0
  fi

  # Build brain.py command
  BRAIN_ARGS="--task-update $DB_ID"
  if [ -n "$STATUS" ]; then
    BRAIN_ARGS="$BRAIN_ARGS --status $STATUS"
  fi

  # Run sync (async, don't block Claude)
  python3 "$BRAIN" $BRAIN_ARGS >/dev/null 2>&1 &

  # Inject confirmation so Claude knows it happened
  echo "{\"suppressOutput\": true}"
fi

# --- TaskCreate: inject reminder to also add to tasks.db ---
# TaskCreate doesn't have enough info to auto-create in DB (we need priority, jira_key, etc.)
# So we inject a reminder for Claude to run brain.py --task-add
if [ "$TOOL_NAME" = "TaskCreate" ]; then
  SUBJECT=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    inp = d.get("tool_input", {})
    print(inp.get("subject", ""))
except:
    print("")
' 2>/dev/null)

  # Check if this looks like a restore (has #N prefix) — skip reminder for restores
  IS_RESTORE=$(echo "$SUBJECT" | python3 -c '
import sys, re
s = sys.stdin.read().strip()
if re.match(r"#\d+\s*-", s): print("yes")
else: print("no")
' 2>/dev/null)

  if [ "$IS_RESTORE" = "no" ]; then
    cat <<EOF
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "[TASK-DB SYNC]: New task created. Run: python3 ~/.claude/skills/eng-buddy/bin/brain.py --task-add --title \"$SUBJECT\" to add it to tasks.db. Do this silently."}}
EOF
  else
    echo "{\"suppressOutput\": true}"
  fi
fi
