#!/usr/bin/env bash
# UserPromptSubmit hook: auto-detect unmapped projects when ftm skills are invoked.
# Detects greenfield vs brownfield and injects instructions to bootstrap ftm-map.
# Only fires once per project (writes .ftm-map/.offered marker).

set -euo pipefail

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null)

# Quick exit if no prompt or jq unavailable
[ -n "$PROMPT" ] || exit 0

# Only fire on ftm-related invocations
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')
IS_FTM=false
for trigger in "/ftm" "ftm-" "brainstorm" "research" "debug this" "audit" "deep dive" "investigate"; do
  if [[ "$PROMPT_LOWER" == *"$trigger"* ]]; then
    IS_FTM=true
    break
  fi
done
$IS_FTM || exit 0

# Already mapped — nothing to do
[ -f ".ftm-map/map.db" ] && exit 0

# Already offered for this project — don't nag
[ -f ".ftm-map/.offered" ] && exit 0

# --- Greenfield vs Brownfield detection ---

# Count source files (fast, capped at 500 to avoid slow ls on huge repos)
SRC_COUNT=0
if command -v find &>/dev/null; then
  SRC_COUNT=$(find . -maxdepth 4 \
    \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.tsx" \
       -o -name "*.jsx" -o -name "*.go" -o -name "*.rs" -o -name "*.swift" \
       -o -name "*.java" -o -name "*.rb" -o -name "*.sh" -o -name "*.mjs" \
       -o -name "*.cjs" \) \
    -not -path "*/node_modules/*" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.git/*" \
    -not -path "*/.worktrees/*" \
    2>/dev/null | head -500 | wc -l | tr -d ' ')
fi

# Git history depth
COMMIT_COUNT=0
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
fi

# Classify
if [ "$SRC_COUNT" -le 5 ] && [ "$COMMIT_COUNT" -le 3 ]; then
  PROJECT_TYPE="greenfield"
  PROJECT_DESC="Greenfield project (~${SRC_COUNT} source files, ${COMMIT_COUNT} commits). Small enough to index instantly."
elif [ "$SRC_COUNT" -le 50 ]; then
  PROJECT_TYPE="small-brownfield"
  PROJECT_DESC="Small brownfield project (~${SRC_COUNT} source files, ${COMMIT_COUNT} commits). Quick to index."
elif [ "$SRC_COUNT" -le 200 ]; then
  PROJECT_TYPE="medium-brownfield"
  PROJECT_DESC="Medium brownfield project (~${SRC_COUNT} source files, ${COMMIT_COUNT} commits). Index takes ~30s."
else
  PROJECT_TYPE="large-brownfield"
  PROJECT_DESC="Large brownfield project (~${SRC_COUNT} source files, ${COMMIT_COUNT} commits). Index may take 1-2 min."
fi

# Write marker so we don't ask again
mkdir -p .ftm-map
echo "$PROJECT_TYPE" > .ftm-map/.offered

# Inject context
cat <<EOJSON
{
  "additionalContext": "[ftm-map-autodetect] This project has no code knowledge graph yet (.ftm-map/map.db missing). ${PROJECT_DESC} Before proceeding with the ftm skill, bootstrap the map: run \`ftm-map/scripts/setup.sh\` then \`ftm-map/scripts/.venv/bin/python3 ftm-map/scripts/index.py --bootstrap .\` in the background. This enables structural queries (blast radius, dependency chains) and keeps INTENT.md/ARCHITECTURE.mmd in sync via the post-commit hook. If the user's request is time-sensitive, proceed with the skill and index in parallel."
}
EOJSON
