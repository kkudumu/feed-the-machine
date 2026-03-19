# Scoring Rubrics — All 5 Dimensions

Detailed rubrics for ftm-retro scoring. Each dimension is scored 0–10 with a citation to specific data. Do not estimate without evidence — if data is missing, note it and score conservatively.

---

## Dimension 1: Wave Parallelism Efficiency (0–10)

Were independent tasks actually dispatched in parallel? Could more tasks have been parallelized?

- **10**: Every task that could run in parallel did. No serial bottlenecks where parallelism was possible.
- **7–9**: Minor serial steps that could have been parallel (e.g., final post-processing tasks run sequentially).
- **4–6**: Significant parallelism opportunities missed. Tasks that had no dependencies ran serially.
- **1–3**: Nearly all tasks ran serially despite having no dependencies on each other.
- **0**: Everything was serial regardless of dependency structure.

Evidence to cite: wave structure from PROGRESS.md, task dependency graph, agent dispatch timestamps.

---

## Dimension 2: Audit Pass Rate (0–10)

What percentage of tasks passed ftm-audit on the first attempt?

- **10**: 100% first-pass. No task needed a fix cycle.
- **8**: 90%+ first-pass. One or two tasks needed minor fixes.
- **6**: 75–89% first-pass.
- **4**: 50–74% first-pass. Roughly half the tasks needed audit remediation.
- **2**: Below 50% first-pass.
- **0**: Every single task failed audit on the first attempt.

Evidence to cite: per-task audit results (pass/fail counts, auto-fix counts, manual-fix counts).

---

## Dimension 3: Codex Gate Pass Rate (0–10)

What percentage of waves passed the ftm-codex-gate on the first attempt?

- **10**: All waves passed on first gate run.
- **7–9**: One wave needed a fix-and-retry.
- **4–6**: Multiple waves needed retries.
- **1–3**: Most waves failed the gate at least once.
- **0**: Every wave failed the gate.

Evidence to cite: codex gate results per wave (pass/fail, failure types).

---

## Dimension 4: Retry and Fix Count (0–10)

How many total review-fix cycles were needed across all tasks and waves? Lower is better.

Formula: `score = max(0, 10 - (total_retries / task_count) * 5)`

- **10**: Zero retries.
- **8**: Fewer than 0.5 retries per task on average.
- **6**: 0.5–1.0 retries per task.
- **4**: 1–2 retries per task.
- **2**: 2–3 retries per task.
- **0**: More than 3 retries per task on average.

Evidence to cite: total retries, broken down by type (audit fix, codex gate retry, manual intervention).

---

## Dimension 5: Execution Smoothness (0–10)

Subjective but evidence-grounded assessment. Were there blockers, ambiguous plan steps, confusing errors, or required manual interventions?

- **10**: Fully autonomous from start to finish. No blockers, no ambiguity, no manual steps.
- **7–9**: Minor friction — one clarification needed, one unexpected error handled gracefully.
- **4–6**: Moderate friction — multiple ambiguities, one blocker that paused execution, one manual intervention.
- **1–3**: Significant friction — repeated blockers, unclear plan steps that caused wrong-direction work, multiple manual interventions.
- **0**: Execution could not proceed without constant human steering.

Evidence to cite: error log entries, any manual interventions recorded in PROGRESS.md, plan ambiguities encountered.

---

## Scoring Principles

### Evidence-first scoring

Every score needs a citation. "Tasks passed audit" is not a citation. "12/14 tasks passed audit on first attempt; Tasks 3 and 9 each needed one auto-fix cycle" is a citation. If the data to score a dimension is genuinely unavailable, note the gap explicitly and score conservatively (assume worst case for that dimension).

### No vibes

Do not write "the execution felt smooth" or "agents seemed efficient." Write "0 manual interventions were required and all errors were caught and auto-resolved by ftm-audit Phase 2." The report is read by future executions that need to calibrate behavior, not by humans looking for encouragement.
