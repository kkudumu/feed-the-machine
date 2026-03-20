#!/usr/bin/env bash
set -euo pipefail

# FTM Skills Installer
# Creates symlinks from this repo into ~/.claude/skills/ so slash commands work.
# Safe to re-run — idempotent. Run after cloning or adding new skills.
#
# Usage:
#   ./install.sh              # Install skills, hooks, and state templates
#   ./install.sh --setup-hooks  # Also merge hook config into settings.json

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
STATE_DIR="$HOME/.claude/ftm-state"
CONFIG_DIR="$HOME/.claude"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS_FILE="$CONFIG_DIR/settings.json"

SETUP_HOOKS=false
for arg in "$@"; do
  case "$arg" in
    --setup-hooks) SETUP_HOOKS=true ;;
  esac
done

echo "Installing FTM skills from: $REPO_DIR"
echo "Linking into: $SKILLS_DIR"
echo ""

mkdir -p "$SKILLS_DIR"

# --- Skills ---

# Link all ftm*.yml files
for yml in "$REPO_DIR"/ftm*.yml; do
  [ -f "$yml" ] || continue
  name=$(basename "$yml")
  # Skip ftm-config.default.yml — it's a template, not a skill
  [[ "$name" == *".default."* ]] && continue
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

# Link all ftm* directories (skills with SKILL.md)
for dir in "$REPO_DIR"/ftm*/; do
  [ -d "$dir" ] || continue
  name=$(basename "$dir")
  [ "$name" = "ftm-state" ] && continue  # state is handled separately
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

SKILL_COUNT=$(ls "$REPO_DIR"/ftm*.yml 2>/dev/null | grep -v '.default.' | wc -l | tr -d ' ')
echo ""
echo "  $SKILL_COUNT skills linked."

# --- Blackboard State ---

if [ -d "$REPO_DIR/ftm-state" ]; then
  echo ""
  mkdir -p "$STATE_DIR/blackboard/experiences"
  for f in "$REPO_DIR/ftm-state/blackboard"/*.json; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    target="$STATE_DIR/blackboard/$name"
    if [ ! -f "$target" ]; then
      cp "$f" "$target"
      echo "  INIT $name (blackboard template)"
    fi
  done
  idx="$STATE_DIR/blackboard/experiences/index.json"
  if [ ! -f "$idx" ]; then
    cp "$REPO_DIR/ftm-state/blackboard/experiences/index.json" "$idx"
    echo "  INIT experiences/index.json (blackboard template)"
  fi
fi

# --- Config ---

if [ ! -f "$CONFIG_DIR/ftm-config.yml" ] && [ -f "$REPO_DIR/ftm-config.default.yml" ]; then
  cp "$REPO_DIR/ftm-config.default.yml" "$CONFIG_DIR/ftm-config.yml"
  echo "  INIT ftm-config.yml (from default template)"
fi

# --- Hooks ---

echo ""
echo "Installing hooks..."

if [ -d "$REPO_DIR/hooks" ]; then
  mkdir -p "$HOOKS_DIR"
  HOOK_COUNT=0

  # Install shell hooks
  for hook in "$REPO_DIR/hooks"/ftm-*.sh; do
    [ -f "$hook" ] || continue
    name=$(basename "$hook")
    target="$HOOKS_DIR/$name"
    if [ -f "$target" ]; then
      cp "$hook" "$target"
      chmod +x "$target"
      echo "  UPDATE $name"
    else
      cp "$hook" "$target"
      chmod +x "$target"
      echo "  INSTALL $name"
    fi
    HOOK_COUNT=$((HOOK_COUNT + 1))
  done

  # Install Node.js hooks
  for hook in "$REPO_DIR/hooks"/ftm-*.mjs; do
    [ -f "$hook" ] || continue
    name=$(basename "$hook")
    target="$HOOKS_DIR/$name"
    if [ -f "$target" ]; then
      cp "$hook" "$target"
      echo "  UPDATE $name"
    else
      cp "$hook" "$target"
      echo "  INSTALL $name"
    fi
    HOOK_COUNT=$((HOOK_COUNT + 1))
  done

  echo ""
  echo "  $HOOK_COUNT hooks installed to $HOOKS_DIR"
fi

# --- Hook Config Merge (--setup-hooks) ---

if [ "$SETUP_HOOKS" = true ]; then
  echo ""
  echo "Setting up hook configuration in settings.json..."

  TEMPLATE="$REPO_DIR/hooks/settings-template.json"
  if [ ! -f "$TEMPLATE" ]; then
    echo "  ERROR: hooks/settings-template.json not found"
    exit 1
  fi

  if ! command -v jq &>/dev/null; then
    echo "  ERROR: jq is required for --setup-hooks. Install with: brew install jq"
    exit 1
  fi

  # Expand ~ to $HOME in the template (jq doesn't expand shell paths)
  EXPANDED_TEMPLATE=$(sed "s|~/.claude|$HOME/.claude|g" "$TEMPLATE")

  if [ ! -f "$SETTINGS_FILE" ]; then
    # No settings.json — create one from the template hooks section
    echo "$EXPANDED_TEMPLATE" | jq '{hooks: .hooks}' > "$SETTINGS_FILE"
    echo "  CREATED $SETTINGS_FILE with FTM hooks"
  else
    # Merge FTM hooks into existing settings.json
    # Strategy: for each hook event type, append FTM entries that don't already exist
    BACKUP="$SETTINGS_FILE.ftm-backup-$(date +%Y%m%d%H%M%S)"
    cp "$SETTINGS_FILE" "$BACKUP"
    echo "  BACKUP $BACKUP"

    # Extract the hooks section from the template
    TEMPLATE_HOOKS=$(echo "$EXPANDED_TEMPLATE" | jq '.hooks')

    # Read existing settings
    EXISTING=$(cat "$SETTINGS_FILE")

    # Ensure hooks key exists
    if echo "$EXISTING" | jq -e '.hooks' >/dev/null 2>&1; then
      : # hooks key exists
    else
      EXISTING=$(echo "$EXISTING" | jq '. + {hooks: {}}')
    fi

    # Merge each hook event type
    for EVENT in PreToolUse UserPromptSubmit PostToolUse Stop; do
      TEMPLATE_ENTRIES=$(echo "$TEMPLATE_HOOKS" | jq --arg e "$EVENT" '.[$e] // []')
      EXISTING_ENTRIES=$(echo "$EXISTING" | jq --arg e "$EVENT" '.hooks[$e] // []')

      # Check if any FTM hooks are already present (by checking command paths)
      FTM_COMMANDS=$(echo "$TEMPLATE_ENTRIES" | jq -r '.[].hooks[]?.command // empty' 2>/dev/null)
      ALREADY_PRESENT=false

      for cmd in $FTM_COMMANDS; do
        cmd_basename=$(basename "$cmd")
        if echo "$EXISTING_ENTRIES" | jq -r '.[].hooks[]?.command // empty' 2>/dev/null | grep -q "$cmd_basename"; then
          ALREADY_PRESENT=true
          break
        fi
      done

      if [ "$ALREADY_PRESENT" = true ]; then
        echo "  SKIP $EVENT hooks (already configured)"
        continue
      fi

      # Append template entries to existing
      MERGED=$(jq -n --argjson existing "$EXISTING_ENTRIES" --argjson template "$TEMPLATE_ENTRIES" '$existing + $template')
      EXISTING=$(echo "$EXISTING" | jq --arg e "$EVENT" --argjson m "$MERGED" '.hooks[$e] = $m')
      echo "  MERGE $EVENT hooks"
    done

    echo "$EXISTING" | jq '.' > "$SETTINGS_FILE"
    echo "  UPDATED $SETTINGS_FILE"
  fi

  echo ""
  echo "  Hooks are now active. See docs/HOOKS.md for details."
else
  echo ""
  echo "  To activate hooks, run: ./install.sh --setup-hooks"
  echo "  Or manually add entries from hooks/settings-template.json to ~/.claude/settings.json"
  echo "  See docs/HOOKS.md for details."
fi

echo ""
echo "Done. $SKILL_COUNT skills, $HOOK_COUNT hooks."
echo "Try: /ftm help"
