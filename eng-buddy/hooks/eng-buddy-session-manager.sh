#!/bin/bash
# Session management helper for eng-buddy

case "$1" in
    start)
        # Create session marker when eng-buddy starts
        touch ~/.claude/eng-buddy/.session-active
        echo "✅ eng-buddy auto-logging activated"
        ;;
    stop)
        # Remove session marker when eng-buddy ends
        rm -f ~/.claude/eng-buddy/.session-active
        echo "⏸️  eng-buddy auto-logging deactivated"
        ;;
    status)
        # Check if session is active
        if [ -f ~/.claude/eng-buddy/.session-active ]; then
            echo "✅ eng-buddy auto-logging is ACTIVE"
        else
            echo "⏸️  eng-buddy auto-logging is INACTIVE"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
