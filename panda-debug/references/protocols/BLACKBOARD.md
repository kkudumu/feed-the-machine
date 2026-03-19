# Shared Blackboard Protocol

The blackboard is a persistent shared state that allows skills to coordinate across sessions and learn from past debugging sessions.

---

## Blackboard Read (on session start)

Before starting, load context from the blackboard:

1. Read `~/.claude/panda-state/blackboard/context.json` — check current_task, recent_decisions, active_constraints
2. Read `~/.claude/panda-state/blackboard/experiences/index.json` — filter entries by task_type="bug" and tags matching the current error domain
3. Load top 3-5 matching experience files for known fixes and failed approaches
4. Read `~/.claude/panda-state/blackboard/patterns.json` — check recurring_issues for matching symptoms and codebase_insights for relevant file patterns

If index.json is empty or no matches found, proceed normally without experience-informed shortcuts.

---

## Blackboard Write (on session complete)

After the debug session concludes, update the blackboard:

### 1. Update context.json

Path: `~/.claude/panda-state/blackboard/context.json`

- Set `current_task.status` to `"complete"`
- Append a decision summary to `recent_decisions` (keep array capped at 10 entries)
- Update `session_metadata.skills_invoked` to include `"panda-debug"`
- Update `session_metadata.last_updated` to current timestamp

### 2. Write Experience File

Path: `~/.claude/panda-state/blackboard/experiences/YYYY-MM-DD_task-slug.json`

Capture the following in the experience file:

```json
{
  "date": "YYYY-MM-DD",
  "task_slug": "short-description-of-bug",
  "task_type": "bug",
  "symptom": "One-sentence description of what the user reported",
  "root_cause": "One-sentence description of what was actually wrong",
  "hypotheses_tested": [
    { "hypothesis": "...", "outcome": "confirmed | rejected" }
  ],
  "fix_approach": "Brief description of the fix strategy used",
  "fix_files": ["path/to/file1.js", "path/to/file2.ts"],
  "verification_method": "test | visual | runtime | combined",
  "tags": ["race-condition", "react", "async", "etc."],
  "check_first_next_time": "The thing that was most predictive of the root cause"
}
```

### 3. Update experiences/index.json

Path: `~/.claude/panda-state/blackboard/experiences/index.json`

Append a new entry to the index:

```json
{
  "file": "YYYY-MM-DD_task-slug.json",
  "task_type": "bug",
  "tags": ["same-tags-as-experience-file"],
  "summary": "One-line description for quick matching"
}
```

### 4. Emit Event

Emit `task_completed` event to signal the session is done.

---

## Experience File Matching Logic

When loading experiences at session start, match by:

1. **task_type** must equal `"bug"`
2. **tags** overlap with current error domain (e.g., framework name, error category, file path patterns)
3. **symptom** similarity (loose match on keywords from the current problem statement)

Prioritize experiences where `check_first_next_time` is populated — these are the highest-value shortcuts.
