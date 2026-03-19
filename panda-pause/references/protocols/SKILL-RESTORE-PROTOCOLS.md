# Skill State Capture and Restoration Protocols

This document defines exactly what state must be captured (by panda-pause) and restored (by panda-resume) for each panda skill. It is the shared contract between the two skills.

---

## panda-brainstorm

### State to Capture

**Phase tracking:**
- Current phase (0, 1, 2, or 3)
- If Phase 1: which round (1, 2, or 3), which path (A: Fresh Idea or B: Brain Dump)
- If Phase 2: how many research+challenge turns have been completed
- If Phase 3: which section of the plan has been presented (Vision, Tasks, Agents, or complete)

**Phase 0 context:**
- The full repo scan results (project type, tech stack, architecture, patterns, infrastructure, scale)
- Whether the scan was skipped (no git repo) and any stack info gathered from the user instead

**Phase 1 — Intake:**
- The user's original idea/request (verbatim if short, summarized if long)
- If Path B: the full brain dump extraction (decisions made, open questions, assumptions, contradictions, gaps)
- All user answers from each completed round
- Research Sprint 1 results (landscape context) — all findings from Web Researcher, GitHub Explorer, Competitive Analyst
- Research Sprint 2 results (constraint-scoped research) — all findings from all three agents
- If Path B: the novelty map (which claims are solved/partially solved/novel)

**Phase 2 — Research + Challenge Loop:**
- Every completed turn's 5 suggestions (or fewer if weak results) with evidence and links
- Every challenge posed and the user's response
- Every question asked and the user's answer
- Accumulated decisions and direction chosen
- Research agent results from each turn (summarized — full URLs and key findings, not raw agent output)
- The current "direction" the brainstorm is heading (architecture chosen, scope narrowed, etc.)

**Phase 3 — Plan Generation:**
- Which sections have been presented and approved (Vision, Tasks, Agents/Waves)
- The plan content generated so far
- The plan file path if it's been saved
- User feedback on each section

### Restoration Instructions

On resume, reload Phase 0 context into the project context register. Reload the full context register from Phase 2 state so the next research sprint does not re-search prior ground. Resume at exactly the turn number and phase detail captured — if the user was mid-Phase 2, the next action is a research sprint responding to their last answer.

---

## panda-executor

### State to Capture

**Plan context:**
- Plan file path (absolute)
- Plan title and summary
- Total task count
- Agent team composition (agent names, roles, task assignments)

**Execution progress:**
- Current wave number
- For each task: status (pending / in-progress / complete / failed / blocked)
- For completed tasks: commit hashes, audit results (pass/fail/auto-fixed), brief summary of what was done
- For in-progress tasks: which agent is working on it, what's been done so far
- For failed/blocked tasks: what went wrong, error details

**Worktree state:**
- List of all worktree branches and their paths
- Which worktrees are active vs merged vs abandoned
- Any merge results or conflicts encountered
- The main/working branch name

**Verification state:**
- Post-task audit results for each completed task
- Any manual intervention items outstanding
- Full test suite status (last run result)

### Restoration Instructions

On resume, verify that all worktrees in the saved state still exist on disk (`git worktree list`). If any are missing, note them for the user before continuing. Resume from the current wave, skipping tasks already marked complete. If a task was in-progress, treat it as needing restart from the beginning of that task.

---

## panda-debug

### State to Capture

**Problem context:**
- The original problem statement (symptom, expected behavior, what's been tried, when it started, reproduction steps)
- Codebase reconnaissance results (entry points, call graph, state flow, dependencies, recent changes, test coverage, config, error handling)
- The investigation plan (likely category, which agents deployed, worktree strategy)

**Phase 1 — Investigation results:**
- Instrumenter report: what was instrumented, log point locations, DEBUG-INSTRUMENTATION.md content
- Researcher report: findings with sources, relevance, solutions, confidence, RESEARCH-FINDINGS.md content
- Reproducer report: trigger command, consistency, boundaries, minimal test path, REPRODUCTION.md content
- Hypothesizer report: all hypotheses ranked with claims, mechanisms, code paths, evidence, HYPOTHESES.md content

**Phase 2 — Synthesis & Solve:**
- Cross-reference analysis (how findings align or conflict)
- Recommended fix approach
- Solver attempts: which hypotheses tried, what was implemented, commit hashes
- FIX-SUMMARY.md content if fix was applied

**Phase 3 — Review & Verify:**
- Reviewer verdict (APPROVED / APPROVED WITH CHANGES / NEEDS REWORK)
- REVIEW-VERDICT.md content
- How many solver-reviewer iterations completed
- Outstanding issues from review

**Worktree state:**
- debug-instrumentation branch and path
- debug-reproduction branch and path
- debug-fix branch and path (including any fix attempt sub-branches)
- Which worktrees still exist vs cleaned up

### Restoration Instructions

On resume, verify debug worktrees still exist. Re-read any artifact files referenced in the state (HYPOTHESES.md, REPRODUCTION.md, etc.) to reload their content into context. Resume at the exact phase captured — if mid-Phase 2, proceed to the next solver iteration using the saved hypotheses and prior solver attempts.

---

## panda-council

### State to Capture

**Council setup:**
- The council prompt (the framed problem statement)
- Whether the user confirmed/edited the prompt
- Prerequisites check result (codex and gemini available?)

**Deliberation state:**
- Current round number (1-5)
- For each completed round, each model's full response:
  - Research summary (what files examined, what was found)
  - Position (their stance)
  - Reasoning (with code references)
  - Concerns
  - Confidence level
- For rebuttal rounds: each model's updated position, new evidence, responses to other models, remaining disagreements
- Alignment analysis after each round (agreement areas, divergence points, different research paths, majority forming?)

**Outcome:**
- Whether consensus has been reached (and if so, which 2 models agreed)
- The verdict if delivered (decision, agreed by, dissent, evidence basis)
- If no consensus after 5 rounds: the synthesis and options presented

### Restoration Instructions

On resume, re-present the council prompt and the round history as a summary before continuing. If consensus was already reached, surface the verdict and ask the user what they want next. If still in deliberation, resume with the next model dispatch using full prior-round context.

---

## panda-audit

### State to Capture

**Trigger context:**
- What triggered the audit (manual invocation, post-task from executor, specific files/scope)
- Scope (full project, specific files, specific task's changes)

**Phase 0 — Project patterns:**
- Detected framework, router, state management, API layer, build tool
- Active dimensions (D1-D5) and their configuration
- Any unusual patterns noted

**Layer 1 — knip results:**
- Full knip output (categorized: unused files, unused exports, unused deps, unlisted deps, unresolved imports)
- Each finding with file:line

**Layer 2 — Adversarial audit results:**
- Each finding with type, location, evidence, and which dimension failed
- Wiring contract checks if applicable (which checks passed, which failed)

**Layer 3 — Auto-fix results:**
- Fixes applied (finding, fix description, verification result)
- Manual intervention items (finding, reason auto-fix skipped, suggested action)
- Re-verification results
- Current iteration count (of max 3)

**Final status:**
- PASS or FAIL
- Remaining issues count and details

### Restoration Instructions

On resume, skip any layers already completed. If mid-Layer 3 auto-fix loop, restore the iteration count and continue from where it left off. If the final status was PASS, surface the result and confirm with the user before doing anything further.
