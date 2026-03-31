#!/bin/bash
# Hook: Deactivate eng-buddy auto-logging when session ends

# Only deactivate if session was active
if [ -f ~/.claude/eng-buddy/.session-active ]; then
    rm -f ~/.claude/eng-buddy/.session-active
    echo "⏸️  eng-buddy auto-logging deactivated (session ended)"
fi
