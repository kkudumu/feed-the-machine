#!/usr/bin/env bash
# PostToolUse hook: detect git commits and inject ftm-map update instructions

set -euo pipefail

# Read stdin into variable
INPUT=$(cat)

# Exit gracefully if stdin is empty or jq is unavailable
if [ -z "$INPUT" ]; then
  echo "{}"
  exit 0
fi

if ! command -v jq &>/dev/null; then
  echo "{}"
  exit 0
fi

# Extract tool_name
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

if [ -z "$TOOL_NAME" ]; then
  echo "{}"
  exit 0
fi

# Check if this is a commit operation
IS_COMMIT=0

if [ "$TOOL_NAME" = "mcp__git__git_commit" ]; then
  IS_COMMIT=1
elif [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
  if [ -n "$COMMAND" ] && echo "$COMMAND" | grep -qE '^\s*git\s+commit'; then
    IS_COMMIT=1
  fi
fi

# Exit quickly for non-commit operations
if [ "$IS_COMMIT" -eq 0 ]; then
  echo "{}"
  exit 0
fi

# Only trigger for mapped projects
if [ ! -f ".ftm-map/map.db" ]; then
  echo "{}"
  exit 0
fi

# Output additionalContext to trigger ftm-map update workflow
cat <<'EOF'
{
  "additionalContext": "A commit was just made. Run ftm-map incremental on changed files, then update INTENT.md and ARCHITECTURE.mmd via ftm-intent and ftm-diagram."
}
EOF
