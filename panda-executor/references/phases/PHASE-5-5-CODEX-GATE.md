# Phase 5.5 — Codex Gate (Wave Boundary Validation)

## When to Invoke

- After EVERY wave completes and is merged — this is the heavy validation gate
- For single-task plans, invoke on task completion instead of wave completion

## Inputs for panda-codex-gate

- `file_list`: All files changed across the wave (`git diff --name-only` against pre-wave state)
- `acceptance_criteria`: Combined acceptance criteria from all tasks in the wave
- `wave_context`: Summary of what the wave accomplished (task titles + brief descriptions)
- `project_root`: The project working directory
- `mode`: `"wave"` for multi-task waves, `"single-task"` for single-task runs

## Result Interpretation

**PASS (no issues found):**
- Log in PROGRESS.md: "Codex gate PASSED — 0 issues"
- Proceed to next wave (or Phase 6 if this was the last wave)

**PASS_WITH_FIXES (issues found and auto-fixed by Codex):**
- Codex committed fixes directly — review the fix commits
- Diff each fix commit against INTENT.md entries for the affected functions
- No INTENT.md conflict → accept the fixes, log in PROGRESS.md and DEBUG.md, proceed
- INTENT.md conflict detected → see INTENT.md Conflict Resolution below

**FAIL (issues Codex could not fix):**
- Attempt to fix them yourself (you have full context from the wave)
- If fixed, commit and re-run the Codex gate
- If unresolved after 2 attempts, report to user:
  ```
  Codex gate FAILED for Wave [N] — manual intervention needed:
  - [remaining issue 1]
  - [remaining issue 2]
  Codex attempted [N] fixes but these remain unresolved.
  ```
  Wait for user input before continuing.

## INTENT.md Conflict Resolution

A conflict exists when Codex's fix changes a function's behavior, reverts a deliberate choice, or changes a signature that INTENT.md documents.

**Step 1 — Detect:** Compare the Codex fix diff against the INTENT.md entry for the affected function.

**Step 2 — Invoke panda-council** with this structured payload:
```
CONFLICT TYPE: Codex fix contradicts INTENT.md

ORIGINAL INTENT (from INTENT.md):
[paste the full INTENT.md entry for the affected function]

CODEX'S CHANGE:
[paste the diff of what Codex changed]

CODEX'S REASONING:
[paste Codex's explanation from the gate results]

THE CODE IN QUESTION:
[file path and relevant code section]

DEBUG.md HISTORY:
[paste relevant entries from DEBUG.md so the council doesn't suggest already-failed approaches]

QUESTION FOR THE COUNCIL:
Should we (A) update INTENT.md to match Codex's fix, or (B) revert Codex's fix and keep the original intent?
```

**Step 3 — Execute the verdict:**
- Verdict A (update intent): Update the INTENT.md entry. Commit: "Update intent: [function] — council verdict [round N]"
- Verdict B (revert fix): Revert Codex's fix commit. Commit: "Revert codex fix: [function] — council verdict preserves original intent"
- Log full decision + reasoning in DEBUG.md
- Continue to next wave after all conflicts are resolved
