#!/bin/bash
# ftm-session-end.sh
# Hook: Deactivate ftm session tracking when conversation ends
# Trigger: SessionEnd
#
# IMPORTANT: Must be listed AFTER ftm-session-snapshot.sh in settings.json
# (in a separate matcher entry). The snapshot hook reads context.json status
# to gate itself — this hook marks the session completed.

FTM_STATE="$HOME/.claude/ftm-state"
CONTEXT_JSON="$FTM_STATE/blackboard/context.json"

# Check if an active session exists
IS_ACTIVE=$(python3 -c "
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

if [ "$IS_ACTIVE" != "1" ]; then
    exit 0
fi

# Mark session as completed in context.json
python3 -c "
import json, sys
from datetime import datetime

try:
    with open('$CONTEXT_JSON') as f:
        d = json.load(f)

    if 'current_task' in d and isinstance(d['current_task'], dict):
        d['current_task']['status'] = 'completed'

    if 'session_metadata' in d and isinstance(d['session_metadata'], dict):
        d['session_metadata']['last_updated'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    with open('$CONTEXT_JSON', 'w') as f:
        json.dump(d, f, indent=2)
except Exception as e:
    sys.stderr.write(f'ftm-session-end: failed to update context.json: {e}\n')
    sys.exit(1)
" 2>/dev/null

echo "ftm session tracking deactivated (session ended)"
