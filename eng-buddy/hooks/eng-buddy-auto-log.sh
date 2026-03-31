#!/bin/bash
# Hook: Auto-log progress + heartbeat for eng-buddy
# Triggers: Every user message while eng-buddy is active
#
# 1. Auto-log: reminds Claude to log progress when user reports completing something
# 2. Task inbox: surfaces unreviewed Slack/email tasks every 10 min
# 3. Heartbeat: every 30 min, scans task state for urgent items to surface
#
# Heartbeat inspired by OpenClaw's HEARTBEAT.md pattern (heartbeat.ts):
# Periodically checks ~/.claude/eng-buddy/HEARTBEAT.md and task state,
# prompting Claude to surface anything time-sensitive without the user asking.
#
# FILES:
#   ~/.claude/eng-buddy/.session-active       - session gate
#   ~/.claude/eng-buddy/.last-heartbeat       - timestamp of last heartbeat
#   ~/.claude/eng-buddy/HEARTBEAT.md          - user-maintained alert/task config

# Check if eng-buddy session is active
if [ ! -f ~/.claude/eng-buddy/.session-active ]; then
    exit 0  # Not in eng-buddy session, skip
fi

# Read payload from stdin (JSON) — extract prompt for action pattern matching
STDIN_DATA=$(cat)
USER_MESSAGE=$(echo "$STDIN_DATA" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('prompt', ''))
except:
    print('')
" 2>/dev/null)
# Fallback: treat stdin as raw message if JSON parse failed
if [ -z "$USER_MESSAGE" ]; then
    USER_MESSAGE="$STDIN_DATA"
fi

# Action indicators (what users say when they've done something)
ACTION_PATTERNS=(
    "^[Ii] (did|completed?|finished|fixed|sent|responded|closed|created|updated|deployed|merged|pushed|committed|tested|reviewed)"
    "^[Jj]ust (did|completed?|finished|fixed|sent|responded|closed|created|updated|deployed|merged|pushed|committed|tested|reviewed)"
    "^[Dd]one"
    "^[Ff]inished"
    "^[Cc]ompleted?"
    "^[Ss]ent (email|message|response)"
    "^[Rr]esponded to"
    "^[Mm]erged"
    "^[Pp]ushed to"
    "^[Cc]ommitted"
    "^[Dd]eployed"
    "^[Ff]ixed"
    "^[Cc]losed (ticket|issue|task)"
    "[Tt]ask.*complete"
    "[Tt]icket.*closed"
)

# Check if message matches any action pattern
SHOULD_LOG=false
for pattern in "${ACTION_PATTERNS[@]}"; do
    if echo "$USER_MESSAGE" | grep -qE "$pattern"; then
        SHOULD_LOG=true
        break
    fi
done

# Also check for follow-up questions after taking action
# (e.g., "I sent the email. What should I do next?")
if echo "$USER_MESSAGE" | grep -qE "(I|i) .* (what|should|next|now)\?"; then
    SHOULD_LOG=true
fi

# If action detected, output logging reminder for Claude to see
if [ "$SHOULD_LOG" = true ]; then
    echo ""
    echo "📝 [Auto-log] Detected progress update. Please log this to today's daily log."
    echo ""
fi

# --- Dashboard sync: surface task-state changes made outside the chat ---
CLAUDE_SYNC_FILE="$HOME/.claude/eng-buddy/.runtime/claude-sync-events.txt"
if [ -s "$CLAUDE_SYNC_FILE" ]; then
    echo ""
    echo "[Dashboard sync] Recent dashboard updates were written to eng-buddy state:"
    head -20 "$CLAUDE_SYNC_FILE"
    echo "Please run 'python3 ~/.claude/skills/eng-buddy/bin/brain.py --tasks --task-json' to reload task state from tasks.db and treat those updates as authoritative."
    echo ""
    : > "$CLAUDE_SYNC_FILE"
fi

# --- Check for pending Slack task inbox items ---
TASK_INBOX=~/.claude/eng-buddy/task-inbox.md
TASK_SHOWN_MARKER=~/.claude/eng-buddy/.task-inbox-last-shown

if [ -f "$TASK_INBOX" ]; then
    PENDING_COUNT=$(grep -c "^## \[ \]" "$TASK_INBOX" 2>/dev/null || echo 0)

    if [ "$PENDING_COUNT" -gt 0 ]; then
        # Only surface once per 10 minutes to avoid noise
        SHOULD_SHOW=true
        if [ -f "$TASK_SHOWN_MARKER" ]; then
            LAST_SHOWN=$(stat -f %m "$TASK_SHOWN_MARKER" 2>/dev/null || echo 0)
            NOW=$(date +%s)
            ELAPSED=$(( NOW - LAST_SHOWN ))
            if [ "$ELAPSED" -lt 600 ]; then
                SHOULD_SHOW=false
            fi
        fi

        if [ "$SHOULD_SHOW" = true ]; then
            touch "$TASK_SHOWN_MARKER"
            echo ""
            echo "📬 [Slack Task Inbox] $PENDING_COUNT unreviewed message(s) detected from Slack that may need action:"
            grep -A2 "^## \[ \]" "$TASK_INBOX" | grep -v "^<!--" | grep -v "^--$" | head -40
            echo ""
            echo "Please review these with the user and offer to create tasks. Mark as [x] in task-inbox.md once reviewed."
            echo ""
        fi
    fi
fi

# --- Heartbeat: periodic task/urgency check ---
# Fires every 30 minutes. Prompts Claude to scan for time-sensitive items
# without the user having to ask. Inspired by OpenClaw's HEARTBEAT.md pattern.
HEARTBEAT_INTERVAL=1800  # 30 minutes in seconds
LAST_HEARTBEAT_FILE="$HOME/.claude/eng-buddy/.last-heartbeat"
HEARTBEAT_MD="$HOME/.claude/eng-buddy/HEARTBEAT.md"

SHOULD_HEARTBEAT=false
if [ -f "$LAST_HEARTBEAT_FILE" ]; then
    LAST_BEAT=$(cat "$LAST_HEARTBEAT_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    ELAPSED=$(( NOW - LAST_BEAT ))
    if [ "$ELAPSED" -ge "$HEARTBEAT_INTERVAL" ]; then
        SHOULD_HEARTBEAT=true
    fi
else
    # First message of session — no heartbeat on first message, just record time
    echo "$(date +%s)" > "$LAST_HEARTBEAT_FILE"
fi

if [ "$SHOULD_HEARTBEAT" = true ]; then
    echo "$(date +%s)" > "$LAST_HEARTBEAT_FILE"
    echo ""
    echo "[HEARTBEAT — $(date '+%H:%M') check-in]: 30 minutes have passed. Briefly scan for anything time-sensitive:"
    echo "- Run 'python3 ~/.claude/skills/eng-buddy/bin/brain.py --tasks' to check tasks.db for deadlines or blockers that need attention."
    echo "- Read ~/.claude/eng-buddy/dependencies/active-blockers.md — any aging blockers to escalate?"
    # Surface HEARTBEAT.md if it exists and has content
    if [ -f "$HEARTBEAT_MD" ]; then
        HB_CONTENT=$(cat "$HEARTBEAT_MD" 2>/dev/null)
        # Check for non-trivial content (not just headers/whitespace)
        HB_ACTIONABLE=$(echo "$HB_CONTENT" | grep -v "^#" | grep -v "^[[:space:]]*$" | head -3)
        if [ -n "$HB_ACTIONABLE" ]; then
            echo "- HEARTBEAT.md has tasks configured — read it and follow any instructions."
        fi
    fi
    echo "If nothing urgent, proceed normally. If something needs attention, surface it briefly."
    echo ""
fi
