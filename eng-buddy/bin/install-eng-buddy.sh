#!/bin/bash
# One-shot eng-buddy installer for cloned repos.
# - Syncs hooks and dashboard runtime files
# - Installs/reloads poller LaunchAgents and seeds runtime/bin poller scripts
# - Starts the dashboard in the background by default

set -euo pipefail

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DASHBOARD="$CLAUDE_HOME/eng-buddy/dashboard"
OPEN_DASHBOARD="${ENG_BUDDY_OPEN_DASHBOARD:-0}"

if [[ ! -x "$SCRIPT_DIR/install-hooks.sh" ]]; then
  echo "ERROR: missing installer dependency: $SCRIPT_DIR/install-hooks.sh" >&2
  exit 1
fi

if [[ ! -x "$SCRIPT_DIR/start-pollers.sh" ]]; then
  echo "ERROR: missing installer dependency: $SCRIPT_DIR/start-pollers.sh" >&2
  exit 1
fi

echo "==> Installing eng-buddy runtime files and hooks"
bash "$SCRIPT_DIR/install-hooks.sh"

echo "==> Installing pollers and LaunchAgents"
bash "$SCRIPT_DIR/start-pollers.sh"

if [[ ! -x "$RUNTIME_DASHBOARD/start.sh" ]]; then
  echo "ERROR: runtime dashboard launcher missing: $RUNTIME_DASHBOARD/start.sh" >&2
  exit 1
fi

echo "==> Starting dashboard"
if [[ "$OPEN_DASHBOARD" == "1" ]]; then
  bash "$RUNTIME_DASHBOARD/start.sh" --ensure-open
else
  bash "$RUNTIME_DASHBOARD/start.sh" --background
fi

cat <<EOF
INSTALL_OK
Skill source: $SKILL_DIR
Claude home: $CLAUDE_HOME
Runtime dashboard: $RUNTIME_DASHBOARD
Open dashboard now: $OPEN_DASHBOARD
EOF
