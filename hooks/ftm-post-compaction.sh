#!/bin/bash
# ftm-post-compaction.sh
# Hook: Post-compaction context restoration for ftm
# Trigger: UserPromptSubmit
#
# Detects when Claude Code has just compacted the session (context was compressed).
# After compaction, Claude's in-memory context is reset to a summary — it loses
# the session's working state. This hook injects a re-initialization prompt that
# tells Claude to reload its state from disk before responding.
#
# Detection method: compaction DECREASES the session JSONL line count in-place
# (same session_id, fewer lines). We track {session_id, line_count} between
# invocations in .session-state to detect this.
#
# Ported from OpenClaw's post-compaction-context.ts pattern.
#
# FILES:
#   ~/.claude/ftm-state/blackboard/context.json  - session gate
#   ~/.claude/ftm-state/.session-state            - JSON: {session_id, line_count}

FTM_STATE="$HOME/.claude/ftm-state"
CONTEXT_JSON="$FTM_STATE/blackboard/context.json"
SESSION_STATE_FILE="$FTM_STATE/.session-state"

# 1. Only run during active ftm sessions
FTM_ACTIVE=$(python3 -c "
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

if [ "$FTM_ACTIVE" != "1" ]; then
    exit 0
fi

# 2. Read hook payload from stdin
PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
    exit 0
fi

SESSION_ID=$(echo "$PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', ''))
except:
    print('')
" 2>/dev/null)

TRANSCRIPT_PATH=$(echo "$PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except:
    print('')
" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

# 3. Find session JSONL
JSONL_FILE=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    JSONL_FILE="$TRANSCRIPT_PATH"
elif [ -n "$SESSION_ID" ]; then
    JSONL_FILE=$(find "$HOME/.claude/projects/" -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
fi

if [ -z "$JSONL_FILE" ] || [ ! -f "$JSONL_FILE" ]; then
    exit 0
fi

# 4. Get current line count
CURRENT_LINES=$(wc -l < "$JSONL_FILE" 2>/dev/null | tr -d ' ')
CURRENT_LINES=${CURRENT_LINES:-0}

# 5. Read stored state
STORED_STATE=$(cat "$SESSION_STATE_FILE" 2>/dev/null || echo '{}')
STORED_SESSION=$(echo "$STORED_STATE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', ''))
except:
    print('')
" 2>/dev/null)
STORED_LINES=$(echo "$STORED_STATE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('line_count', 0))
except:
    print(0)
" 2>/dev/null)

# 6. Always update stored state with current values
python3 -c "
import json
with open('$SESSION_STATE_FILE', 'w') as f:
    json.dump({'session_id': '$SESSION_ID', 'line_count': $CURRENT_LINES}, f)
" 2>/dev/null

# 7. Detect compaction: same session, line count DECREASED
if [ "$STORED_SESSION" != "$SESSION_ID" ]; then
    exit 0  # New session, not compaction
fi

if [ -z "$STORED_LINES" ] || [ "$STORED_LINES" = "0" ]; then
    exit 0  # No baseline yet
fi

# Check if line count dropped (with a meaningful threshold to avoid noise)
DIFF=$(( STORED_LINES - CURRENT_LINES ))
if [ "$DIFF" -lt 10 ] 2>/dev/null; then
    exit 0  # Line count didn't drop significantly — no compaction
fi

# 8. Compaction detected! Inject context restoration prompt
TODAY=$(date +%Y-%m-%d)

echo ""
echo "[POST-COMPACTION RESTORE — session context was just compacted]:"
echo "The conversation was just summarized and your in-session state was reset."
echo "State was preserved in ftm-state. BEFORE responding to the message below:"
echo "1. Read ~/.claude/ftm-state/blackboard/context.json (current task and session state)"
echo "2. Read any relevant daily log or session snapshot from ~/.claude/ftm-state/sessions/"
echo "Then respond as if you just loaded into a fresh ftm session."
echo "Do not announce this restoration to the user — just do it and proceed."
echo ""
