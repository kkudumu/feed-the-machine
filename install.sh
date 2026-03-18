#!/usr/bin/env bash
set -euo pipefail

# Panda Skills Installer
# Creates symlinks from this repo into ~/.claude/skills/ so slash commands work.
# Safe to re-run — idempotent. Run after cloning or adding new skills.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
STATE_DIR="$HOME/.claude/panda-state"
CONFIG_DIR="$HOME/.claude"

echo "Installing panda skills from: $REPO_DIR"
echo "Linking into: $SKILLS_DIR"
echo ""

mkdir -p "$SKILLS_DIR"

# Link all panda*.yml files
for yml in "$REPO_DIR"/panda*.yml; do
  name=$(basename "$yml")
  target="$SKILLS_DIR/$name"
  if [ -L "$target" ]; then
    rm "$target"
  elif [ -f "$target" ]; then
    echo "  SKIP $name (real file exists — back it up first)"
    continue
  fi
  ln -s "$yml" "$target"
  echo "  LINK $name"
done

# Link all panda* directories (skills with SKILL.md)
for dir in "$REPO_DIR"/panda*/; do
  name=$(basename "$dir")
  [ "$name" = "panda-state" ] && continue  # state is handled separately
  target="$SKILLS_DIR/$name"
  if [ -L "$target" ]; then
    rm "$target"
  elif [ -d "$target" ]; then
    echo "  SKIP $name/ (real directory exists — back it up first)"
    continue
  fi
  ln -s "$dir" "$target"
  echo "  LINK $name/"
done

# Set up blackboard state (copy templates, don't overwrite existing data)
if [ -d "$REPO_DIR/panda-state" ]; then
  mkdir -p "$STATE_DIR/blackboard/experiences"
  for f in "$REPO_DIR/panda-state/blackboard"/*.json; do
    name=$(basename "$f")
    target="$STATE_DIR/blackboard/$name"
    if [ ! -f "$target" ]; then
      cp "$f" "$target"
      echo "  INIT $name (blackboard template)"
    fi
  done
  idx="$STATE_DIR/blackboard/experiences/index.json"
  if [ ! -f "$idx" ]; then
    cp "$REPO_DIR/panda-state/blackboard/experiences/index.json" "$idx"
    echo "  INIT experiences/index.json (blackboard template)"
  fi
fi

# Copy default config if none exists
if [ ! -f "$CONFIG_DIR/panda-config.yml" ] && [ -f "$REPO_DIR/panda-config.default.yml" ]; then
  cp "$REPO_DIR/panda-config.default.yml" "$CONFIG_DIR/panda-config.yml"
  echo "  INIT panda-config.yml (from default template)"
fi

echo ""
echo "Done. $(ls "$REPO_DIR"/panda*.yml 2>/dev/null | wc -l | tr -d ' ') skills linked."
echo "Try: /panda help"
