---
name: ftm-verify
description: Comprehensive post-execution verification and auto-remediation engine using dual-model adversarial analysis. Replaces ftm-retro. After ftm-executor completes a plan, this skill runs two independent verification passes in parallel — Codex (OpenAI) and Gemini (Google) — each reading the entire codebase to check plan fulfillment, documentation fidelity, build health, test quality (tests that probe real failure modes, not just happy paths), and wiring integrity. Falls back to Claude subagents if either CLI is unavailable. Reconciles findings, auto-remediates with parallel fix agents, and reports what was found, disagreed on, and fixed. Use when user says "verify", "is the plan done", "check everything", "verify plan", "ftm-verify", "did we miss anything", "is it complete", "validate the build", "check the plan", "verify execution", "post-execution check", or after any ftm-executor run completes. Also triggers on "retro", "retrospective", "how did that go", "execution review" since this skill supersedes ftm-retro. Even if the user just says "are we good?" after a plan execution — this is the skill.
---

## Events

### Emits
- `verification_complete` — when all verification phases finish and the final report is produced
- `issue_found` — when any verification agent discovers a gap, failure, or inconsistency
- `issue_remediated` — when a remediation agent successfully fixes a found issue
- `experience_recorded` — when a task outcome is written to the blackboard experience log (inherited from ftm-retro)
- `pattern_discovered` — when a recurring pattern is identified from accumulated experiences (inherited from ftm-retro)

### Listens To
- `task_completed` — micro-reflection trigger: record the task outcome as a structured experience entry
- `error_encountered` — failure analysis: record the error context as a failure experience for pattern learning
- `bug_fixed` — success recording: record the fix details as a positive experience

## Blackboard Read

Before starting, load context from the blackboard:

1. Read `~/.claude/ftm-state/blackboard/context.json` — check current_task, recent_decisions, active_constraints
2. Read `~/.claude/ftm-state/blackboard/experiences/index.json` — filter entries by task_type matching plan tasks and tags overlapping with verification, testing, documentation
3. Load top 3-5 matching experience files for common verification failures and effective remediation strategies
4. Read `~/.claude/ftm-state/blackboard/patterns.json` — check recurring_issues for systemic problems that keep appearing

If index.json is empty or no matches found, proceed normally.

# FTM Verify — Post-Execution Verification & Auto-Remediation

Comprehensive verification engine that answers one question: **"Is this plan actually done?"** Not "did the tasks run" — but "does the built system match what was planned, is it wired, tested, documented, and working?"

## Why This Exists

ftm-executor is good at running tasks. But "tasks completed" is not the same as "plan fulfilled." A task can pass its local tests while:
- Missing a feature the brainstorm plan specified
- Having tests that only check the happy path and miss every real failure mode
- Leaving INTENT.md entries stale or missing for new functions
- Having ARCHITECTURE.mmd that doesn't reflect the actual module graph
- Building cleanly but having dead code or unwired components
- Having PROGRESS.md that says "complete" for items that are half-done

This skill exists because the gap between "tasks ran" and "plan delivered" is where quality goes to die. It closes that gap with parallel verification agents, auto-remediates everything it can, and gives you a clear picture of what's actually done.

## Operating Modes

### Mode 1: Auto-triggered by ftm-executor (Phase 6.5)

ftm-executor calls this skill after all waves complete and the final commit is made. It passes execution context directly:

- Plan document path and title
- Task count, wave count, agents spawned
- Per-task audit results (pass/fail/auto-fix counts)
- Codex gate results per wave
- Total execution duration
- Errors, blockers, or manual interventions
- PROGRESS.md path

When invoked in this mode, proceed directly to Phase 1 — all data is available.

### Mode 2: Manual (`/ftm verify` or `/ftm-verify`)

When invoked without execution context:

1. Search the current project for the most recent `PROGRESS.md`. Read it fully to reconstruct what ran.
2. Look for plan files — check `~/.claude/plans/` for the most recently modified `.md` file, or ask the user which plan to verify against.
3. If no PROGRESS.md exists, check `~/.claude/ftm-retros/` for recent reports and ask the user which execution they want to verify.
4. Once context is established, proceed to Phase 1.

Never ask the user to provide data you can find yourself. Read the files.

---

## Phase 0.5: CLI Availability Check

Before doing anything else, detect which external CLI tools are available and authenticated. This determines the verification strategy.

**Run these checks in parallel:**

```bash
# Check Codex
CODEX_AVAILABLE=false
if command -v codex &>/dev/null; then
  # Verify auth by running a trivial command
  if codex exec --full-auto --ephemeral -m "o3" "echo CODEX_AUTH_OK" 2>/dev/null | grep -q "CODEX_AUTH_OK"; then
    CODEX_AVAILABLE=true
  fi
fi

# Check Gemini
GEMINI_AVAILABLE=false
if command -v gemini &>/dev/null; then
  # Verify auth by running a trivial prompt
  if gemini --yolo -o text "echo GEMINI_AUTH_OK" 2>/dev/null | grep -q "GEMINI_AUTH_OK"; then
    GEMINI_AVAILABLE=true
  fi
fi
```

**Strategy selection — three-tier verification:**

All tiers always run. The question is only which tools are available for the first two tiers.

| Codex | Gemini | Tier 1 & 2 Strategy |
|-------|--------|---------------------|
| Yes | Yes | **Codex + Gemini** — both external models verify in parallel |
| Yes | No | **Codex + Claude broad-pass** — Codex does Tier 1, Claude subagent does Tier 2 |
| No | Yes | **Gemini + Claude broad-pass** — Gemini does Tier 1, Claude subagent does Tier 2 |
| No | No | **Claude dual broad-pass** — two Claude subagents with different system prompts |

**Tier 3 (6 specialized Claude subagents) ALWAYS runs regardless of Tier 1 & 2 availability.** This is the deep, granular verification layer that catches what the broad passes miss.

Report the strategy to the user:
```
CLI check:
  Codex: [installed + authenticated / installed but auth failed / not installed]
  Gemini: [installed + authenticated / installed but auth failed / not installed]

Verification plan:
  Tier 1: [Codex / Claude broad-pass] — full codebase analysis
  Tier 2: [Gemini / Claude broad-pass] — independent second opinion
  Tier 3: 6 specialized Claude subagents (always) — deep domain-specific verification
  Tier 4: Reconciliation + auto-remediation
```

**Auth failure handling:** If a CLI is installed but auth fails, suggest the user run the auth command:
- Codex: `codex login`
- Gemini: `gemini` (interactive auth flow on first run)

Then fall back to Claude broad-pass for that tier. Do not block on auth — proceed with what's available.

---

## Phase 1: Context Assembly

Before dispatching verification passes, build the full picture:

1. **Read the plan document** — extract every task, feature, acceptance criterion, and deliverable. This is your checklist.
2. **Read PROGRESS.md** — understand what was reported as complete vs incomplete.
3. **Read all documentation files** — INTENT.md (root + per-module), ARCHITECTURE.mmd (root + per-module DIAGRAM.mmd), STYLE.md, DEBUG.md.
4. **Get the git diff** — `git diff <pre-execution-commit>..HEAD --stat` to understand total scope of changes.
5. **Identify the test suite** — locate test runner config (jest, vitest, pytest, etc.) and understand how to run tests.

Output a brief status before dispatching:
```
Verification starting for: [plan title]
Tasks in plan: [N]
Files changed: [N]
Dispatching Pass 1 (Codex) and Pass 2 (Gemini) in parallel...
```

---

## Phase 2: Dual-Model Adversarial Verification

The core of ftm-verify is two independent verification passes by different AI models, run in parallel. Each model reads the entire codebase and plan independently and produces findings. This adversarial approach catches blind spots that any single model would miss — different models have different biases, different code-reading strengths, and different failure-mode intuitions.

### Why Two Models Instead of One

A single model verifying its own ecosystem's output is like grading your own homework. Codex (OpenAI) and Gemini (Google) bring genuinely different perspectives:
- They parse code differently and catch different classes of issues
- They have different training biases about what "good tests" and "clean code" look like
- Disagreements between them surface the most interesting findings — if both models flag the same issue, it's almost certainly real; if only one flags it, it's worth investigating
- This mirrors the ftm-council philosophy: multi-model deliberation reduces blind spots

### Pass 1: Codex Deep Verification

Launch Codex with full read access to analyze the entire project against the plan. Codex runs in `--full-auto` mode with `--ephemeral` to prevent session persistence. The output is captured to a file for parsing.

**Command construction:**

```bash
codex exec --full-auto --ephemeral \
  -m "o3" \
  -C "[project_root]" \
  -o "[workspace]/codex-report.md" \
  "$(cat <<'PROMPT'
You are a post-execution verification agent. A plan was executed and you need to
determine whether the result is actually complete, correct, and production-ready.

READ THESE FILES FIRST:
- Plan: [plan_path]
- Progress: [project_root]/PROGRESS.md
- All documentation: INTENT.md, ARCHITECTURE.mmd, STYLE.md, DEBUG.md (root + per-module)

Then systematically verify ALL of the following. Be adversarial — your job is to
find problems, not confirm success.

## 1. PLAN FULFILLMENT
For EACH task in the plan:
- Read the acceptance criteria
- Find and READ the actual implementation code (not just check if files exist)
- Verify each acceptance criterion is met
- Rate: FULFILLED / PARTIAL (list gaps) / MISSING / DIVERGED (describe difference)

## 2. DOCUMENTATION FIDELITY
For each documentation file:
- INTENT.md: Every function in code has an entry? Entries match actual behavior?
  Stale entries for deleted functions? Module map complete?
- ARCHITECTURE.mmd: Nodes match real modules? Edges match real imports?
  Missing modules? Phantom modules?
- STYLE.md: Sample 5-10 changed files — do they follow declared Hard Limits?
- PROGRESS.md: Tasks marked COMPLETE are actually complete?
- DEBUG.md: Exists if debugging occurred?

## 3. BUILD & COMPILE
Run these commands and report results:
- Dependency install (npm install / pip install / etc.)
- Type check (tsc --noEmit / mypy / etc.) — zero errors required
- Lint check (eslint / ruff / etc.) — report real errors
- Build (npm run build / python -m build / etc.) — must exit 0
- Check for circular imports

## 4. TEST QUALITY (MOST IMPORTANT)
For each feature in the plan, find its tests and evaluate:
- Do tests cover FAILURE MODES? (invalid input, boundaries, error paths,
  race conditions, state transitions)
- Are assertions specific? (exact values, not just toBeTruthy)
- Are mocks realistic? (match real API shapes)
- Would the tests catch a real bug, or do they just make green checkmarks?

Rate each feature: STRONG / ADEQUATE / WEAK / MISSING
List specific failure modes that have NO test coverage.
Flag tautological tests (tests that pass even with broken code).

## 5. WIRING INTEGRITY
For every NEW file created:
- Trace import chain to entry point — is it reachable?
- If component: is it rendered in JSX?
- If route/view: is there a route config entry?
- If API function: is it called somewhere?
- If store field: is it read somewhere?
Flag orphaned code, broken chains, dead exports.

## 6. EXECUTION QUALITY
Score 0-10 with evidence citations (from PROGRESS.md):
- Wave Parallelism Efficiency
- Audit Pass Rate (% first-pass)
- Codex Gate Pass Rate (% first-pass)
- Retry/Fix Count: max(0, 10 - (retries/tasks)*5)
- Execution Smoothness (blockers, manual interventions)

OUTPUT FORMAT — use this EXACT structure:

CODEX_VERIFICATION_REPORT

### Plan Fulfillment
| Task | Status | Evidence | Gaps |
|------|--------|----------|------|

### Documentation Fidelity
| Document | Status | Issues |
|----------|--------|--------|
MISSING_ENTRIES: ...
STALE_ENTRIES: ...

### Build & Compile
| Check | Status | Details |
|-------|--------|---------|
BLOCKERS: ...

### Test Quality
| Feature | Test Files | Rating | Missing Coverage |
|---------|-----------|--------|-----------------|
FAILURE_MODES_NOT_TESTED: ...
TAUTOLOGICAL_TESTS: ...

### Wiring
| Item | Type | Status | Chain |
|------|------|--------|-------|
ORPHANED: ...

### Execution Scores
| Dimension | Score | Evidence |
|-----------|-------|----------|
Overall: X/50
PROMPT
)"
```

**Fallback (Codex unavailable):** If Phase 0.5 determined Codex is not available, spawn a Claude subagent (Agent tool) with the same prompt text above. Give the subagent `mode: "auto"` and include "Save your full report to [workspace]/codex-report.md" in the prompt. Log: "Codex not available — using Claude subagent for Pass 1."

### Pass 2: Gemini Deep Verification

Launch Gemini in parallel with Codex. Gemini runs in `--yolo` mode for full autonomous access. Output is captured via `--output-format json` or redirected to a file.

**Command construction:**

```bash
gemini --yolo \
  -m "gemini-2.5-pro" \
  --output-format text \
  "$(cat <<'PROMPT'
You are an independent post-execution verification agent. A different AI already
built this project from a plan. Your job is to verify the work with fresh eyes.
Be skeptical — assume nothing works until you prove it does.

READ THESE FILES FIRST:
- Plan: [plan_path]
- Progress: [project_root]/PROGRESS.md
- All documentation: INTENT.md, ARCHITECTURE.mmd, STYLE.md, DEBUG.md (root + per-module)

Systematically verify ALL of the following:

## 1. PLAN FULFILLMENT
For EACH task in the plan:
- Read the acceptance criteria
- Find and READ the actual code (files existing is not proof of completion)
- Verify each criterion is genuinely met
- Rate: FULFILLED / PARTIAL (list what's missing) / MISSING / DIVERGED

## 2. DOCUMENTATION ACCURACY
Check every documentation file against the ACTUAL CODE (not the plan):
- INTENT.md entries match real function behavior?
- ARCHITECTURE.mmd nodes/edges match real modules/imports?
- STYLE.md rules actually followed in the code?
- PROGRESS.md statuses match reality?
- Any functions without docs? Any docs for deleted functions?

## 3. BUILD HEALTH
Run and report:
- Dependency resolution
- Type checking (zero errors)
- Linting (real errors only)
- Full build (must succeed)
- Circular import check

## 4. TEST QUALITY — THIS IS THE MOST IMPORTANT CHECK
For each planned feature, find its tests. Then ask:
- Would these tests catch a REAL bug? Or do they just verify the happy path?
- Do they test: invalid input? boundary conditions? error paths? concurrency?
- Are assertions specific (exact values) or vague (toBeTruthy, toBeDefined)?
- Are mocks realistic or do they return empty objects?
- If I broke the implementation, would these tests actually fail?

Rate: STRONG / ADEQUATE / WEAK / MISSING per feature.
List every failure mode you can think of that has NO test.

## 5. WIRING CHECK
For new code:
- Is every file reachable from the entry point?
- Components rendered? Routes registered? APIs called? Store fields read?
- Any dead exports or orphaned files?

## 6. EXECUTION SCORING
Score 0-10 each with data citations:
- Wave Parallelism, Audit Pass Rate, Codex Gate Pass Rate,
  Retry Count, Smoothness

OUTPUT FORMAT — use EXACT structure:

GEMINI_VERIFICATION_REPORT

### Plan Fulfillment
| Task | Status | Evidence | Gaps |
|------|--------|----------|------|

### Documentation
| Document | Status | Issues |
|----------|--------|--------|

### Build
| Check | Status | Details |
|-------|--------|---------|

### Test Quality
| Feature | Rating | Missing Coverage |
|---------|--------|-----------------|
FAILURE_MODES_NOT_TESTED: ...

### Wiring
| Item | Status | Details |
|------|--------|---------|

### Execution Scores
| Dimension | Score | Evidence |
|-----------|-------|----------|
Overall: X/50
PROMPT
)" > "[workspace]/gemini-report.md" 2>&1
```

**Fallback (Gemini unavailable):** If Phase 0.5 determined Gemini is not available, spawn a Claude subagent with the same prompt text above. Give the subagent `mode: "auto"` and include "Save your full report to [workspace]/gemini-report.md" in the prompt. Log: "Gemini not available — using Claude subagent for Pass 2."

### Launching Both Passes

Both commands run simultaneously. Use background processes:

```bash
# Launch both in parallel
codex exec --full-auto --ephemeral -m "o3" -C "$PROJECT_ROOT" \
  -o "$WORKSPACE/codex-report.md" "$CODEX_PROMPT" &
CODEX_PID=$!

gemini --yolo -m "gemini-2.5-pro" "$GEMINI_PROMPT" \
  > "$WORKSPACE/gemini-report.md" 2>&1 &
GEMINI_PID=$!

# Wait for both
wait $CODEX_PID
CODEX_EXIT=$?
wait $GEMINI_PID
GEMINI_EXIT=$?
```

While Tier 1 & 2 run, immediately launch Tier 3 in parallel — don't wait for the broad passes to finish.

---

## Phase 2.5: Tier 3 — Specialized Claude Subagents

Launch ALL 6 specialized subagents simultaneously via the Agent tool. Each agent goes deep on one verification dimension — they read every relevant file, run commands, and produce structured findings. These agents have domain expertise that the broad Codex/Gemini passes lack.

The power of this architecture: Tier 1 & 2 give you breadth (two different models reading everything), Tier 3 gives you depth (six specialists each going deep on their domain). Together they form a verification net that's extremely hard to slip through.

**Read `agents/tier3-prompts.md`** for the exact prompt text for each agent. The 6 agents are:

| Agent | Domain | What It Checks |
|-------|--------|---------------|
| **1. Plan Fulfillment** | Features vs plan | Every acceptance criterion met? Code exists and is complete? |
| **2. Doc Fidelity** | Documentation accuracy | INTENT.md, ARCHITECTURE.mmd, STYLE.md, PROGRESS.md, DEBUG.md all match code? |
| **3. Build & Compile** | Build health | Dependencies, types, lint, build, circular imports — all green? |
| **4. Test Quality** | Test effectiveness | Tests probe failure modes? Or just happy-path checkmarks? **(Most important agent)** |
| **5. Wiring** | Code connectivity | Everything reachable from entry point? No orphaned files/exports? |
| **6. Execution Scoring** | Execution quality | Wave parallelism, audit pass rate, retry count, smoothness (0-10 each) |

Replace `[plan_path]`, `[project_root]`, and `[progress_path]` placeholders in the prompts before dispatching.

### Launching All Tiers

All 8 processes (2 CLI + 6 subagents) launch simultaneously:

```
Tier 1: Codex exec (background process)         ─┐
Tier 2: Gemini (background process)              ─┤── All running in parallel
Tier 3 Agent 1: Plan Fulfillment Checker         ─┤
Tier 3 Agent 2: Documentation Fidelity Checker   ─┤
Tier 3 Agent 3: Build & Compile Verifier         ─┤
Tier 3 Agent 4: Test Quality Auditor             ─┤
Tier 3 Agent 5: Wiring Integrity Checker         ─┤
Tier 3 Agent 6: Execution Quality Scorer         ─┘
```

As each returns, collect its report. Proceed to Phase 3 once all 8 are done.

---

## Phase 3: Three-Tier Reconciliation & Triage

After all tiers complete, reconcile findings across all three tiers. This is where the architecture's power becomes clear — you have three independent verification perspectives, each with different strengths.

### Step 1: Parse All Reports

Read all 8 reports:
- `[workspace]/codex-report.md` (Tier 1)
- `[workspace]/gemini-report.md` (Tier 2)
- 6 subagent reports from Tier 3

### Step 2: Cross-Tier Agreement Classification

For each finding across the 6 verification dimensions:

| Agreement Level | Meaning | Confidence | Action |
|----------------|---------|------------|--------|
| **All 3 tiers flag it** | Unanimous — definitely a real issue | Very high | Auto-remediate immediately |
| **2 of 3 tiers flag it** | Strong consensus — almost certainly real | High | Auto-remediate |
| **Only 1 tier flags it** | Possible false positive OR unique catch | Medium | Claude adjudicates by reading the code. Tier 3 specialists get extra trust for their domain. |
| **All 3 tiers say PASS** | Unanimous pass — very likely fine | Very high | No action |
| **Scores disagree by >2 points** | Different evidence interpretation | — | Use the lowest (most conservative) score; note disagreement |

**Tier 3 domain trust rule:** When a Tier 3 specialist disagrees with the broad Tier 1/2 passes on something in its domain, lean toward the specialist. A test quality auditor that says tests are WEAK overrides a broad pass that said ADEQUATE — the specialist read every test file in detail while the broad pass skimmed.

### Step 3: Build Cross-Tier Disagreement Map

```
CROSS-TIER DISAGREEMENT MAP:
| Item | Tier 1 (Codex) | Tier 2 (Gemini) | Tier 3 (Specialist) | Adjudication | Notes |
|------|---------------|----------------|--------------------|--------------|----|
| Task 5 | FULFILLED | PARTIAL | PARTIAL (Agent 1) | PARTIAL — 2/3 consensus | Codex missed error handling gap |
| Test: auth | ADEQUATE | WEAK | WEAK (Agent 4) | WEAK — specialist + Gemini agree | Agent 4 found 4 untested failure modes |
| INTENT.md | 3 stale | ACCURATE | 2 stale (Agent 2) | 3 stale — Tier 1 most thorough here | Gemini missed renamed functions |
| Build | PASS | PASS | FAIL: 2 type errors (Agent 3) | FAIL — Agent 3 actually ran tsc | Broad passes may not have executed build |
```

### Step 4: Triage Categories

Every confirmed finding goes into one of these buckets:

| Category | Criteria | Action |
|----------|----------|--------|
| **BLOCKER** | Build fails, tests crash, missing critical feature | Must fix before declaring done |
| **REMEDIATE** | Stale docs, weak tests, orphaned code, partial features | Auto-fix via remediation agents |
| **NOTE** | Minor style issues, non-critical warnings, informational | Log in report, don't fix |

### Triage Rules

- Plan item MISSING → BLOCKER
- Plan item PARTIAL → REMEDIATE (if small gap) or BLOCKER (if major gap)
- Plan item DIVERGED → NOTE (document the divergence, user decides)
- **Documentation layer MISSING (never created)** → **BLOCKER — DO NOT auto-remediate.** This means ftm-executor's Phase 1.5 (Documentation Layer Bootstrap) failed or was skipped. Bootstrapping INTENT.md/ARCHITECTURE.mmd from scratch is the executor's job, not verify's. Report: `"BLOCKER: Documentation layer was never bootstrapped by executor. INTENT.md / ARCHITECTURE.mmd / STYLE.md not found. Re-run executor Phase 1.5 or invoke ftm-intent / ftm-diagram manually."`
- Documentation STALE or INCOMPLETE (exists but inaccurate) → REMEDIATE (update entries to match code)
- Build/type/lint failure → BLOCKER
- Test quality WEAK → REMEDIATE (write better tests)
- Test quality MISSING → BLOCKER (write tests)
- Wiring ORPHANED → REMEDIATE
- Execution scores → NOTE (informational, no fix needed)

---

## Phase 4: Parallel Auto-Remediation

For every BLOCKER and REMEDIATE finding, dispatch fix agents. Launch as many in parallel as possible — group by domain to avoid file conflicts.

### Remediation Agent Prompt Template

```
You are a remediation agent fixing issues found during post-execution verification.

Project root: [path]
Plan path: [path] (for context on what was intended)

YOUR ASSIGNED FIXES:
[list of findings with category, location, and what needs to change]

For each fix:
1. Read the relevant code and documentation
2. Make the fix
3. Verify the fix (run tests if you wrote tests, re-check docs if you updated docs)
4. Commit with a clear message: "fix(verify): [what was fixed]"

RULES:
- Fix EXACTLY what's listed. Don't refactor surrounding code.
- For missing tests: write tests that probe FAILURE MODES, not just happy paths.
  Every test you write should answer "what bug would this catch?"
  If you can't answer that question, the test is useless.
- For stale documentation: update to match ACTUAL code behavior, not planned behavior.
- For orphaned code: wire it in if the plan calls for it, remove it if it's dead.
- For missing plan features: implement them following the plan's acceptance criteria.
- If a fix requires changes to files another remediation agent is working on,
  note the conflict and skip — it will be caught in re-verification.

OUTPUT:
REMEDIATION_REPORT
| Finding | Fix Applied | Verified | Commit |
|---------|------------|----------|--------|
| [finding] | [what was done] | PASS/FAIL | [commit hash] |

COULD_NOT_FIX: [list any findings that need manual intervention, with reason]
```

### Remediation Grouping Strategy

Group findings to minimize file conflicts between parallel agents:

1. **Doc fixes** — one agent handles ALL documentation updates (INTENT.md, ARCHITECTURE.mmd, DIAGRAM.mmd, PROGRESS.md)
2. **Test fixes** — one agent per module/domain writes missing tests and strengthens weak ones
3. **Code fixes** — one agent per module handles missing features, wiring, dead code
4. **Build fixes** — one agent handles dependency issues, type errors, lint errors

### Remediation Limits

- Max 3 attempts per finding. If it can't be fixed in 3 tries, flag for manual intervention.
- Max 2 remediation rounds total. After round 2, report remaining issues and stop.
- If remediation introduces NEW issues (regression), revert and flag.

---

## Phase 5: Re-Verification

After all remediation agents complete:

1. **Re-run build** — confirm everything still compiles
2. **Re-run tests** — confirm all tests pass (including newly written ones)
3. **Spot-check docs** — verify remediated documentation entries are accurate
4. **Spot-check wiring** — verify previously orphaned code is now connected

If re-verification finds new issues introduced by remediation:
- If minor: fix inline and commit
- If major: revert the remediation commit and flag for manual intervention

---

## Phase 6: Report Generation

### Step 1: Create report directory

```bash
mkdir -p ~/.claude/ftm-retros/
```

Using the same directory as ftm-retro for backwards compatibility — this skill supersedes it.

### Step 2: Generate plan slug

Take the plan title, lowercase, replace spaces with hyphens, strip non-alphanumeric except hyphens.

### Step 3: Check for past reports

Read all `.md` files in `~/.claude/ftm-retros/` for the Pattern Analysis section.

### Step 4: Write the report

Save to: `~/.claude/ftm-retros/{plan-slug}-{YYYY-MM-DD}.md`

```markdown
# Verify: {Plan Title}

**Date:** {YYYY-MM-DD}
**Plan:** {absolute path to plan file}
**Duration:** {total execution time}
**Verification Duration:** {time spent on verification + remediation}
**Verification Strategy:** {Full adversarial (Codex + Gemini) / Codex + Claude / Gemini + Claude / Claude dual-subagent}

## Plan Fulfillment

| Task | Status | Notes |
|------|--------|-------|
| 1. [title] | FULFILLED / PARTIAL / MISSING / DIVERGED | [details] |

**Fulfillment Rate: {N}/{total} tasks fully implemented**

## Verification Summary

| Check | Tier 1 | Tier 2 | Tier 3 (Specialist) | Consensus | Remediated | Remaining |
|-------|--------|--------|--------------------|-----------|-----------:|----------:|
| Plan Fulfillment | [N] gaps | [N] gaps | [N] gaps (Agent 1) | [N] confirmed | [N] fixed | [N] |
| Documentation | [N] issues | [N] issues | [N] issues (Agent 2) | [N] confirmed | [N] fixed | [N] |
| Build & Compile | [N] errors | [N] errors | [N] errors (Agent 3) | [N] confirmed | [N] fixed | [N] |
| Test Quality | [N] weak | [N] weak | [N] weak (Agent 4) | [N] confirmed | [N] strengthened | [N] |
| Wiring | [N] orphaned | [N] orphaned | [N] orphaned (Agent 5) | [N] confirmed | [N] wired | [N] |

## Cross-Tier Disagreement Map

| Item | Tier 1 (Codex/Claude) | Tier 2 (Gemini/Claude) | Tier 3 (Specialist) | Adjudication | Notes |
|------|----------------------|----------------------|--------------------|--------------|-------|
| [item] | [finding] | [finding] | [finding] | [decision] | [reasoning] |

## Execution Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Wave Parallelism | X/10 | {evidence} |
| Audit Pass Rate | X/10 | {evidence} |
| Codex Gate Pass Rate | X/10 | {evidence} |
| Retry/Fix Count | X/10 | {evidence} |
| Execution Smoothness | X/10 | {evidence} |

**Execution Score: {sum}/50**

## What Was Found & Fixed

{List every finding that was auto-remediated, grouped by category}

### Documentation Fixes
- [what was stale/missing] → [what was added/updated] ([commit hash])

### Test Improvements
- [feature] — added [N] tests covering: [failure modes] ([commit hash])

### Wiring Fixes
- [component/function] — [what was orphaned] → [how it was connected] ([commit hash])

### Code Fixes
- [feature] — [what was missing/broken] → [what was implemented/fixed] ([commit hash])

## Remaining Issues

{List anything that could NOT be auto-remediated}

| Issue | Category | Reason Not Fixed | Suggested Action |
|-------|----------|-----------------|-----------------|
| [issue] | BLOCKER/REMEDIATE | [why auto-fix failed] | [what the user should do] |

## Test Quality Summary

| Feature | Rating | Coverage Notes |
|---------|--------|---------------|
| [feature] | STRONG/ADEQUATE/WEAK/MISSING | [what's tested, what's not] |

**Failure modes not tested:** [list specific scenarios]

## What Went Well

{2-4 specific observations grounded in data}

## What Was Slow

{2-4 specific bottlenecks with timing data}

## Proposed Improvements

{3-5 specific, actionable suggestions}
Format: **N. {Title}** — {Skill to change} — {Change} — {Expected impact}

## Pattern Analysis

{Only if past reports exist in ~/.claude/ftm-retros/}

### Recurring Issues
{Problems appearing in 2+ reports}

### Score Trends
{Compare scores across reports with actual numbers}

### Unaddressed Suggestions
{Format: **[ESCALATED]** {suggestion} — first proposed in {slug-date}, appeared {N} times}
```

---

## Phase 7: Output

After saving the report, print to the user:

```
Verification complete: ~/.claude/ftm-retros/{filename}

Plan Fulfillment: {N}/{total} tasks ({percentage}%)
Execution Score: {X}/50

Found {N} issues:
  - {N} auto-remediated ({N} doc fixes, {N} test improvements, {N} wiring fixes, {N} code fixes)
  - {N} remaining (require manual attention)

Top issue: {single most impactful remaining problem, or "none — all clear"}
```

Do not print the full report to the terminal. The summary above is sufficient.

---

## Key Behaviors

### Tests that find bugs, not tests that pass

The test quality auditor is the most important part of this skill. When remediation agents write tests, every test must answer the question: "what bug would this catch?" A test that only verifies the happy path with `expect(result).toBeTruthy()` is actively harmful — it creates false confidence that the feature works when it might fail on the first edge case a real user hits.

Good test remediation looks like:
- "Added test for empty input — the function returned undefined instead of throwing, which would cause a silent failure downstream"
- "Added test for concurrent requests — discovered the cache doesn't handle race conditions"
- "Added test for malformed API response — the error handler swallows the error and returns null"

Bad test remediation looks like:
- "Added test that calls the function and checks it returns something"
- "Added test that mocks everything and verifies the mock was called"

### Evidence-first scoring

Every score needs a citation. "Tasks passed audit" is not a citation. "12/14 tasks passed audit on first attempt; Tasks 3 and 9 each needed one auto-fix cycle" is a citation. If data is genuinely unavailable, note the gap and score conservatively.

### Documentation must match code, not plans

When checking documentation fidelity, the source of truth is the CODE, not the plan. If the plan said "build a REST API" but the implementation uses GraphQL, the INTENT.md should document the GraphQL implementation — not the planned REST API. Documentation that describes planned behavior instead of actual behavior is worse than missing documentation.

### Remediation is surgical, not sweeping

Fix agents should fix exactly what's flagged. A missing INTENT.md entry gets an INTENT.md entry. A weak test gets stronger assertions. An orphaned component gets wired in. No refactoring, no "while I'm here" improvements, no scope creep. The verification found specific issues; the remediation fixes those specific issues.

### Pattern escalation

Recurring issues appearing in 3+ reports get `[ESCALATED - 3+ occurrences]` and move to the top of Proposed Improvements. These are systemic problems, not noise.

### No vibes

Do not write "the execution went well" or "tests look good." Write "0 type errors, 0 build failures, 14/14 tasks fulfilled, 3 tests strengthened from WEAK to ADEQUATE." The report is read by future executions that need data, not encouragement.

---

## Micro-Reflection Mode

Inherited from ftm-retro. Lightweight experience entries recorded after significant actions.

### Trigger Events
- `task_completed` — any task completion
- `bug_fixed` — a bug was resolved
- `error_encountered` — an unexpected error during execution
- `code_committed` — a meaningful commit was made
- `plan_generated` — a plan was created
- `user_correction` — the user corrected the approach

### Reflection Format

"I [succeeded/failed/partially succeeded] at [task description] because [specific reason].
Next time I should [concrete actionable adjustment].
Confidence: [low/medium/high]"

### Experience Entry Creation

Write to `~/.claude/ftm-state/blackboard/experiences/YYYY-MM-DD_task-slug.json` following the blackboard schema. Key fields: task_type, description, approach, outcome, lessons, complexity_estimated vs complexity_actual, capabilities_used, tags, confidence.

### Pattern Extraction

After writing an experience, check for pattern promotion:
1. Read `experiences/index.json`
2. Count entries with overlapping task_type AND tags sharing the same lesson theme
3. If 3+ similar experiences → promote to `patterns.json`
4. Confidence: low at 3 occurrences, medium at 5+, high at 8+

### Pattern Decay

Patterns not reinforced within 30 days have confidence reduced: high → medium → low → removed. Check decay when reading patterns.json.

---

## Blackboard Write

After completing, update the blackboard:

1. Update `~/.claude/ftm-state/blackboard/context.json`:
   - Set current_task status to "complete"
   - Append verification summary to recent_decisions (cap at 10)
   - Update session_metadata.skills_invoked and last_updated
2. Write experience file to `~/.claude/ftm-state/blackboard/experiences/YYYY-MM-DD_task-slug.json`
3. Update `~/.claude/ftm-state/blackboard/experiences/index.json`
4. Emit `verification_complete` event

## Requirements

- reference: `PROGRESS.md` | optional | execution progress log
- reference: `~/.claude/ftm-retros/` | optional | prior reports for pattern analysis
- reference: `references/protocols/SCORING-RUBRICS.md` | required | scoring scale breakpoints and evidence requirements
- reference: `references/templates/REPORT-FORMAT.md` | required | verification report output template
- reference: `references/protocols/REMEDIATION-STRATEGIES.md` | required | fix strategies by finding type
- reference: `references/protocols/TEST-QUALITY-RUBRICS.md` | required | test quality rating criteria
- reference: `~/.claude/ftm-state/blackboard/experiences/index.json` | optional | experience inventory
- reference: `~/.claude/ftm-state/blackboard/patterns.json` | optional | pattern registry
- tool: `git` | required | diff analysis and commit operations
- tool: `node` | optional | build, test, lint execution

## Risk

- level: medium_write
- scope: writes verification report to ~/.claude/ftm-retros/; remediation agents modify source files, test files, and documentation; writes experience files to blackboard; promotes patterns
- rollback: git revert remediation commits (all tagged with "fix(verify):" prefix); delete report file; remove experience entry from blackboard

## Approval Gates

- trigger: BLOCKER finding that cannot be auto-remediated | action: report to user with suggested fix, wait for input
- trigger: remediation would delete code | action: show what will be removed, get implicit approval via 3-second display (auto-proceed unless user objects)
- trigger: pattern promotion triggered (3+ matching experiences) | action: auto-promote (learning system behavior)
- trigger: 2 remediation rounds complete with remaining issues | action: stop remediation, report remaining issues
- complexity_routing: micro → auto | small → auto | medium → auto | large → auto | xl → auto

## Fallbacks

- condition: codex not installed or auth failed | action: use Claude subagent for Pass 1; suggest user run `codex login` for future runs
- condition: gemini not installed or auth failed | action: use Claude subagent for Pass 2; suggest user run `gemini` for interactive auth
- condition: both codex and gemini unavailable | action: run two independent Claude subagents with different system prompts for Tier 1 & 2 (one as "adversarial auditor", one as "skeptical reviewer"); Tier 3 still runs its 6 specialists regardless
- condition: PROGRESS.md not found and manual mode | action: check ~/.claude/ftm-retros/ for recent reports; ask user which execution to verify
- condition: plan document not found | action: ask user for plan path; if unavailable, skip plan fulfillment check and run other verifications only
- condition: no test runner detected | action: skip test execution, still audit test file quality if test files exist
- condition: knip not available | action: skip static analysis wiring, rely on grep-based tracing only
- condition: experiences/index.json has fewer than 10 entries | action: cold-start mode — record every task, set all confidence to low
- condition: no build system detected | action: skip build verification, note in report
- condition: codex exec times out (>10 minutes) | action: kill process, use partial output if available, fall back to Claude subagent for remaining checks
- condition: gemini process times out (>10 minutes) | action: kill process, use partial output if available, fall back to Claude subagent for remaining checks

## Capabilities

- cli: `codex` | preferred | Codex CLI for Pass 1 deep verification (`codex exec --full-auto --ephemeral`)
- cli: `gemini` | preferred | Gemini CLI for Pass 2 deep verification (`gemini --yolo`)
- cli: `git` | required | diff analysis and remediation commits
- cli: `node` | optional | build, test, and lint execution
- cli: `knip` | optional | static dead-code analysis
- env: `OPENAI_API_KEY` | optional | required for codex auth (may be pre-configured via `codex login`)
- env: `GEMINI_API_KEY` or Google auth | optional | required for gemini auth

## Event Payloads

### verification_complete
- skill: string — "ftm-verify"
- tier1_source: string — "codex" | "claude_subagent"
- tier2_source: string — "gemini" | "claude_subagent"
- tier3_agents: number — 6 (always)
- plan_fulfillment_rate: number — percentage of tasks fulfilled
- execution_score: number — total score out of 50
- issues_found: number — total issues across all agents
- issues_agreed: number — issues both passes agreed on
- issues_disputed: number — issues only one pass found (adjudicated)
- issues_remediated: number — issues auto-fixed
- issues_remaining: number — issues needing manual attention
- report_path: string — absolute path to saved report
- duration_ms: number — total verification + remediation time

### issue_found
- skill: string — "ftm-verify"
- agent: string — which verification agent found it
- category: string — "BLOCKER" | "REMEDIATE" | "NOTE"
- type: string — finding type (e.g., "MISSING_FEATURE", "STALE_DOCS", "WEAK_TESTS", "ORPHANED_CODE")
- location: string — file:line or document name
- description: string — what's wrong

### issue_remediated
- skill: string — "ftm-verify"
- original_finding: string — reference to the issue_found
- fix_description: string — what was done
- commit_hash: string — remediation commit
- verified: boolean — whether the fix was re-verified

### experience_recorded
- skill: string — "ftm-verify"
- experience_path: string — path to written experience file
- task_type: string — type of task recorded
- outcome: string — success | partial | failure
- confidence: string — low | medium | high

### pattern_discovered
- skill: string — "ftm-verify"
- pattern_name: string — name of the promoted pattern
- category: string — codebase_insights | execution_patterns | user_behavior | recurring_issues
- occurrence_count: number — experiences that triggered promotion
- confidence: string — low | medium | high
