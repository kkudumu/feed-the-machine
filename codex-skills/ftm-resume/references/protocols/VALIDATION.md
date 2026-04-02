# Resume Validation Protocols

Before attempting to restore a session, run these environment checks. Each check either passes, warns, or blocks resumption.

---

## Check 1: State File Integrity

Read `~/.codex/ftm-state/STATE.md`.

**File missing:**
```
No saved ftm session found at ~/.codex/ftm-state/STATE.md

To save a session mid-workflow, use $ftm-pause during any active ftm skill.
```
Stop here.

**File exists but unparseable (missing frontmatter, malformed YAML):**
```
Found state file but it appears corrupted — missing required frontmatter fields.
Expected fields: skill, phase, timestamp, project_dir

Would you like me to try to extract what I can from the file, or should we start fresh?
```

**Required frontmatter fields:**

| Field | Required | Purpose |
|-------|----------|---------|
| `skill` | Yes | Which ftm skill to resume |
| `phase` | Yes | Which phase the skill was in |
| `phase_detail` | No | Human-readable position within phase |
| `timestamp` | Yes | When the session was saved |
| `project_dir` | Yes | Project directory the session was working in |
| `git_branch` | No | Git branch at time of save |
| `git_commit` | No | HEAD commit at time of save |

**Incomplete state (missing critical sections — no "Next Step," no "Context Snapshot"):**

Warn: "The state file is incomplete — it may have been saved during an error. I can try to resume with what's available, but some context may be missing. Alternatively, we can start fresh."

---

## Check 2: Version Compatibility

If the state file has a `ftm_version` field, compare it to the installed skill version.

- **Same version**: Pass.
- **Minor version difference**: Warn. "This state was saved with an older version of ftm. The workflow may behave slightly differently, but resumption should work."
- **Major version difference**: Block with explanation. "This state was saved with ftm v{N}, but the installed version is v{M}. Major version changes may have altered skill structure. Resuming could produce unexpected behavior. Recommend starting fresh."
- **No version field**: Proceed without warning (pre-versioning state files are assumed compatible).

---

## Check 3: Project Directory

```bash
test -d "{project_dir}" && echo "EXISTS" || echo "MISSING"
```

- **EXISTS**: Pass. Continue.
- **MISSING**: Block. "The project directory `{project_dir}` no longer exists. Cannot resume — the codebase isn't available. Did the project move?"

---

## Check 4: Git State (if git fields present)

```bash
cd "{project_dir}" && git branch --show-current && git rev-parse --short HEAD
```

Compare current branch and commit against saved values.

- **Same branch, same commit**: Pass — nothing changed.
- **Same branch, different commit**: Warn. "The codebase has been modified since the session was saved. {N} new commits on `{branch}` since `{saved_commit}`." Show the commit log between saved and current. Ask if the user wants to continue anyway or review changes first.
- **Different branch**: Warn. "You're now on branch `{current}` but the session was saved on `{saved_branch}`. Would you like to switch back to `{saved_branch}`, or continue on `{current}`?"

---

## Check 5: Worktree Branches (executor and debug only)

If the state file references worktree branches:

```bash
cd "{project_dir}" && git worktree list
git branch --list "plan-exec/*" "debug/*"
```

- **All referenced branches exist**: Pass.
- **Some missing**: Warn. List which branches are missing. "These worktree branches from the saved session no longer exist: {list}. Tasks associated with these branches may need to be re-executed."
- **All missing**: Warn more strongly. "All worktree branches from the saved session have been cleaned up. Completed task work may have been merged already. In-progress tasks will need to restart."

---

## Check 6: Plan File (executor only)

If the state references a plan file:

```bash
test -f "{plan_path}" && echo "EXISTS" || echo "MISSING"
```

- **EXISTS**: Pass.
- **MISSING**: Block. "The plan file `{plan_path}` no longer exists. Cannot resume executor without a plan. Do you have the plan elsewhere?"

---

## Check 7: Artifact Files (debug only)

Check for any referenced artifact files (RESEARCH-FINDINGS.md, HYPOTHESES.md, REPRODUCTION.md, etc.):

```bash
for f in {artifact_paths}; do test -f "$f" && echo "$f: EXISTS" || echo "$f: MISSING"; done
```

- **All exist**: Pass.
- **Some missing**: Warn. The state file should contain the key content from these files, so they're reconstructible. Note which are missing.

---

## Check 8: Staleness

Calculate the age of the saved state by comparing the `timestamp` field to the current time.

- **< 24 hours**: Fresh. No warning needed.
- **1–7 days**: Mild staleness. Note and proceed: "This session is {N} days old. The codebase may have changed — check the git log above."
- **> 7 days**: Present staleness options explicitly:

```
This session was saved 12 days ago. The codebase has likely changed significantly.

Options:
1. Resume anyway — use the saved context but some references may be outdated
2. Resume with a fresh repo scan — re-run Phase 0 to update project context, then
   continue from where you left off
3. Start fresh — discard this state and begin a new session

Which would you prefer?
```

If the user picks option 2: run Phase 0 of the relevant skill (repo scan for brainstorm, plan re-read for executor, codebase reconnaissance for debug) with fresh data. Merge the new scan with the saved state — keeping all decisions, answers, and progress but updating the project context.

---

## Check 9: Skill Availability

If the state says `skill: ftm-debug` but that skill isn't in the skills directory:

"The saved session requires ftm-{skill} but that skill isn't available. Install it and try again."

Block resumption.

---

## Validation Summary

Run all applicable checks in order. Present a consolidated summary before asking the user to confirm:

```
Validation complete:
  ✓ State file: valid
  ✓ Project directory: exists
  ✓ Git state: same branch, 2 new commits (show log)
  ⚠ Worktrees: plan-exec/task-3 missing
  ✓ Plan file: exists
  ✓ Session age: 6 hours

1 warning. Ready to resume? (or review warnings first)
```

A single block-level failure prevents resumption. Warnings require user acknowledgment before proceeding.
