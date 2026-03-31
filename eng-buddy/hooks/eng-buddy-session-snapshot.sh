#!/bin/bash
# eng-buddy-session-snapshot.sh
# Hook: Session snapshot on conversation end
# Trigger: SessionEnd
#
# Captures the last 15 meaningful user/assistant exchanges as a markdown snapshot
# when an eng-buddy session ends. Fills the gap where sessions that never hit the
# compaction token threshold would lose all conversational context.
#
# Inspired by OpenClaw's session snapshot mechanism, which fires on /new or /reset.
# We fire on SessionEnd since Claude Code doesn't expose /new or /reset as hook events.
#
# Filtering:
#   - Keeps: user and assistant messages with text content
#   - Skips: tool_use blocks, tool_result blocks, system messages, slash commands
#   - Truncates: messages > 2000 chars (long pastes don't need full capture)
#
# Filename: YYYY-MM-DDTHH-MM-<topic-slug>.md  (topic derived from last user message)
#
# IMPORTANT: Must be listed BEFORE eng-buddy-session-end.sh in settings.json.
# session-end.sh removes .session-active — this hook checks for it.
#
# OUTPUT: ~/.claude/eng-buddy/sessions/
# MINIMUM: 3 meaningful messages required to write a snapshot (skip trivial sessions)
#
# FILES:
#   ~/.claude/eng-buddy/.session-active    - session gate (read only, not modified)
#   ~/.claude/eng-buddy/sessions/          - snapshot output directory

SESSION_ACTIVE="$HOME/.claude/eng-buddy/.session-active"
SESSIONS_DIR="$HOME/.claude/eng-buddy/sessions"
MAX_MESSAGES=15
MIN_MESSAGES=3

# 1. Only run during active eng-buddy sessions
if [ ! -f "$SESSION_ACTIVE" ]; then
    exit 0
fi

# 2. Read hook payload from stdin
PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
    exit 0
fi

# 3. Extract session_id and transcript_path
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

# 4. Find session JSONL
JSONL_FILE=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    JSONL_FILE="$TRANSCRIPT_PATH"
elif [ -n "$SESSION_ID" ]; then
    JSONL_FILE=$(find "$HOME/.claude/projects/" -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
fi

if [ -z "$JSONL_FILE" ] || [ ! -f "$JSONL_FILE" ]; then
    exit 0
fi

# 5. Ensure sessions directory exists
mkdir -p "$SESSIONS_DIR"

# 6. Parse JSONL, build snapshot, write file — all in one Python block
export JSONL_FILE SESSION_ID SESSIONS_DIR MAX_MESSAGES MIN_MESSAGES
python3 << 'PYEOF'
import json, sys, os, re
from datetime import datetime

jsonl_path = os.environ['JSONL_FILE']
session_id = os.environ.get('SESSION_ID', 'unknown')
sessions_dir = os.environ['SESSIONS_DIR']
max_msgs = int(os.environ.get('MAX_MESSAGES', '15'))
min_msgs = int(os.environ.get('MIN_MESSAGES', '3'))

# --- Parse JSONL ---
try:
    with open(jsonl_path) as f:
        lines = f.readlines()
except Exception:
    sys.exit(0)

messages = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue

    msg = obj.get('message', {})
    if not isinstance(msg, dict):
        continue

    role = msg.get('role', '')
    if role not in ('user', 'assistant'):
        continue

    content = msg.get('content', '')

    # Extract text content only — skip tool_use, tool_result, image blocks
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    t = block.get('text', '').strip()
                    if t:
                        text_parts.append(t)
                # skip: tool_use, tool_result, image, thinking, etc.
            elif isinstance(block, str):
                t = block.strip()
                if t:
                    text_parts.append(t)
        text = '\n'.join(text_parts)
    elif isinstance(content, str):
        text = content.strip()
    else:
        continue

    if not text:
        continue

    # Skip slash commands (e.g. /eng-buddy, /clear, /new, /compact)
    if role == 'user' and text.lstrip().startswith('/'):
        continue

    messages.append({'role': role, 'text': text})

# Take last max_msgs meaningful messages
recent = messages[-max_msgs:]

# Require minimum message count — skip trivial sessions
if len(recent) < min_msgs:
    sys.exit(0)

# --- Derive topic slug from last user message with some substance ---
topic = 'session'
for m in reversed(recent):
    if m['role'] == 'user' and len(m['text']) > 15:
        raw = m['text'][:80].lower()
        raw = re.sub(r'[^a-z0-9\s]', ' ', raw)
        raw = re.sub(r'\s+', '-', raw.strip())
        raw = re.sub(r'-+', '-', raw).strip('-')[:50].rstrip('-')
        if raw:
            topic = raw
        break

# --- Build filename and output path ---
now = datetime.now()
timestamp_file = now.strftime('%Y-%m-%dT%H-%M')
timestamp_display = now.strftime('%Y-%m-%d %H:%M')
filename = f'{timestamp_file}-{topic}.md'
output_path = os.path.join(sessions_dir, filename)

# --- Write snapshot markdown ---
lines_out = [
    f'# Session Snapshot — {timestamp_display}',
    '',
    f'**Messages captured**: {len(recent)} (last {len(recent)} of session)',
    f'**Session**: {session_id[:8]}...',
    '',
    '---',
    '',
]

for msg in recent:
    role_label = '**You**' if msg['role'] == 'user' else '**Claude**'
    text = msg['text']
    # Truncate very long messages (pasted content, etc.) to keep snapshot lean
    if len(text) > 2000:
        text = text[:2000] + '\n\n[... truncated — full content in daily log ...]'
    lines_out.append(f'{role_label}: {text}')
    lines_out.append('')

try:
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines_out))
except Exception:
    pass
PYEOF

exit 0
