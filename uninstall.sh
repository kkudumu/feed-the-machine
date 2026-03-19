#!/usr/bin/env bash
set -euo pipefail

# Removes ftm skill symlinks from ~/.claude/skills/
# Only removes symlinks — never deletes real files.

SKILLS_DIR="$HOME/.claude/skills"

echo "Removing ftm skill symlinks from: $SKILLS_DIR"
echo ""

count=0
for link in "$SKILLS_DIR"/ftm*; do
  if [ -L "$link" ]; then
    name=$(basename "$link")
    rm "$link"
    echo "  UNLINK $name"
    count=$((count + 1))
  fi
done

echo ""
echo "Removed $count symlinks."
echo "Blackboard state at ~/.claude/ftm-state/ was NOT touched."
echo "Config at ~/.claude/ftm-config.yml was NOT touched."
