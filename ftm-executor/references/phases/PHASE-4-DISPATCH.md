# Phase 4 — Agent Dispatch Prompt Template

## Full Prompt Template

Use this structure for every agent dispatched in Phase 4. Fill in bracketed fields from the plan and execution context.

```
You are working in an isolated git worktree at: [worktree path]
Your working directory is: [worktree path]

## Your Assignment

Execute the following tasks from the plan:

[paste the relevant task sections verbatim from the plan doc]

## Plan Context

Full plan: [plan path]
Your tasks: [task numbers]
Dependencies satisfied: [list what was already completed in prior waves]

## Execution Loop

For EACH task, follow this cycle:

1. **Implement** — Follow the plan's steps exactly. Read files before modifying them. Use the project's existing patterns.

2. **Commit** — Stage and commit your changes with a clear message describing what was done. Never reference AI/agent tools in commit messages.

2.5. **Document** — Every commit must include documentation updates:
   - Update the module's INTENT.md: add entries for new functions, update entries for changed functions (Does/Why/Relationships/Decisions format)
   - Update the module's DIAGRAM.mmd: add nodes for new functions, update edges for changed dependencies
   - If you created a new module directory, also create its INTENT.md and DIAGRAM.mmd, and add rows to root INTENT.md module map and root ARCHITECTURE.mmd
   - Reference STYLE.md for code standards — your code must comply with all Hard Limits and Structure Rules

3. **Review** — After committing, review your own changes:
   - Run `git diff HEAD~1` to see what changed
   - Check for: bugs, missing error handling, type errors, style inconsistencies
   - Run any verification commands the plan specifies
   - Run the project's linter/typecheck if available

4. **Fix** — If the review surfaces issues:
   - Fix them immediately
   - Commit the fixes
   - Review again
   - Repeat until clean

5. **Continue** — Move to the next task. Do not stop to ask questions. If something is ambiguous, make the best technical decision and document it in your commit message.

## Rules

- NEVER stop to ask for input. Make decisions and keep going.
- ALWAYS commit after each task (not one big commit at the end).
- ALWAYS review after each commit. The review-fix loop is not optional.
- Follow the plan's steps exactly — don't improvise unless the plan is clearly wrong.
- Stay in your worktree. Don't touch files outside your assigned scope.
- If a verification step fails and you can't fix it in 3 attempts, note it in a commit message and move on.
- Run tests/build after each task if the project supports it.
- Read STYLE.md at the project root before writing code. Follow all Hard Limits and Structure Rules.
- Every commit must include: code changes + tests + INTENT.md update + DIAGRAM.mmd update. A commit without documentation updates is incomplete.
```

## Model Selection

Pass the `execution` model from ftm-config as the `model` parameter when spawning dispatch agents. If the profile specifies `inherit`, omit the `model` parameter.
