# Report Format — Verification Output Template

This is the exact format for all verification report files saved to `~/.claude/ftm-retros/`.

---

## File Naming

Save to: `~/.claude/ftm-retros/{plan-slug}-{YYYY-MM-DD}.md`

### Slug Generation

Take the plan title, lowercase it, replace spaces with hyphens, strip all non-alphanumeric characters except hyphens.

Examples:
- "FTM Ecosystem Expansion" -> `ftm-ecosystem-expansion`
- "Fix Auth Bug + Rate Limiting" -> `fix-auth-bug-rate-limiting`
- "v2.0 API Refactor" -> `v20-api-refactor`

---

## Report Template

```markdown
# Verify: {Plan Title}

**Date:** {YYYY-MM-DD}
**Plan:** {absolute path to plan file}
**Duration:** {total execution time}
**Verification Duration:** {time spent on verification + remediation}

## Plan Fulfillment

| Task | Status | Notes |
|------|--------|-------|
| 1. [title] | FULFILLED / PARTIAL / MISSING / DIVERGED | [details] |

**Fulfillment Rate: {N}/{total} tasks fully implemented**

## Verification Summary

| Check | Agent | Findings | Remediated | Remaining |
|-------|-------|----------|------------|-----------|
| Plan Fulfillment | fulfillment-checker | [N] gaps | [N] fixed | [N] remain |
| Documentation | doc-fidelity-checker | [N] issues | [N] fixed | [N] remain |
| Build & Compile | build-verifier | [N] errors | [N] fixed | [N] remain |
| Test Quality | test-auditor | [N] weak/missing | [N] strengthened | [N] remain |
| Wiring | wiring-checker | [N] orphaned | [N] wired | [N] remain |

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

### Documentation Fixes
- [what was stale/missing] -> [what was added/updated] ([commit hash])

### Test Improvements
- [feature] — added [N] tests covering: [failure modes] ([commit hash])

### Wiring Fixes
- [component/function] — [what was orphaned] -> [how it was connected] ([commit hash])

### Code Fixes
- [feature] — [what was missing/broken] -> [what was implemented/fixed] ([commit hash])

## Remaining Issues

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
Format: **N. {Title}** -- {Skill to change} -- {Change} -- {Expected impact}

## Pattern Analysis

{Only if past reports exist in ~/.claude/ftm-retros/}

### Recurring Issues
{Problems appearing in 2+ reports}

### Score Trends
{Compare scores across reports with actual numbers}

### Unaddressed Suggestions
{Format: **[ESCALATED]** {suggestion} -- first proposed in {slug-date}, appeared {N} times}
```

---

## Improvement Specificity Standard

"Improve test coverage" is not an improvement proposal. "Add boundary condition tests for the payment calculation module — specifically: test zero amount, negative amount, amount exceeding daily limit, and concurrent payment requests — because the current tests only check a single valid payment" is an improvement proposal. Every proposed improvement must be concrete enough that a future session could implement it from the description alone.

## Pattern Escalation Standard

Recurring issues that have appeared in 3+ reports without being addressed should be flagged with `[ESCALATED - 3+ occurrences]` and moved to the top of the Proposed Improvements list.
