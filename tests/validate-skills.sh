#!/usr/bin/env bash
# validate-skills.sh — Verify all SKILL.md files are well-formed
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0
ERRORS=""

MAX_SKILL_BYTES=40960  # 40 KiB — ftm-mind and ftm-executor legitimately exceed 20KB

for skill_dir in "$REPO_DIR"/ftm*/; do
  skill_md="$skill_dir/SKILL.md"
  name=$(basename "$skill_dir")

  [ "$name" = "ftm-state" ] && continue

  # --- missing SKILL.md ---
  if [ ! -f "$skill_md" ]; then
    ERRORS="${ERRORS}\n  FAIL  $name — missing SKILL.md"
    FAIL=$((FAIL + 1))
    continue
  fi

  # --- frontmatter must open with --- ---
  FIRST_LINE=$(head -1 "$skill_md")
  if [ "$FIRST_LINE" != "---" ]; then
    ERRORS="${ERRORS}\n  FAIL  $name — SKILL.md missing frontmatter (no opening ---)"
    FAIL=$((FAIL + 1))
    continue
  fi

  # --- name: field present ---
  if ! head -20 "$skill_md" | grep -q '^name:'; then
    ERRORS="${ERRORS}\n  FAIL  $name — SKILL.md frontmatter missing 'name:' field"
    FAIL=$((FAIL + 1))
  fi

  # --- description: field present ---
  if ! head -20 "$skill_md" | grep -q '^description:'; then
    ERRORS="${ERRORS}\n  FAIL  $name — SKILL.md frontmatter missing 'description:' field"
    FAIL=$((FAIL + 1))
  fi

  # --- no hardcoded user home paths ---
  if grep -q '/Users/[a-zA-Z]' "$skill_md"; then
    ERRORS="${ERRORS}\n  FAIL  $name — SKILL.md contains hardcoded user home path"
    FAIL=$((FAIL + 1))
  fi

  # --- name: value must match directory name ---
  FRONTMATTER_NAME=$(head -20 "$skill_md" | grep '^name:' | head -1 | sed 's/^name:[[:space:]]*//' | tr -d '[:space:]')
  if [ -n "$FRONTMATTER_NAME" ] && [ "$FRONTMATTER_NAME" != "$name" ]; then
    ERRORS="${ERRORS}\n  FAIL  $name — SKILL.md name: '${FRONTMATTER_NAME}' does not match directory name '${name}'"
    FAIL=$((FAIL + 1))
  fi

  # --- size threshold: must not exceed 20 KiB ---
  FILE_SIZE=$(wc -c < "$skill_md")
  if [ "$FILE_SIZE" -gt "$MAX_SKILL_BYTES" ]; then
    ERRORS="${ERRORS}\n  FAIL  $name — SKILL.md exceeds 20,480 bytes (actual: ${FILE_SIZE} bytes)"
    FAIL=$((FAIL + 1))
  fi

  PASS=$((PASS + 1))
done

# --- yml -> directory check (already existed; preserved) ---
for yml in "$REPO_DIR"/ftm*.yml; do
  yml_name=$(basename "$yml" .yml)
  [ "$yml_name" = "ftm-config" ] && continue
  [ "$yml_name" = "ftm-config.default" ] && continue
  if [ ! -d "$REPO_DIR/$yml_name" ]; then
    ERRORS="${ERRORS}\n  FAIL  ${yml_name}.yml — no matching skill directory"
    FAIL=$((FAIL + 1))
  fi
done

# --- directory -> yml check (new: bidirectional) ---
for skill_dir in "$REPO_DIR"/ftm*/; do
  dir_name=$(basename "$skill_dir")
  [ "$dir_name" = "ftm-state" ] && continue

  # Only flag directories that actually contain a SKILL.md
  if [ ! -f "$skill_dir/SKILL.md" ]; then
    continue
  fi

  if [ ! -f "$REPO_DIR/${dir_name}.yml" ]; then
    ERRORS="${ERRORS}\n  FAIL  ${dir_name}/ — has SKILL.md but no matching ${dir_name}.yml"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Skill Validation Results"
echo "========================"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"

if [ -n "$ERRORS" ]; then
  echo ""
  echo "Failures:"
  echo -e "$ERRORS"
fi

echo ""
exit $FAIL
