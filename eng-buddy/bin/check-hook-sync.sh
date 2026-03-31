#!/bin/bash
# check-hook-sync.sh
# Verifies eng-buddy hook scripts are synchronized between:
# - Canonical source: skills/eng-buddy/hooks
# - Parent mirror: hooks
# - Runtime mirror: eng-buddy/hooks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"

CANONICAL_DIR="$SKILL_DIR/hooks"
PARENT_MIRROR_DIR="$REPO_ROOT/hooks"
RUNTIME_MIRROR_DIR="$REPO_ROOT/eng-buddy/hooks"

if [ ! -d "$CANONICAL_DIR" ]; then
  echo "ERROR: canonical hook directory not found: $CANONICAL_DIR" >&2
  exit 1
fi

tmp_source="$(mktemp)"
tmp_target="$(mktemp)"
trap 'rm -f "$tmp_source" "$tmp_target"' EXIT

list_hooks() {
  local dir="$1"
  find "$dir" -maxdepth 1 -type f -name 'eng-buddy-*.sh' -exec basename {} \; | sort
}

compare_dir() {
  local source_dir="$1"
  local target_dir="$2"
  local label="$3"
  local has_error=0

  if [ ! -d "$target_dir" ]; then
    echo "ERROR: $label missing at $target_dir"
    return 1
  fi

  list_hooks "$source_dir" > "$tmp_source"
  list_hooks "$target_dir" > "$tmp_target"

  if ! diff -u "$tmp_source" "$tmp_target" >/dev/null; then
    echo "ERROR: hook file list mismatch for $label"
    diff -u "$tmp_source" "$tmp_target" || true
    has_error=1
  fi

  while IFS= read -r file; do
    [ -n "$file" ] || continue
    if [ ! -f "$target_dir/$file" ]; then
      continue
    fi

    if ! cmp -s "$source_dir/$file" "$target_dir/$file"; then
      echo "ERROR: content mismatch in $label for $file"
      has_error=1
    fi

    if [ ! -x "$target_dir/$file" ]; then
      echo "ERROR: non-executable hook in $label: $file"
      has_error=1
    fi
  done < "$tmp_source"

  return "$has_error"
}

overall_status=0

compare_dir "$CANONICAL_DIR" "$PARENT_MIRROR_DIR" "parent hooks mirror" || overall_status=1
compare_dir "$CANONICAL_DIR" "$RUNTIME_MIRROR_DIR" "runtime hooks mirror" || overall_status=1

if [ "$overall_status" -ne 0 ]; then
  echo "Hook synchronization check failed."
  exit 1
fi

echo "Hook synchronization check passed."
