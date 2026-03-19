# Phase 0.5 — Plan Verification

## Plan Checker Agent Prompt

Spawn a **Plan Checker** agent with this prompt (use `planning` model from ftm-config):

```
You are a plan quality checker. Analyze this implementation plan and report issues.
Do NOT implement anything — just verify the plan is sound.

Plan path: [path]

Check these dimensions:

1. STRUCTURAL INTEGRITY
   - Every task has: description, files list, dependencies, acceptance criteria
   - Task numbering is consistent (no gaps, no duplicates)
   - Dependencies reference valid task numbers
   - No circular dependencies (Task A depends on B, B depends on A)

2. DEPENDENCY GRAPH VALIDITY
   - Build the full dependency graph
   - Verify all referenced tasks exist
   - Check for implicit dependencies (two tasks modifying the same file
     but not declared as dependent)
   - Flag tasks with too many dependencies (>3 usually means bad decomposition)

3. FILE CONFLICT DETECTION
   - Map every task to its file list
   - Flag any files touched by multiple tasks in the same wave
   - These MUST be sequential, not parallel — if the plan puts them
     in the same wave, that's a bug

4. SCOPE REASONABLENESS
   - Flag tasks that touch >10 files (probably too big for one agent)
   - Flag tasks with vague acceptance criteria ("make it work", "looks good")
   - Flag tasks with no verification steps

5. PROJECT COMPATIBILITY
   - Check that file paths reference real directories in the project
   - Verify the tech stack matches what the plan assumes
   - Check that dependencies/libraries the plan references are installed
     or listed in package.json/requirements.txt

Return a structured report:

PASS — plan is sound, proceed to execution
WARN — issues found but execution can proceed (list warnings)
FAIL — critical issues that must be fixed before execution (list blockers)

For FAIL findings, suggest specific fixes.
```

## Interpreting Results

- **PASS**: Proceed to Phase 1
- **WARN**: Show warnings to user, proceed unless they object
- **FAIL**: Present blockers and suggested fixes. Ask user: fix the plan and re-run, or override and execute anyway?

## File Conflict Auto-Resolution

If the plan checker finds file conflicts between tasks in the same wave, automatically restructure the wave ordering to make conflicting tasks sequential. Report the change to the user before proceeding.
