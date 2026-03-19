#!/usr/bin/env bash
# tests/test-blackboard.sh — Tests for blackboard data mechanics
# Validates that JSON schema enforcement catches invalid data and accepts valid data.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCHEMAS="$REPO_DIR/ftm-state/schemas"
BLACKBOARD_TEMPLATES="$REPO_DIR/ftm-state/blackboard"

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

# Run ajv validate; return exit code without aborting the script.
ajv_exit_code() {
  local schema="$1"
  local data="$2"
  npx ajv validate \
    -s "$schema" \
    -d "$data" \
    --errors=text \
    --validate-formats=false \
    2>/dev/null
  return $?
}

# Wrapper that captures pass/fail without killing the test runner.
assert_valid() {
  local label="$1"
  local schema="$2"
  local data="$3"
  if ajv_exit_code "$schema" "$data"; then
    pass "$label"
  else
    fail "$label" "expected ajv to exit 0 (valid), but it exited non-zero"
  fi
}

assert_invalid() {
  local label="$1"
  local schema="$2"
  local data="$3"
  if ajv_exit_code "$schema" "$data"; then
    fail "$label" "expected ajv to exit non-zero (invalid), but it exited 0"
  else
    pass "$label"
  fi
}

# ---------------------------------------------------------------------------
# Setup: temp working directory
# ---------------------------------------------------------------------------

TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

TMPBB="$TMPDIR_ROOT/blackboard"
mkdir -p "$TMPBB/experiences"

# Seed the temp dir with template files
cp "$BLACKBOARD_TEMPLATES/context.json" "$TMPBB/context.json"
cp "$BLACKBOARD_TEMPLATES/patterns.json" "$TMPBB/patterns.json"
cp "$BLACKBOARD_TEMPLATES/experiences/index.json" "$TMPBB/experiences/index.json"

echo ""
echo "Blackboard Tests"
echo "================"

# ---------------------------------------------------------------------------
# Test group: Template files pass validation (sanity check)
# ---------------------------------------------------------------------------

echo ""
echo "--- Template validation (schema sanity)"

assert_valid \
  "context template validates against context.schema.json" \
  "$SCHEMAS/context.schema.json" \
  "$TMPBB/context.json"

assert_valid \
  "experience index template validates against experience-index.schema.json" \
  "$SCHEMAS/experience-index.schema.json" \
  "$TMPBB/experiences/index.json"

assert_valid \
  "patterns template validates against patterns.schema.json" \
  "$SCHEMAS/patterns.schema.json" \
  "$TMPBB/patterns.json"

# ---------------------------------------------------------------------------
# Test group: Write valid experience entry
# ---------------------------------------------------------------------------

echo ""
echo "--- Valid experience entry"

VALID_EXP="$TMPBB/experiences/2026-03-18_test-feature.json"
cat > "$VALID_EXP" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Add blackboard test harness for schema validation",
  "agent_team": ["backend-architect", "test-writer-fixer"],
  "wave_count": 2,
  "audit_outcomes": {
    "pass": 5,
    "auto_fix": 1,
    "fail": 0
  },
  "lessons_learned": [
    "Always run schema validation before writing to ftm-state",
    "Experience files must include task_type and timestamp"
  ],
  "timestamp": "2026-03-18T10:00:00Z",
  "confidence": 0.85,
  "tags": ["blackboard", "schema", "testing"]
}
EOF

assert_valid \
  "valid experience entry passes experience.schema.json" \
  "$SCHEMAS/experience.schema.json" \
  "$VALID_EXP"

# Update the index to reference the new entry and validate that too
VALID_INDEX="$TMPBB/experiences/index.json"
cat > "$VALID_INDEX" <<'EOF'
{
  "entries": [
    {
      "id": "2026-03-18_test-feature",
      "file": "2026-03-18_test-feature.json",
      "task_type": "feature",
      "tags": ["blackboard", "schema", "testing"],
      "timestamp": "2026-03-18T10:00:00Z",
      "confidence": 0.85
    }
  ],
  "metadata": {
    "total_count": 1,
    "last_updated": "2026-03-18T10:00:00Z",
    "max_entries": 200,
    "pruning_strategy": "remove_oldest_low_confidence"
  }
}
EOF

assert_valid \
  "updated experience index with one entry passes schema" \
  "$SCHEMAS/experience-index.schema.json" \
  "$VALID_INDEX"

# ---------------------------------------------------------------------------
# Test group: Minimum-field experience entry (only required fields)
# ---------------------------------------------------------------------------

echo ""
echo "--- Minimum required fields"

MIN_EXP="$TMPBB/experiences/2026-03-18_minimal.json"
cat > "$MIN_EXP" <<'EOF'
{
  "task_type": "bugfix",
  "task_description": "Minimal required fields only",
  "timestamp": "2026-03-18T12:00:00Z"
}
EOF

assert_valid \
  "experience with only required fields (task_type, task_description, timestamp) is valid" \
  "$SCHEMAS/experience.schema.json" \
  "$MIN_EXP"

# ---------------------------------------------------------------------------
# Test group: Experience entry missing required fields
# ---------------------------------------------------------------------------

echo ""
echo "--- Missing required fields (should fail)"

MISSING_TASK_TYPE="$TMPBB/experiences/bad-missing-task-type.json"
cat > "$MISSING_TASK_TYPE" <<'EOF'
{
  "task_description": "Missing task_type field",
  "timestamp": "2026-03-18T10:00:00Z"
}
EOF

assert_invalid \
  "experience missing task_type fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$MISSING_TASK_TYPE"

MISSING_TIMESTAMP="$TMPBB/experiences/bad-missing-timestamp.json"
cat > "$MISSING_TIMESTAMP" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Missing timestamp field"
}
EOF

assert_invalid \
  "experience missing timestamp fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$MISSING_TIMESTAMP"

MISSING_DESCRIPTION="$TMPBB/experiences/bad-missing-description.json"
cat > "$MISSING_DESCRIPTION" <<'EOF'
{
  "task_type": "refactor",
  "timestamp": "2026-03-18T10:00:00Z"
}
EOF

assert_invalid \
  "experience missing task_description fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$MISSING_DESCRIPTION"

EMPTY_OBJECT="$TMPBB/experiences/bad-empty.json"
echo '{}' > "$EMPTY_OBJECT"

assert_invalid \
  "empty experience object fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$EMPTY_OBJECT"

# ---------------------------------------------------------------------------
# Test group: Experience with extra/unknown fields (additionalProperties: false)
# ---------------------------------------------------------------------------

echo ""
echo "--- Additional properties not allowed"

EXTRA_FIELDS="$TMPBB/experiences/bad-extra-fields.json"
cat > "$EXTRA_FIELDS" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Has extra field",
  "timestamp": "2026-03-18T10:00:00Z",
  "invented_field": "this should not be here"
}
EOF

assert_invalid \
  "experience with extra unknown field fails schema (additionalProperties: false)" \
  "$SCHEMAS/experience.schema.json" \
  "$EXTRA_FIELDS"

# ---------------------------------------------------------------------------
# Test group: Experience boundary values on numeric fields
# ---------------------------------------------------------------------------

echo ""
echo "--- Numeric field boundary values"

CONFIDENCE_ZERO="$TMPBB/experiences/confidence-zero.json"
cat > "$CONFIDENCE_ZERO" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Confidence at minimum boundary (0.0)",
  "timestamp": "2026-03-18T10:00:00Z",
  "confidence": 0.0
}
EOF

assert_valid \
  "experience with confidence=0.0 (minimum) is valid" \
  "$SCHEMAS/experience.schema.json" \
  "$CONFIDENCE_ZERO"

CONFIDENCE_ONE="$TMPBB/experiences/confidence-one.json"
cat > "$CONFIDENCE_ONE" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Confidence at maximum boundary (1.0)",
  "timestamp": "2026-03-18T10:00:00Z",
  "confidence": 1.0
}
EOF

assert_valid \
  "experience with confidence=1.0 (maximum) is valid" \
  "$SCHEMAS/experience.schema.json" \
  "$CONFIDENCE_ONE"

CONFIDENCE_NEGATIVE="$TMPBB/experiences/bad-confidence-negative.json"
cat > "$CONFIDENCE_NEGATIVE" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Confidence below minimum",
  "timestamp": "2026-03-18T10:00:00Z",
  "confidence": -0.1
}
EOF

assert_invalid \
  "experience with confidence=-0.1 (below minimum) fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$CONFIDENCE_NEGATIVE"

CONFIDENCE_TOO_HIGH="$TMPBB/experiences/bad-confidence-high.json"
cat > "$CONFIDENCE_TOO_HIGH" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Confidence above maximum",
  "timestamp": "2026-03-18T10:00:00Z",
  "confidence": 1.1
}
EOF

assert_invalid \
  "experience with confidence=1.1 (above maximum) fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$CONFIDENCE_TOO_HIGH"

WAVE_COUNT_ZERO="$TMPBB/experiences/bad-wave-count-zero.json"
cat > "$WAVE_COUNT_ZERO" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Wave count below minimum (1)",
  "timestamp": "2026-03-18T10:00:00Z",
  "wave_count": 0
}
EOF

assert_invalid \
  "experience with wave_count=0 (below minimum of 1) fails validation" \
  "$SCHEMAS/experience.schema.json" \
  "$WAVE_COUNT_ZERO"

WAVE_COUNT_ONE="$TMPBB/experiences/wave-count-one.json"
cat > "$WAVE_COUNT_ONE" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Wave count at minimum boundary (1)",
  "timestamp": "2026-03-18T10:00:00Z",
  "wave_count": 1
}
EOF

assert_valid \
  "experience with wave_count=1 (minimum allowed) is valid" \
  "$SCHEMAS/experience.schema.json" \
  "$WAVE_COUNT_ONE"

AUDIT_NEGATIVE="$TMPBB/experiences/bad-audit-negative.json"
cat > "$AUDIT_NEGATIVE" <<'EOF'
{
  "task_type": "feature",
  "task_description": "Audit outcome with negative count",
  "timestamp": "2026-03-18T10:00:00Z",
  "audit_outcomes": {
    "pass": -1,
    "auto_fix": 0,
    "fail": 0
  }
}
EOF

assert_invalid \
  "experience with negative audit_outcomes.pass fails validation (minimum: 0)" \
  "$SCHEMAS/experience.schema.json" \
  "$AUDIT_NEGATIVE"

# ---------------------------------------------------------------------------
# Test group: Experience wrong types on fields
# ---------------------------------------------------------------------------

echo ""
echo "--- Wrong field types"

WRONG_TYPE_TASK_TYPE="$TMPBB/experiences/bad-task-type-number.json"
cat > "$WRONG_TYPE_TASK_TYPE" <<'EOF'
{
  "task_type": 42,
  "task_description": "task_type must be a string",
  "timestamp": "2026-03-18T10:00:00Z"
}
EOF

assert_invalid \
  "experience with task_type as integer fails validation (must be string)" \
  "$SCHEMAS/experience.schema.json" \
  "$WRONG_TYPE_TASK_TYPE"

WRONG_TYPE_WAVE="$TMPBB/experiences/bad-wave-float.json"
cat > "$WRONG_TYPE_WAVE" <<'EOF'
{
  "task_type": "feature",
  "task_description": "wave_count must be integer",
  "timestamp": "2026-03-18T10:00:00Z",
  "wave_count": 1.5
}
EOF

assert_invalid \
  "experience with wave_count as float fails validation (must be integer)" \
  "$SCHEMAS/experience.schema.json" \
  "$WRONG_TYPE_WAVE"

WRONG_TYPE_TAGS="$TMPBB/experiences/bad-tags-string.json"
cat > "$WRONG_TYPE_TAGS" <<'EOF'
{
  "task_type": "feature",
  "task_description": "tags must be an array",
  "timestamp": "2026-03-18T10:00:00Z",
  "tags": "not-an-array"
}
EOF

assert_invalid \
  "experience with tags as string fails validation (must be array)" \
  "$SCHEMAS/experience.schema.json" \
  "$WRONG_TYPE_TAGS"

WRONG_TYPE_LESSONS="$TMPBB/experiences/bad-lessons-object.json"
cat > "$WRONG_TYPE_LESSONS" <<'EOF'
{
  "task_type": "feature",
  "task_description": "lessons_learned must be an array",
  "timestamp": "2026-03-18T10:00:00Z",
  "lessons_learned": {"key": "not an array"}
}
EOF

assert_invalid \
  "experience with lessons_learned as object fails validation (must be array)" \
  "$SCHEMAS/experience.schema.json" \
  "$WRONG_TYPE_LESSONS"

# ---------------------------------------------------------------------------
# Test group: context.json — valid states
# ---------------------------------------------------------------------------

echo ""
echo "--- context.json valid states"

CONTEXT_ACTIVE="$TMPDIR_ROOT/context-active.json"
cat > "$CONTEXT_ACTIVE" <<'EOF'
{
  "current_task": {
    "id": "task-001",
    "description": "Build blackboard test suite",
    "type": "feature",
    "started_at": "2026-03-18T09:00:00Z",
    "status": "in_progress"
  },
  "recent_decisions": [
    {
      "summary": "Use ajv-cli for schema validation in tests",
      "timestamp": "2026-03-18T09:05:00Z",
      "skill": "ftm-executor"
    }
  ],
  "active_constraints": ["max 1000 lines per file", "no hardcoded paths"],
  "user_preferences": {
    "communication_style": "concise",
    "approval_gates": "on_destructive",
    "default_model_profile": "balanced"
  },
  "session_metadata": {
    "started_at": "2026-03-18T09:00:00Z",
    "last_updated": "2026-03-18T09:10:00Z",
    "conversation_id": "conv-abc123",
    "messages_count": 5,
    "skills_invoked": ["ftm-executor", "ftm-audit"]
  }
}
EOF

assert_valid \
  "context with active task (status=in_progress) passes schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_ACTIVE"

CONTEXT_COMPLETE="$TMPDIR_ROOT/context-complete.json"
cat > "$CONTEXT_COMPLETE" <<'EOF'
{
  "current_task": {
    "id": "task-002",
    "description": "Completed task example",
    "type": "bugfix",
    "started_at": "2026-03-18T08:00:00Z",
    "status": "complete"
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": "2026-03-18T08:00:00Z",
    "last_updated": "2026-03-18T08:30:00Z",
    "conversation_id": null,
    "messages_count": 0,
    "skills_invoked": []
  }
}
EOF

assert_valid \
  "context with completed task (status=complete) passes schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_COMPLETE"

CONTEXT_FAILED="$TMPDIR_ROOT/context-failed.json"
cat > "$CONTEXT_FAILED" <<'EOF'
{
  "current_task": {
    "id": "task-003",
    "description": "Failed task example",
    "type": "refactor",
    "started_at": "2026-03-18T07:00:00Z",
    "status": "failed"
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": "2026-03-18T07:00:00Z",
    "last_updated": null,
    "conversation_id": null,
    "messages_count": 0,
    "skills_invoked": []
  }
}
EOF

assert_valid \
  "context with failed task (status=failed) passes schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_FAILED"

CONTEXT_PENDING="$TMPDIR_ROOT/context-pending.json"
cat > "$CONTEXT_PENDING" <<'EOF'
{
  "current_task": {
    "id": "task-004",
    "description": "Pending task",
    "type": "feature",
    "started_at": null,
    "status": "pending"
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": null,
    "last_updated": null,
    "conversation_id": null,
    "messages_count": 0,
    "skills_invoked": []
  }
}
EOF

assert_valid \
  "context with pending task (status=pending) passes schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_PENDING"

# ---------------------------------------------------------------------------
# Test group: context.json — invalid status values
# ---------------------------------------------------------------------------

echo ""
echo "--- context.json invalid status values"

CONTEXT_BAD_STATUS="$TMPDIR_ROOT/context-bad-status.json"
cat > "$CONTEXT_BAD_STATUS" <<'EOF'
{
  "current_task": {
    "id": "task-bad",
    "description": "Status is not in the allowed enum",
    "type": "feature",
    "started_at": null,
    "status": "invalid_status"
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": null,
    "last_updated": null,
    "conversation_id": null,
    "messages_count": 0,
    "skills_invoked": []
  }
}
EOF

assert_invalid \
  "context with status='invalid_status' fails schema (not in enum)" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_BAD_STATUS"

CONTEXT_STATUS_NUMBER="$TMPDIR_ROOT/context-status-number.json"
cat > "$CONTEXT_STATUS_NUMBER" <<'EOF'
{
  "current_task": {
    "id": "task-bad",
    "description": "Status must be string or null, not a number",
    "type": "feature",
    "started_at": null,
    "status": 1
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": null,
    "last_updated": null,
    "conversation_id": null,
    "messages_count": 0,
    "skills_invoked": []
  }
}
EOF

assert_invalid \
  "context with status as integer fails schema (must be string or null)" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_STATUS_NUMBER"

# ---------------------------------------------------------------------------
# Test group: context.json — missing required top-level fields
# ---------------------------------------------------------------------------

echo ""
echo "--- context.json missing required fields"

CONTEXT_MISSING_TASK="$TMPDIR_ROOT/context-missing-task.json"
cat > "$CONTEXT_MISSING_TASK" <<'EOF'
{
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": null,
    "last_updated": null,
    "conversation_id": null,
    "messages_count": 0,
    "skills_invoked": []
  }
}
EOF

assert_invalid \
  "context missing current_task fails schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_MISSING_TASK"

CONTEXT_MISSING_META="$TMPDIR_ROOT/context-missing-meta.json"
cat > "$CONTEXT_MISSING_META" <<'EOF'
{
  "current_task": {
    "id": null,
    "description": null,
    "type": null,
    "started_at": null,
    "status": null
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  }
}
EOF

assert_invalid \
  "context missing session_metadata fails schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_MISSING_META"

# ---------------------------------------------------------------------------
# Test group: context.json — recent_decisions maxItems enforcement
# ---------------------------------------------------------------------------

echo ""
echo "--- context.json recent_decisions boundary"

# Build an array with exactly 10 decisions (allowed)
python3 - <<'PYEOF' > "$TMPDIR_ROOT/context-10-decisions.json"
import json

decisions = [
  {
    "summary": f"Decision {i}",
    "timestamp": "2026-03-18T10:00:00Z",
    "skill": "ftm-executor"
  }
  for i in range(10)
]

context = {
  "current_task": {
    "id": None,
    "description": None,
    "type": None,
    "started_at": None,
    "status": None
  },
  "recent_decisions": decisions,
  "active_constraints": [],
  "user_preferences": {
    "communication_style": None,
    "approval_gates": None,
    "default_model_profile": None
  },
  "session_metadata": {
    "started_at": None,
    "last_updated": None,
    "conversation_id": None,
    "messages_count": 0,
    "skills_invoked": []
  }
}
print(json.dumps(context, indent=2))
PYEOF

assert_valid \
  "context with exactly 10 recent_decisions (maxItems) passes schema" \
  "$SCHEMAS/context.schema.json" \
  "$TMPDIR_ROOT/context-10-decisions.json"

# Build an array with 11 decisions (exceeds maxItems: 10)
python3 - <<'PYEOF' > "$TMPDIR_ROOT/context-11-decisions.json"
import json

decisions = [
  {
    "summary": f"Decision {i}",
    "timestamp": "2026-03-18T10:00:00Z",
    "skill": "ftm-executor"
  }
  for i in range(11)
]

context = {
  "current_task": {
    "id": None,
    "description": None,
    "type": None,
    "started_at": None,
    "status": None
  },
  "recent_decisions": decisions,
  "active_constraints": [],
  "user_preferences": {
    "communication_style": None,
    "approval_gates": None,
    "default_model_profile": None
  },
  "session_metadata": {
    "started_at": None,
    "last_updated": None,
    "conversation_id": None,
    "messages_count": 0,
    "skills_invoked": []
  }
}
print(json.dumps(context, indent=2))
PYEOF

assert_invalid \
  "context with 11 recent_decisions (exceeds maxItems: 10) fails schema" \
  "$SCHEMAS/context.schema.json" \
  "$TMPDIR_ROOT/context-11-decisions.json"

CONTEXT_NEG_MESSAGES="$TMPDIR_ROOT/context-negative-messages.json"
cat > "$CONTEXT_NEG_MESSAGES" <<'EOF'
{
  "current_task": {
    "id": null,
    "description": null,
    "type": null,
    "started_at": null,
    "status": null
  },
  "recent_decisions": [],
  "active_constraints": [],
  "user_preferences": {
    "communication_style": null,
    "approval_gates": null,
    "default_model_profile": null
  },
  "session_metadata": {
    "started_at": null,
    "last_updated": null,
    "conversation_id": null,
    "messages_count": -1,
    "skills_invoked": []
  }
}
EOF

assert_invalid \
  "context with messages_count=-1 (below minimum 0) fails schema" \
  "$SCHEMAS/context.schema.json" \
  "$CONTEXT_NEG_MESSAGES"

# ---------------------------------------------------------------------------
# Test group: patterns.json — valid structures
# ---------------------------------------------------------------------------

echo ""
echo "--- patterns.json valid and invalid"

assert_valid \
  "patterns template (empty arrays) passes schema" \
  "$SCHEMAS/patterns.schema.json" \
  "$TMPBB/patterns.json"

PATTERNS_POPULATED="$TMPDIR_ROOT/patterns-populated.json"
cat > "$PATTERNS_POPULATED" <<'EOF'
{
  "codebase_insights": [
    {"type": "convention", "note": "All skill dirs use kebab-case naming"}
  ],
  "execution_patterns": [
    {"wave_shape": "2-wave", "frequency": "high", "context": "simple feature tasks"}
  ],
  "user_behavior": [
    {"preference": "concise_output", "confidence": 0.9}
  ],
  "recurring_issues": [
    {"issue": "missing frontmatter in SKILL.md", "count": 3}
  ]
}
EOF

assert_valid \
  "patterns with populated arrays passes schema" \
  "$SCHEMAS/patterns.schema.json" \
  "$PATTERNS_POPULATED"

PATTERNS_MISSING_FIELD="$TMPDIR_ROOT/patterns-missing-field.json"
cat > "$PATTERNS_MISSING_FIELD" <<'EOF'
{
  "codebase_insights": [],
  "execution_patterns": [],
  "user_behavior": []
}
EOF

assert_invalid \
  "patterns missing recurring_issues field fails schema" \
  "$SCHEMAS/patterns.schema.json" \
  "$PATTERNS_MISSING_FIELD"

PATTERNS_EXTRA="$TMPDIR_ROOT/patterns-extra.json"
cat > "$PATTERNS_EXTRA" <<'EOF'
{
  "codebase_insights": [],
  "execution_patterns": [],
  "user_behavior": [],
  "recurring_issues": [],
  "invented_field": "not allowed"
}
EOF

assert_invalid \
  "patterns with unknown extra field fails schema (additionalProperties: false)" \
  "$SCHEMAS/patterns.schema.json" \
  "$PATTERNS_EXTRA"

PATTERNS_WRONG_TYPE="$TMPDIR_ROOT/patterns-wrong-type.json"
cat > "$PATTERNS_WRONG_TYPE" <<'EOF'
{
  "codebase_insights": "should be an array",
  "execution_patterns": [],
  "user_behavior": [],
  "recurring_issues": []
}
EOF

assert_invalid \
  "patterns with codebase_insights as string fails schema (must be array)" \
  "$SCHEMAS/patterns.schema.json" \
  "$PATTERNS_WRONG_TYPE"

# ---------------------------------------------------------------------------
# Test group: experience-index.schema.json — edge cases
# ---------------------------------------------------------------------------

echo ""
echo "--- experience index edge cases"

INDEX_EMPTY="$TMPDIR_ROOT/index-empty.json"
cat > "$INDEX_EMPTY" <<'EOF'
{
  "entries": [],
  "metadata": {
    "total_count": 0,
    "last_updated": null,
    "max_entries": 200,
    "pruning_strategy": "remove_oldest_low_confidence"
  }
}
EOF

assert_valid \
  "experience index with empty entries passes schema" \
  "$SCHEMAS/experience-index.schema.json" \
  "$INDEX_EMPTY"

INDEX_MISSING_ENTRIES="$TMPDIR_ROOT/index-missing-entries.json"
cat > "$INDEX_MISSING_ENTRIES" <<'EOF'
{
  "metadata": {
    "total_count": 0,
    "last_updated": null,
    "max_entries": 200,
    "pruning_strategy": "remove_oldest_low_confidence"
  }
}
EOF

assert_invalid \
  "experience index missing entries field fails schema" \
  "$SCHEMAS/experience-index.schema.json" \
  "$INDEX_MISSING_ENTRIES"

INDEX_MISSING_METADATA="$TMPDIR_ROOT/index-missing-metadata.json"
cat > "$INDEX_MISSING_METADATA" <<'EOF'
{
  "entries": []
}
EOF

assert_invalid \
  "experience index missing metadata fails schema" \
  "$SCHEMAS/experience-index.schema.json" \
  "$INDEX_MISSING_METADATA"

INDEX_ENTRY_MISSING_ID="$TMPDIR_ROOT/index-entry-missing-id.json"
cat > "$INDEX_ENTRY_MISSING_ID" <<'EOF'
{
  "entries": [
    {
      "file": "2026-03-18_test.json",
      "task_type": "feature",
      "tags": [],
      "timestamp": "2026-03-18T10:00:00Z",
      "confidence": 0.8
    }
  ],
  "metadata": {
    "total_count": 1,
    "last_updated": null,
    "max_entries": 200,
    "pruning_strategy": "remove_oldest_low_confidence"
  }
}
EOF

assert_invalid \
  "experience index entry missing id field fails schema" \
  "$SCHEMAS/experience-index.schema.json" \
  "$INDEX_ENTRY_MISSING_ID"

INDEX_ENTRY_BAD_CONFIDENCE="$TMPDIR_ROOT/index-bad-confidence.json"
cat > "$INDEX_ENTRY_BAD_CONFIDENCE" <<'EOF'
{
  "entries": [
    {
      "id": "2026-03-18_test",
      "file": "2026-03-18_test.json",
      "task_type": "feature",
      "tags": [],
      "timestamp": "2026-03-18T10:00:00Z",
      "confidence": 1.5
    }
  ],
  "metadata": {
    "total_count": 1,
    "last_updated": null,
    "max_entries": 200,
    "pruning_strategy": "remove_oldest_low_confidence"
  }
}
EOF

assert_invalid \
  "experience index entry with confidence=1.5 (above maximum) fails schema" \
  "$SCHEMAS/experience-index.schema.json" \
  "$INDEX_ENTRY_BAD_CONFIDENCE"

INDEX_NEG_TOTAL="$TMPDIR_ROOT/index-neg-total.json"
cat > "$INDEX_NEG_TOTAL" <<'EOF'
{
  "entries": [],
  "metadata": {
    "total_count": -1,
    "last_updated": null,
    "max_entries": 200,
    "pruning_strategy": "remove_oldest_low_confidence"
  }
}
EOF

assert_invalid \
  "experience index with metadata.total_count=-1 fails schema (minimum: 0)" \
  "$SCHEMAS/experience-index.schema.json" \
  "$INDEX_NEG_TOTAL"

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
