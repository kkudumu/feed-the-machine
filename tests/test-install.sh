#!/usr/bin/env bash
# tests/test-install.sh — Tests for install.sh and uninstall.sh behavior
# Verifies symlink creation, idempotency, selective preservation, and uninstall cleanup.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_SCRIPT="$REPO_DIR/install.sh"
UNINSTALL_SCRIPT="$REPO_DIR/uninstall.sh"

PASS=0
FAIL=0
ERRORS=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pass() {
  local name="$1"
  echo "  PASS  $name"
  PASS=$((PASS + 1))
}

fail() {
  local name="$1"
  local reason="$2"
  echo "  FAIL  $name"
  echo "        $reason"
  ERRORS="${ERRORS}\n  FAIL  $name — $reason"
  FAIL=$((FAIL + 1))
}

assert_true() {
  local label="$1"
  local condition="$2"   # a bash command to evaluate; pass=0 exit, fail=non-zero
  if eval "$condition"; then
    pass "$label"
  else
    fail "$label" "condition was false: $condition"
  fi
}

assert_false() {
  local label="$1"
  local condition="$2"
  if eval "$condition"; then
    fail "$label" "expected false but condition was true: $condition"
  else
    pass "$label"
  fi
}

assert_symlink() {
  local label="$1"
  local path="$2"
  if [ -L "$path" ]; then
    pass "$label"
  else
    fail "$label" "expected symlink at $path but not found (or is a regular file/dir)"
  fi
}

assert_not_exists() {
  local label="$1"
  local path="$2"
  if [ -e "$path" ] || [ -L "$path" ]; then
    fail "$label" "expected path to be absent: $path"
  else
    pass "$label"
  fi
}

assert_regular_file() {
  local label="$1"
  local path="$2"
  if [ -f "$path" ] && [ ! -L "$path" ]; then
    pass "$label"
  else
    fail "$label" "expected a real (non-symlink) file at $path"
  fi
}

# Run install.sh with HOME overridden to the temp dir.
run_install() {
  local fake_home="$1"
  HOME="$fake_home" bash "$INSTALL_SCRIPT" > /dev/null 2>&1
}

# Run uninstall.sh with HOME overridden to the temp dir.
run_uninstall() {
  local fake_home="$1"
  HOME="$fake_home" bash "$UNINSTALL_SCRIPT" > /dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Setup: create a temp HOME directory that mimics ~/.claude
# ---------------------------------------------------------------------------

TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

FAKE_HOME="$TMPDIR_ROOT/home"
FAKE_CLAUDE="$FAKE_HOME/.claude"
FAKE_SKILLS="$FAKE_CLAUDE/skills"
FAKE_STATE="$FAKE_CLAUDE/panda-state"

mkdir -p "$FAKE_SKILLS"

echo ""
echo "Install / Uninstall Tests"
echo "========================="

# ---------------------------------------------------------------------------
# Test group: install.sh — symlink creation
# ---------------------------------------------------------------------------

echo ""
echo "--- install.sh creates expected symlinks"

run_install "$FAKE_HOME"

# Every panda*.yml in the repo should be symlinked into FAKE_SKILLS
YML_COUNT=0
YML_MISSING=0
for yml in "$REPO_DIR"/panda*.yml; do
  name=$(basename "$yml")
  target="$FAKE_SKILLS/$name"
  YML_COUNT=$((YML_COUNT + 1))
  if ! [ -L "$target" ]; then
    YML_MISSING=$((YML_MISSING + 1))
    fail "symlink for $name created by install" "not a symlink at $target"
  fi
done

if [ "$YML_MISSING" -eq 0 ]; then
  pass "all $YML_COUNT panda*.yml files symlinked into skills dir"
fi

# Every panda* directory (except panda-state) should be symlinked
DIR_COUNT=0
DIR_MISSING=0
for dir in "$REPO_DIR"/panda*/; do
  name=$(basename "$dir")
  [ "$name" = "panda-state" ] && continue
  target="$FAKE_SKILLS/$name"
  DIR_COUNT=$((DIR_COUNT + 1))
  if ! [ -L "$target" ]; then
    DIR_MISSING=$((DIR_MISSING + 1))
    fail "symlink for $name/ created by install" "not a symlink at $target"
  fi
done

if [ "$DIR_MISSING" -eq 0 ]; then
  pass "all $DIR_COUNT panda* skill directories symlinked into skills dir"
fi

# panda-state directory itself must NOT be symlinked into skills dir
assert_not_exists \
  "panda-state is not symlinked into skills dir" \
  "$FAKE_SKILLS/panda-state"

# ---------------------------------------------------------------------------
# Test group: install.sh — symlinks resolve to correct targets
# ---------------------------------------------------------------------------

echo ""
echo "--- symlinks resolve to correct repo targets"

# Spot-check a few known skills
for name in panda.yml panda-executor.yml panda-audit.yml; do
  target="$FAKE_SKILLS/$name"
  if [ -L "$target" ]; then
    resolved="$(readlink "$target")"
    if [ "$resolved" = "$REPO_DIR/$name" ]; then
      pass "symlink $name points to repo source ($REPO_DIR/$name)"
    else
      fail "symlink $name points to correct source" "got $resolved, expected $REPO_DIR/$name"
    fi
  fi
done

for name in panda-executor panda-audit panda-mind; do
  target="$FAKE_SKILLS/$name"
  if [ -L "$target" ]; then
    resolved="$(readlink "$target")"
    # Directory symlinks point to the directory with trailing slash from the glob
    if echo "$resolved" | grep -q "$REPO_DIR/$name"; then
      pass "symlink $name/ points to repo source"
    else
      fail "symlink $name/ points to correct source" "got $resolved, expected path containing $REPO_DIR/$name"
    fi
  fi
done

# ---------------------------------------------------------------------------
# Test group: install.sh — SKILL.md files are accessible through symlinks
# ---------------------------------------------------------------------------

echo ""
echo "--- SKILL.md files accessible through symlinks"

for dir in "$REPO_DIR"/panda*/; do
  name=$(basename "$dir")
  [ "$name" = "panda-state" ] && continue

  skill_md_in_repo="$dir/SKILL.md"
  [ ! -f "$skill_md_in_repo" ] && continue

  skill_md_via_link="$FAKE_SKILLS/$name/SKILL.md"
  if [ -f "$skill_md_via_link" ]; then
    pass "SKILL.md accessible via symlink for $name"
  else
    fail "SKILL.md accessible via symlink for $name" "$skill_md_via_link not readable"
  fi
done

# ---------------------------------------------------------------------------
# Test group: install.sh — blackboard state initialization
# ---------------------------------------------------------------------------

echo ""
echo "--- blackboard state initialized"

assert_true \
  "blackboard directory created at panda-state/blackboard" \
  "[ -d '$FAKE_STATE/blackboard' ]"

assert_true \
  "blackboard/experiences directory created" \
  "[ -d '$FAKE_STATE/blackboard/experiences' ]"

# Template files should be copied (not symlinked) — install preserves data
for fname in context.json patterns.json; do
  assert_regular_file \
    "blackboard/$fname copied as real file (not symlink)" \
    "$FAKE_STATE/blackboard/$fname"
done

assert_regular_file \
  "blackboard/experiences/index.json copied as real file" \
  "$FAKE_STATE/blackboard/experiences/index.json"

# Verify copied files are valid JSON
for fname in context.json patterns.json; do
  fpath="$FAKE_STATE/blackboard/$fname"
  if python3 -c "import json,sys; json.load(open('$fpath'))" 2>/dev/null; then
    pass "copied blackboard/$fname is valid JSON"
  else
    fail "copied blackboard/$fname is valid JSON" "file failed JSON parse"
  fi
done

if python3 -c "import json,sys; json.load(open('$FAKE_STATE/blackboard/experiences/index.json'))" 2>/dev/null; then
  pass "copied experiences/index.json is valid JSON"
else
  fail "copied experiences/index.json is valid JSON" "file failed JSON parse"
fi

# ---------------------------------------------------------------------------
# Test group: install.sh — default config initialization
# ---------------------------------------------------------------------------

echo ""
echo "--- panda-config.yml initialized from default"

if [ -f "$REPO_DIR/panda-config.default.yml" ]; then
  assert_regular_file \
    "panda-config.yml created at ~/.claude/ from default template" \
    "$FAKE_CLAUDE/panda-config.yml"
else
  echo "  SKIP  panda-config.default.yml not present in repo — skipping config test"
fi

# ---------------------------------------------------------------------------
# Test group: install.sh — idempotency (safe to re-run)
# ---------------------------------------------------------------------------

echo ""
echo "--- install.sh idempotency (re-run is safe)"

# Record the readlink target for a yml before second run
SAMPLE_YML="panda.yml"
LINK_BEFORE="$(readlink "$FAKE_SKILLS/$SAMPLE_YML" 2>/dev/null || echo "missing")"

# Run install a second time
run_install "$FAKE_HOME"

LINK_AFTER="$(readlink "$FAKE_SKILLS/$SAMPLE_YML" 2>/dev/null || echo "missing")"

if [ "$LINK_BEFORE" = "$LINK_AFTER" ]; then
  pass "second install run preserves existing symlink targets"
else
  fail "second install run preserves existing symlink targets" \
    "symlink changed: before=$LINK_BEFORE after=$LINK_AFTER"
fi

# Blackboard data should not be overwritten if it already exists
CONTEXT_PATH="$FAKE_STATE/blackboard/context.json"
# Write a sentinel value to context.json
python3 -c "
import json
with open('$CONTEXT_PATH') as f:
    data = json.load(f)
data['session_metadata']['messages_count'] = 99
with open('$CONTEXT_PATH', 'w') as f:
    json.dump(data, f)
"

run_install "$FAKE_HOME"

MESSAGES_COUNT="$(python3 -c "import json; d=json.load(open('$CONTEXT_PATH')); print(d['session_metadata']['messages_count'])")"
if [ "$MESSAGES_COUNT" = "99" ]; then
  pass "re-running install does not overwrite existing blackboard data"
else
  fail "re-running install does not overwrite existing blackboard data" \
    "expected messages_count=99 but got $MESSAGES_COUNT (data was overwritten)"
fi

# config file should not be overwritten if it already exists
if [ -f "$FAKE_CLAUDE/panda-config.yml" ]; then
  echo "sentinel-do-not-overwrite: true" >> "$FAKE_CLAUDE/panda-config.yml"
  run_install "$FAKE_HOME"
  if grep -q "sentinel-do-not-overwrite" "$FAKE_CLAUDE/panda-config.yml"; then
    pass "re-running install does not overwrite existing panda-config.yml"
  else
    fail "re-running install does not overwrite existing panda-config.yml" \
      "sentinel line was removed — config was overwritten"
  fi
fi

# ---------------------------------------------------------------------------
# Test group: install.sh — does not create real files in skills dir
# ---------------------------------------------------------------------------

echo ""
echo "--- install.sh only creates symlinks (no real files copied to skills dir)"

for entry in "$FAKE_SKILLS"/panda*; do
  [ -e "$entry" ] || continue
  name=$(basename "$entry")
  if [ ! -L "$entry" ]; then
    fail "skills dir contains only symlinks" \
      "$name is a real file/dir in skills dir, expected symlink"
  fi
done
pass "all panda* entries in skills dir are symlinks"

# ---------------------------------------------------------------------------
# Test group: uninstall.sh — removes all panda* symlinks
# ---------------------------------------------------------------------------

echo ""
echo "--- uninstall.sh removes panda* symlinks"

# Count symlinks before uninstall
BEFORE_COUNT=0
for link in "$FAKE_SKILLS"/panda*; do
  [ -L "$link" ] && BEFORE_COUNT=$((BEFORE_COUNT + 1))
done

run_uninstall "$FAKE_HOME"

AFTER_COUNT=0
for link in "$FAKE_SKILLS"/panda*; do
  [ -L "$link" ] 2>/dev/null && AFTER_COUNT=$((AFTER_COUNT + 1)) || true
done

if [ "$AFTER_COUNT" -eq 0 ]; then
  pass "uninstall removes all $BEFORE_COUNT panda* symlinks from skills dir"
else
  fail "uninstall removes all panda* symlinks" \
    "$AFTER_COUNT symlink(s) remain after uninstall"
fi

# ---------------------------------------------------------------------------
# Test group: uninstall.sh — preserves blackboard state
# ---------------------------------------------------------------------------

echo ""
echo "--- uninstall.sh does not touch panda-state data"

assert_true \
  "panda-state/blackboard directory preserved after uninstall" \
  "[ -d '$FAKE_STATE/blackboard' ]"

assert_true \
  "panda-state/blackboard/context.json preserved after uninstall" \
  "[ -f '$FAKE_STATE/blackboard/context.json' ]"

assert_true \
  "panda-state/blackboard/patterns.json preserved after uninstall" \
  "[ -f '$FAKE_STATE/blackboard/patterns.json' ]"

assert_true \
  "panda-state/blackboard/experiences/index.json preserved after uninstall" \
  "[ -f '$FAKE_STATE/blackboard/experiences/index.json' ]"

# Confirm our sentinel value survived uninstall
MESSAGES_AFTER="$(python3 -c "import json; d=json.load(open('$CONTEXT_PATH')); print(d['session_metadata']['messages_count'])")"
if [ "$MESSAGES_AFTER" = "99" ]; then
  pass "blackboard context.json data unchanged after uninstall"
else
  fail "blackboard context.json data unchanged after uninstall" \
    "expected messages_count=99 but got $MESSAGES_AFTER"
fi

# ---------------------------------------------------------------------------
# Test group: uninstall.sh — preserves panda-config.yml
# ---------------------------------------------------------------------------

echo ""
echo "--- uninstall.sh does not touch panda-config.yml"

if [ -f "$FAKE_CLAUDE/panda-config.yml" ]; then
  assert_regular_file \
    "panda-config.yml survives uninstall" \
    "$FAKE_CLAUDE/panda-config.yml"

  if grep -q "sentinel-do-not-overwrite" "$FAKE_CLAUDE/panda-config.yml"; then
    pass "panda-config.yml content unchanged after uninstall"
  else
    fail "panda-config.yml content unchanged after uninstall" \
      "sentinel line missing — file was modified"
  fi
fi

# ---------------------------------------------------------------------------
# Test group: uninstall.sh — only removes symlinks, never real files
# ---------------------------------------------------------------------------

echo ""
echo "--- uninstall.sh only removes symlinks, never real files"

# Plant a real file named panda-custom.yml in skills dir before uninstall
REAL_FILE="$FAKE_SKILLS/panda-custom.yml"
echo "name: panda-custom" > "$REAL_FILE"

# Re-install to recreate symlinks, then uninstall again
run_install "$FAKE_HOME"
run_uninstall "$FAKE_HOME"

if [ -f "$REAL_FILE" ] && [ ! -L "$REAL_FILE" ]; then
  pass "uninstall preserves real files in skills dir (not symlinks)"
else
  fail "uninstall preserves real files in skills dir" \
    "$REAL_FILE was removed (should only remove symlinks)"
fi

# ---------------------------------------------------------------------------
# Test group: install + uninstall + reinstall cycle
# ---------------------------------------------------------------------------

echo ""
echo "--- install/uninstall/reinstall cycle"

# Uninstall (symlinks already gone from prior uninstall above)
# Reinstall fresh
run_install "$FAKE_HOME"

REINSTALL_COUNT=0
for link in "$FAKE_SKILLS"/panda*; do
  [ -L "$link" ] && REINSTALL_COUNT=$((REINSTALL_COUNT + 1)) || true
done

if [ "$REINSTALL_COUNT" -ge "$BEFORE_COUNT" ]; then
  pass "reinstall after uninstall recreates all symlinks ($REINSTALL_COUNT links)"
else
  fail "reinstall after uninstall recreates all symlinks" \
    "expected at least $BEFORE_COUNT, got $REINSTALL_COUNT"
fi

# SKILL.md files still accessible after reinstall
for dir in "$REPO_DIR"/panda*/; do
  name=$(basename "$dir")
  [ "$name" = "panda-state" ] && continue
  skill_md_in_repo="$dir/SKILL.md"
  [ ! -f "$skill_md_in_repo" ] && continue

  skill_md_via_link="$FAKE_SKILLS/$name/SKILL.md"
  if [ ! -f "$skill_md_via_link" ]; then
    fail "SKILL.md accessible after reinstall for $name" "$skill_md_via_link not readable"
  fi
done
pass "all SKILL.md files accessible through symlinks after reinstall"

# ---------------------------------------------------------------------------
# Test group: uninstall.sh — no skills dir does not abort
# ---------------------------------------------------------------------------

echo ""
echo "--- uninstall.sh handles missing skills dir gracefully"

EMPTY_HOME="$TMPDIR_ROOT/empty-home"
mkdir -p "$EMPTY_HOME/.claude/skills"

# Run uninstall with no panda* symlinks — should exit 0
if HOME="$EMPTY_HOME" bash "$UNINSTALL_SCRIPT" > /dev/null 2>&1; then
  pass "uninstall exits 0 when no panda* symlinks exist"
else
  fail "uninstall exits 0 when no panda* symlinks exist" \
    "uninstall.sh returned non-zero for empty skills dir"
fi

# ---------------------------------------------------------------------------
# Test group: install.sh exits non-zero on permission error
# ---------------------------------------------------------------------------

echo ""
echo "--- install.sh with unreadable repo dir"

# We skip this on CI/root environments where chmod restrictions may not apply
if [ "$(id -u)" != "0" ]; then
  UNREADABLE_HOME="$TMPDIR_ROOT/unreadable-home"
  mkdir -p "$UNREADABLE_HOME/.claude/skills"

  # Make the skills dir unwriteable
  chmod 555 "$UNREADABLE_HOME/.claude/skills"

  # install.sh tries to create symlinks and should fail
  if HOME="$UNREADABLE_HOME" bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
    fail "install.sh exits non-zero when skills dir is unwriteable" \
      "install.sh exited 0 despite unwriteable target dir"
  else
    pass "install.sh exits non-zero when skills dir is unwriteable"
  fi

  chmod 755 "$UNREADABLE_HOME/.claude/skills"
else
  echo "  SKIP  permission test skipped (running as root)"
fi

# ---------------------------------------------------------------------------
# Test group: install.sh — skills dir created if missing
# ---------------------------------------------------------------------------

echo ""
echo "--- install.sh creates skills dir if not present"

FRESH_HOME="$TMPDIR_ROOT/fresh-home"
mkdir -p "$FRESH_HOME/.claude"
# Intentionally do NOT create $FRESH_HOME/.claude/skills

run_install "$FRESH_HOME"

assert_true \
  "install.sh creates ~/.claude/skills when missing" \
  "[ -d '$FRESH_HOME/.claude/skills' ]"

FRESH_LINK_COUNT=0
for link in "$FRESH_HOME/.claude/skills"/panda*; do
  [ -L "$link" ] 2>/dev/null && FRESH_LINK_COUNT=$((FRESH_LINK_COUNT + 1)) || true
done

if [ "$FRESH_LINK_COUNT" -gt 0 ]; then
  pass "install.sh creates symlinks in freshly created skills dir ($FRESH_LINK_COUNT links)"
else
  fail "install.sh creates symlinks in freshly created skills dir" \
    "no panda* symlinks found after install to fresh dir"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Failures:"
  echo -e "$ERRORS"
  echo ""
  exit 1
fi

echo ""
exit 0
