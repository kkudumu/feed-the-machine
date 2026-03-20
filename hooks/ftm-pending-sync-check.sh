#!/usr/bin/env bash
# UserPromptSubmit hook: checks for pending commit syncs from out-of-session commits

PENDING_FILE="$HOME/.claude/ftm-state/.pending-commit-syncs"

# Quick exit if no pending syncs
[ -f "$PENDING_FILE" ] || { echo '{}'; exit 0; }
[ -s "$PENDING_FILE" ] || { echo '{}'; exit 0; }

# Count pending entries
COUNT=$(wc -l < "$PENDING_FILE" | tr -d ' ')

# Read all pending entries
ENTRIES=$(cat "$PENDING_FILE")

# Consume the file (mark as processed)
rm -f "$PENDING_FILE"

# Inject context
cat <<EOJSON
{"additionalContext": "There are $COUNT pending out-of-session commits that need ftm-map incremental sync. Run ftm-map incremental for each:\n$ENTRIES"}
EOJSON
