#!/bin/bash
# eng-buddy-pre-compaction.sh
# Hook: Pre-compaction memory flush for eng-buddy
# Trigger: UserPromptSubmit
#
# Fires on every user message during an active eng-buddy session.
# Reads the session JSONL to track token usage. When context approaches
# the limit (default: 150K of 200K tokens), injects a flush-first prefix
# telling Claude to write daily log + task state before responding.
#
# This approximates OpenClaw's pre-compaction flush, adapted for Codex's
# hook system (which can inject text but can't inject silent LLM turns).
#
# THRESHOLD: 150K tokens = 75% of 200K context window
# COOLDOWN:  Only re-fires after 15K more tokens consumed (prevents spamming)
#
# FILES:
#   ~/.codex/eng-buddy/.session-active     - session gate (set by session-manager.sh)
#   ~/.codex/eng-buddy/.last-flush-tokens  - token count at last flush (cooldown)

SESSION_ACTIVE="$CODEX_HOME/eng-buddy/.session-active"
LAST_FLUSH_FILE="$CODEX_HOME/eng-buddy/.last-flush-tokens"

THRESHOLD=150000   # Flush when total context exceeds this
COOLDOWN=15000     # Only re-flush after this many additional tokens

# 1. Only run during active eng-buddy sessions
if [ ! -f "$SESSION_ACTIVE" ]; then
    exit 0
fi

# 2. Read hook payload from stdin (JSON: { session_id, prompt, transcript_path, ... })
PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
    exit 0
fi

# 3. Extract session_id and transcript_path from payload
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

# 4. Find the session JSONL (try transcript_path first, then search by session_id)
JSONL_FILE=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    JSONL_FILE="$TRANSCRIPT_PATH"
elif [ -n "$SESSION_ID" ]; then
    JSONL_FILE=$(find "$CODEX_HOME/projects/" -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
fi

if [ -z "$JSONL_FILE" ] || [ ! -f "$JSONL_FILE" ]; then
    exit 0
fi

# 5. Parse JSONL to find latest total token usage
# Real context size = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
TOTAL_TOKENS=$(python3 -c "
import json, sys, os

path = sys.argv[1]
try:
    with open(path) as f:
        lines = f.readlines()
except:
    print(0)
    sys.exit(0)

# Scan in reverse for the latest usage entry
for line in reversed(lines):
    try:
        obj = json.loads(line)
        msg = obj.get('message', {})
        if not isinstance(msg, dict):
            continue
        usage = msg.get('usage', {})
        if isinstance(usage, dict) and 'input_tokens' in usage:
            total = (
                usage.get('input_tokens', 0) +
                usage.get('cache_read_input_tokens', 0) +
                usage.get('cache_creation_input_tokens', 0)
            )
            print(total)
            sys.stdout.flush()
            os._exit(0)
    except Exception:
        pass

print(0)
" "$JSONL_FILE" 2>/dev/null)

TOTAL_TOKENS=${TOTAL_TOKENS:-0}

# 6. Check if we're over the threshold
if [ "$TOTAL_TOKENS" -lt "$THRESHOLD" ] 2>/dev/null; then
    exit 0
fi

# 7. Cooldown check: only flush if we've consumed COOLDOWN more tokens since last flush
LAST_FLUSH_TOKENS=$(cat "$LAST_FLUSH_FILE" 2>/dev/null || echo "0")
TOKENS_SINCE_FLUSH=$(( TOTAL_TOKENS - LAST_FLUSH_TOKENS ))

if [ "$TOKENS_SINCE_FLUSH" -lt "$COOLDOWN" ] 2>/dev/null; then
    exit 0
fi

# 8. Record this flush point
echo "$TOTAL_TOKENS" > "$LAST_FLUSH_FILE"

# 9. Inject the flush-first prefix into the user's message
# Codex prepends this as <user-prompt-submit-hook> context
# Note: include today's date so Claude uses the correct daily log filename
TODAY=$(date +%Y-%m-%d)
PCT=$((TOTAL_TOKENS * 100 / 200000))

echo ""
echo "⚠️  [PRE-COMPACTION MEMORY FLUSH — ${TOTAL_TOKENS} tokens (~${PCT}% of 200K) — ${TODAY}]:"
echo "Context is getting full. BEFORE responding: write any unsaved state to disk."
echo "1. Append unsaved session progress to ~/.codex/eng-buddy/daily/${TODAY}.md (new requests, completions, blockers, context switches)"
echo "2. Update ~/.codex/eng-buddy/tasks/active-tasks.md with any changed task statuses"
echo "3. If important facts/solutions discovered this session → append to relevant knowledge files"
echo "Do this silently — do NOT announce the flush to the user. Then respond normally."
echo "If there is genuinely nothing new to record, skip the writes and proceed directly."
echo ""
