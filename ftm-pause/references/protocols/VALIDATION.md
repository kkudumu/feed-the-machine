# State Validation Logic

This document defines all validation checks performed before and after writing state to disk.

---

## Pre-Write Validation

Before writing `~/.claude/ftm-state/STATE.md`, verify the following:

### Skill Detection Confirmed

- A ftm skill was positively identified from the conversation context
- If no skill detected: halt and tell the user "No active ftm session detected" — do not write a blank or partial state file

### Required Frontmatter Fields Present

The YAML frontmatter block must contain:
- `skill` — one of: ftm-brainstorm, ftm-executor, ftm-debug, ftm-council, ftm-audit
- `phase` — the current phase number or stage name for that skill
- `phase_detail` — a human-readable one-liner about exactly where the session stopped
- `timestamp` — ISO 8601 format (YYYY-MM-DDThh:mm:ss)
- `project_dir` — absolute path to the working directory

Git fields (`git_branch`, `git_commit`) are required only if a git repo is present. If no repo, omit them rather than leaving them blank.

### State File Contains Actual Content

- "Next Step" section must be specific and actionable — not a placeholder like "[describe next step]"
- Decisions Made section must reflect real decisions from the conversation, not template text
- If the session was very early (e.g., Phase 0 only), the "Captured" summary should say so explicitly

### Artifacts Verified

For each artifact path listed in the state file:
- The file must exist on disk at the recorded path
- If an artifact path is stale (file was deleted or moved), note it with `[NOT FOUND]` rather than silently omitting it

---

## Post-Write Validation

After writing the state file, verify:

### File Was Written Successfully

- The state file exists at `~/.claude/ftm-state/STATE.md`
- File size is non-zero
- The frontmatter block is parseable (starts with `---`, contains required keys)

### State Is Resumable

The written state must pass the "cold start test": a fresh conversation with no prior context should be able to reconstruct the session from the state file alone, without needing to ask the user "where were we?" Concretely:
- The skill and phase are unambiguous
- The Next Step section tells ftm-resume exactly what action to take first
- Enough prior context is captured that the first response after resume won't require re-explaining the project

---

## Edge Case Handling

### Multiple Skills Active

If two ftm skills were invoked in the same conversation (e.g., brainstorm followed by executor), save the most recently active one to `STATE.md`. Save the other to `STATE-[skill].md` in the same directory. Both files go through the same validation.

### Overwriting Existing State

Overwrite `STATE.md` without prompting. The previous state was either already resumed and consumed, or abandoned. Validation still applies to the new file.

### No Git Repo

Skip `git_branch` and `git_commit` fields entirely. Record only `project_dir`. Do not write empty string values for these fields — omit them from the frontmatter block.

### Very Early Session (Phase 0 or Step 1 Only)

Capture whatever exists. Even a Phase 0 repo scan is worth saving. The "Next Step" section should note that the user needs to answer the first intake question. This passes validation — sparse state is valid state.

### Large State Files

Do not truncate. Some sessions accumulate substantial state — 8+ brainstorm turns with full research results, or an executor session with 20+ tasks. The state file can be large. Completeness is required for reliable restoration.
