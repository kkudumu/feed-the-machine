# Panda Event Registry

This document defines the full event vocabulary for the panda skill system. The mind reads this during its Decide phase to determine which skills to trigger after any action completes.

---

## How to Read This Document

Each event entry uses the following format:

```markdown
### event_name
- **Description**: What this event means
- **Emitted by**: [list of skills]
- **Listened to by**: [list of skills]
- **Fast-path**: yes/no (fast-path events bypass mind mediation and always trigger their listeners)
- **Payload**: {key fields the event carries}
```

**Fast-path events** are always triggered immediately — the mind does not evaluate whether to route them. Use fast-path for events where the downstream response is unconditional and latency matters (documentation sync, micro-reflections).

**Mediated events** pass through the mind's Decide phase. The mind evaluates context and decides whether to trigger listeners, which listener to prefer, and whether to combine multiple events before acting.

---

## How to Add an Event Declaration to a Skill

When adding event declarations to a skill's SKILL.md, insert an `## Events` section AFTER the YAML frontmatter block and BEFORE the first major heading of existing content. Do NOT modify any other content.

Use this exact format:

```markdown
## Events

### Emits
- `event_name` — when [the condition that causes this skill to emit the event]

### Listens To
- `event_name` — [what this skill does in response when this event fires]
```

Guidelines for writing clear declarations:
- Emit conditions should describe the specific moment the event fires, not the entire skill workflow. Example: "when a git commit is made" not "during execution".
- Listen-to descriptions should describe the triggered action, not the full response workflow. Example: "auto-investigate the failure" not "launch Phase 1 agents".
- Use backtick-quoted event names consistently.
- One bullet per event. If a skill emits the same event under multiple conditions, combine them into one bullet with "or" — e.g., "when the test suite passes, or when a post-fix verification succeeds".

---

## Full Event Vocabulary

### task_received
- **Description**: A new task has entered the system and is acknowledged by the executor
- **Emitted by**: panda-executor
- **Listened to by**: panda-mind (log task arrival, initialize tracking context), panda-brainstorm (begin ideation work when mind routes an incoming task for exploration)
- **Fast-path**: no
- **Payload**: `{ task_description, plan_path, wave_number, task_number }`

---

### plan_generated
- **Description**: A plan document was created and is ready for review or execution
- **Emitted by**: panda-executor, panda-brainstorm
- **Listened to by**: panda-mind (surface plan to user, optionally trigger panda-audit pre-flight)
- **Fast-path**: no
- **Payload**: `{ plan_path, plan_title, task_count, wave_count }`

---

### plan_approved
- **Description**: The user has approved a plan for execution
- **Emitted by**: panda-executor (after user confirmation)
- **Listened to by**: panda-executor (begin Phase 3 worktree setup and agent dispatch)
- **Fast-path**: no
- **Payload**: `{ plan_path, plan_title, approved_by, timestamp }`

---

### code_changed
- **Description**: One or more files were modified — pre-commit state, changes not yet persisted to git history
- **Emitted by**: panda-executor
- **Listened to by**: panda-mind (record in blackboard, may trigger pre-commit checks)
- **Fast-path**: no
- **Payload**: `{ files_changed: [path], task_number, agent_name, worktree_path }`

---

### code_committed
- **Description**: A git commit was successfully made — changes are persisted to the repository
- **Emitted by**: panda-executor
- **Listened to by**: panda-intent (update INTENT.md entries for changed functions), panda-diagram (update DIAGRAM.mmd nodes and edges for changed modules), panda-codex-gate (run adversarial validation at wave boundaries after commits land)
- **Fast-path**: yes — documentation must always stay in sync with commits, no mind mediation needed
- **Payload**: `{ commit_hash, commit_message, files_changed: [path], worktree_path, task_number }`

---

### test_passed
- **Description**: The test suite (or a targeted subset) ran and all tests passed
- **Emitted by**: panda-executor, panda-debug
- **Listened to by**: panda-mind (update task status, potentially unblock next wave)
- **Fast-path**: no
- **Payload**: `{ test_runner, test_count, duration_ms, scope: "full_suite" | "task_scope", task_number }`

---

### test_failed
- **Description**: The test suite ran and one or more tests failed
- **Emitted by**: panda-executor, panda-debug
- **Listened to by**: panda-debug (auto-investigate the failure), panda-mind (block wave advancement, update task status)
- **Fast-path**: no
- **Payload**: `{ test_runner, failed_tests: [{ name, file, error }], total_count, failed_count, task_number }`

---

### bug_fixed
- **Description**: A specific bug was identified, a fix was applied, and the Reviewer agent approved the fix
- **Emitted by**: panda-debug
- **Listened to by**: panda-retro (record the fix as a success experience), panda-mind (update task status, unblock dependents)
- **Fast-path**: no
- **Payload**: `{ bug_description, root_cause, files_changed: [path], fix_commits: [hash], reviewer_verdict }`

---

### audit_complete
- **Description**: panda-audit finished its full analysis (all three layers) for a given scope
- **Emitted by**: panda-audit
- **Listened to by**: panda-executor (interpret results: mark task complete, queue auto-fix, or hold for manual review), panda-mind (update audit record on blackboard)
- **Fast-path**: no
- **Payload**: `{ scope: [path], findings_count, auto_fixed_count, manual_required_count, final_status: "PASS" | "FAIL", changelog_path }`

---

### issue_found
- **Description**: A problem was discovered — by panda-audit static analysis, by adversarial audit, or by panda-debug investigation
- **Emitted by**: panda-audit, panda-debug, panda-codex-gate
- **Listened to by**: panda-mind (log the issue, decide whether to surface to user or auto-route to fix)
- **Fast-path**: no
- **Payload**: `{ issue_type, file_path, line_hint, description, severity: "error" | "warning", source: "knip" | "adversarial" | "debug", auto_fixable: boolean }`

---

### documentation_updated
- **Description**: INTENT.md or a DIAGRAM.mmd file was updated to reflect new or changed code
- **Emitted by**: panda-intent, panda-diagram
- **Listened to by**: panda-mind (record documentation sync on blackboard, reset the "docs behind" flag for the affected module)
- **Fast-path**: no
- **Payload**: `{ file_path, module_name, update_type: "intent" | "diagram", changed_entries: [string] }`

---

### review_complete
- **Description**: A code review or audit review finished and produced a verdict
- **Emitted by**: panda-audit (after adversarial layer), panda-debug (after Reviewer agent), panda-council (after majority verdict or 5-round synthesis), panda-codex-gate (after Codex analysis completes)
- **Listened to by**: panda-audit (validate review findings match static analysis), panda-mind (update review status on blackboard)
- **Fast-path**: no
- **Payload**: `{ verdict: "APPROVED" | "APPROVED_WITH_CHANGES" | "NEEDS_REWORK", reviewer, findings: [string], task_number }`

---

### task_completed
- **Description**: A task finished — including passing all verification gates (tests, audit, Codex gate)
- **Emitted by**: panda-executor, panda-debug, panda-audit, panda-retro, panda-brainstorm, panda-council, panda-codex-gate, panda-intent, panda-diagram, panda-browse, panda-pause, panda-resume, panda-upgrade, panda-config
- **Listened to by**: panda-retro (micro-reflection trigger — record the task outcome as an experience), panda-mind (advance wave state, check if all tasks in wave are done)
- **Fast-path**: yes — micro-reflection runs on every task completion unconditionally; no mind mediation needed
- **Payload**: `{ task_number, task_title, plan_path, wave_number, duration_ms, audit_result, agent_name }`

---

### error_encountered
- **Description**: An unexpected error occurred during execution that was not part of a normal test failure
- **Emitted by**: panda-executor, panda-debug
- **Listened to by**: panda-debug (diagnose the error), panda-retro (record as a failure experience for pattern learning), panda-mind (halt or reroute depending on severity)
- **Fast-path**: no
- **Payload**: `{ error_message, stack_trace, phase, task_number, skill: "panda-executor" | "panda-debug", recoverable: boolean }`

---

### session_paused
- **Description**: The session state was serialized and saved — the user is ending the session but wants to resume later
- **Emitted by**: panda-pause (dedicated pause skill)
- **Listened to by**: panda-mind (write final blackboard snapshot, record open tasks and current wave state)
- **Fast-path**: no
- **Payload**: `{ session_id, plan_path, current_wave, open_tasks: [number], blackboard_snapshot_path, timestamp }`

---

### session_resumed
- **Description**: A previously paused session state was restored and execution is continuing
- **Emitted by**: panda-resume (dedicated resume skill)
- **Listened to by**: panda-executor (restore wave state and re-dispatch open tasks), panda-mind (reload blackboard snapshot)
- **Fast-path**: no
- **Payload**: `{ session_id, plan_path, restored_wave, open_tasks: [number], blackboard_snapshot_path, timestamp }`

---

### experience_recorded
- **Description**: A new experience entry (task outcome, fix attempt, blocker) was written to the blackboard's experience log
- **Emitted by**: panda-retro
- **Listened to by**: panda-mind (evaluate whether the experience reveals a new pattern to promote)
- **Fast-path**: no
- **Payload**: `{ experience_type: "success" | "failure" | "fix" | "blocker", description, task_number, plan_slug, timestamp }`

---

### pattern_discovered
- **Description**: A recurring pattern was identified from accumulated experiences and promoted to the patterns.json library
- **Emitted by**: panda-retro
- **Listened to by**: panda-mind (index the new pattern so it can inform future Decide-phase routing), panda-executor (optionally: adjust agent prompts if pattern is execution-relevant)
- **Fast-path**: no
- **Payload**: `{ pattern_name, pattern_description, first_seen_retro, occurrence_count, suggested_action, patterns_file_path }`

---

## Fast-Path Summary

| Event | Always triggers |
|---|---|
| `code_committed` | panda-intent (INTENT.md sync), panda-diagram (DIAGRAM.mmd sync) |
| `task_completed` | panda-retro (micro-reflection / experience recording) |

All other events are mediated by the mind's Decide phase.

---

## Event Routing Reference

Use this table to quickly look up which skills are involved when an event fires:

| Event | Emitters | Listeners |
|---|---|---|
| task_received | executor | mind, brainstorm |
| plan_generated | executor, brainstorm | mind |
| plan_approved | executor | executor |
| code_changed | executor | mind |
| code_committed | executor | intent, diagram, codex-gate |
| test_passed | executor, debug | mind |
| test_failed | executor, debug | debug, mind |
| bug_fixed | debug | retro, mind |
| audit_complete | audit | executor, mind |
| issue_found | audit, debug, codex-gate | mind |
| documentation_updated | intent, diagram | mind |
| review_complete | audit, debug, council, codex-gate | audit, mind |
| task_completed | executor, debug, audit, retro, brainstorm, council, codex-gate, intent, diagram, browse, pause, resume, upgrade, config | retro, mind |
| error_encountered | executor, debug | debug, retro, mind |
| session_paused | pause | mind |
| session_resumed | resume | executor, mind |
| experience_recorded | retro | mind |
| pattern_discovered | retro | mind, executor |
