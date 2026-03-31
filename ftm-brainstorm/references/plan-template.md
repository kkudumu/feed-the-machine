# Plan Generation Template

Load this file only when the user approves moving to Phase 3 (plan generation).

## Pre-Plan Sequence

Before generating ANY plan content:
1. **Spec Self-Review** module must have run (check for placeholders, contradictions, gaps)
2. **Pre-Mortem Stress Test** module must have run (top failures identified, mitigations selected)
3. Summary approved by user

## Present Incrementally

Do NOT dump the entire plan in one message. Present section by section:

1. **Vision + Architecture Decisions + Risk Mitigations** — ask: "Does this foundation look right?"
2. **Task Breakdown with Discovery Levels** — ask: "Any tasks missing, or should any be split/merged?"
3. **Agent Team + Execution Order + Validation Strategy** — ask: "Good to save it?"

Only save after all three sections are approved.

## Plan Document Structure

```markdown
# [Project/Feature Name] — Implementation Plan

## Vision
[2-3 sentence summary of what we're building and why, grounded in research findings]

## Key Research Findings
- [Most important patterns/decisions discovered, with source links]
- [Each finding that materially influenced the plan]

## Architecture Decisions
[Major technical choices and the reasoning behind each — reference the research turn where evidence was found]

## Canonical References
[MANDATORY section — links to specs, docs, ADRs, or external resources that implementing agents MUST read]
- [Link 1]: [what it is and why it matters]
- [Link 2]: [what it is and why it matters]

## Risk Mitigations (from Pre-Mortem)
[Selected mitigations that become explicit tasks or acceptance criteria]
- Risk: [failure scenario] → Mitigation: [what we're doing about it] → Task: [which task handles it]

## Deferred Ideas (Future Work)
[Ideas raised during brainstorm that were deferred to keep v1 scope tight]
- [Idea 1]: [brief description, why deferred]
- [Idea 2]: [brief description, why deferred]

## Tasks

### Task N: [Title]
**Description:** [What needs to be built — explicit enough that an agent with zero context can execute]
**Discovery Level:** [L0 skip | L1 quick verify | L2 standard | L3 deep dive]
**Files:** [Expected files to create/modify — use ACTUAL project paths from Phase 0]
**Dependencies:** [Which tasks must complete first, or "none"]
**Agent type:** [frontend-developer, backend-architect, etc.]
**Acceptance criteria:**
- [ ] [Specific, testable criterion]
- [ ] [Another criterion]
**Verify command:** [Automated command that proves this task is done — Nyquist rule: every task MUST have one]
**Hints:**
- [Relevant research finding with source URL]
- [Known pitfall from research: "Watch out for Z — see [link]"]
- [If brain dump: novelty verdict — "Already solved by [tool]" or "Novel — no prior art"]
- [Pre-mortem mitigation if applicable]
**Wiring:**
  exports:
    - symbol: [ExportedName]
      from: [file path]
  imported_by:
    - file: [parent file that should import this]
  rendered_in:
    - parent: [ParentComponent]
      placement: "[where in parent JSX]"
  route_path: [/path]
  nav_link:
    - location: [sidebar|navbar|menu]
      label: "[Display text]"

## Agent Team
| Agent | Role | Tasks |
|-------|------|-------|
| [type] | [what they handle] | [task numbers] |

## Execution Order
- **Wave 1 (parallel):** Tasks [X, Y, Z] — no dependencies
- **Wave 2 (parallel, after wave 1):** Tasks [A, B] — depend on wave 1
- **Wave 3:** Task [C] — integration/final assembly

## Validation Strategy
[How we verify the whole thing works end-to-end after all waves complete]
- Smoke test: [command or manual step]
- Integration test: [what to check]
- User acceptance: [what the user should see/experience]
```

## Wiring Contract Rules

Auto-populate the `Wiring:` block based on file type:

- **New component** (.tsx/.vue/.svelte): exports (component name), imported_by (parent), rendered_in (where in JSX), route_path (if page)
- **New hook** (use*.ts): exports (function), imported_by (consuming components)
- **New API function** (api/*.ts): exports (functions), imported_by (hooks/components calling them)
- **New store/state**: store_reads (which components read), store_writes (which write)
- **New route/view**: route_path, nav_link (where navigation appears), rendered_in (router config)
- **New CLI command**: entry_point, subcommand_tree, config_reads, output_format
- **New middleware**: intercepts (which routes), order (before/after what), passes_to (next handler)

## Hints Population

For each task, pull from the cumulative research register:

1. **Web Researcher findings** — blog posts, case studies, patterns (include URL)
2. **GitHub Explorer findings** — repos that solved similar problems (include URL + what's useful)
3. **Competitive Analyst findings** — products to learn from or differentiate against
4. **Stack Researcher findings** — library versions, compatibility notes, configuration patterns
5. **Architecture Researcher findings** — structural patterns, scaling considerations
6. **Pitfall Researcher findings** — warnings, anti-patterns, known failure modes
7. **UX/Domain Researcher findings** — UX patterns, accessibility requirements, domain conventions
8. **Brain dump novelty map** (Path B): solved/partially solved/novel verdicts
9. **Pre-mortem mitigations** — selected risk mitigations that apply to this task
10. **Assumption audit results** — crackable assumptions that affect this task

Rules:
- Always include source links
- 2-4 bullets per task, not paragraphs
- "No specific research findings for this task" if nothing applies
- Hints are suggestions, not mandates

## Discovery Level Guidelines

Assess each task's discovery level based on:

- **Level 0 (Skip):** Pure internal work using existing patterns. No research needed. Example: "Add a new route following the existing pattern in routes.ts"
- **Level 1 (Quick Verify, 2-5 min):** Single known library, confirm syntax. Example: "Use date-fns for date formatting — confirm API for relative dates"
- **Level 2 (Standard, 15-30 min):** Choosing between options, new integration. Example: "Integrate Stripe checkout — research current best practice for SCA compliance"
- **Level 3 (Deep Dive, 1+ hour):** Architectural decisions, novel problems. Example: "Design real-time sync protocol — research CRDT vs OT for collaborative editing"

Tag each task with its level. Level 2+ tasks get extra research hints from the brainstorm's findings. Level 3 tasks should reference the specific research turn where the approach was decided.

## Verify Command Rules (Nyquist Validation)

**Source:** GSD Nyquist rule

Every task MUST have a `Verify command` that can be run automatically. No exceptions.

Good verify commands:
- `npm test -- --testPathPattern=feature-name`
- `curl -s http://localhost:3000/api/endpoint | jq .status`
- `npx tsc --noEmit`
- `grep -r "ExportedName" src/ | wc -l` (verify wiring)

Bad verify commands:
- "Check that it looks right" (not automated)
- "Run the app and verify" (too vague)
- "Manual testing required" (violates Nyquist)

If a task genuinely can't have an automated verify (pure visual design), note: `Verify: MANUAL — [specific thing to check visually]` and explain why automated isn't possible.

## Quality Rules

- Tasks small enough for one agent session (if a task description exceeds 200 words, split it)
- Every task has testable acceptance criteria
- Every task has an automated verify command (Nyquist rule)
- Dependencies explicit — no implicit ordering
- Agent assignments match domain
- Wave structure maximizes parallelism
- File paths reference ACTUAL project structure from Phase 0
- Leverage existing project patterns (don't reinvent)
- Risk mitigations from pre-mortem are embedded as tasks or acceptance criteria
- Canonical references section is populated
- Deferred ideas section captures scope that was cut
- Discovery levels are assigned and realistic
- No placeholders — every instruction is concrete enough for a zero-context agent

## Plan Quality Verification

After generating the plan, run the Plan Checker agent (see SKILL.md Phase 3).

The checker validates:
1. **Spec coverage** — every brainstorm decision appears in a task
2. **Placeholder scan** — no TBDs, TODOs, or vague instructions
3. **Task decomposition** — every task fits one agent session
4. **Buildability** — dependency order is correct
5. **Nyquist validation** — every task has automated verify
6. **Wiring completeness** — no orphaned exports/imports
7. **YAGNI** — no tasks that aren't traceable to brainstorm decisions

Fix checker issues inline. Up to 3 iterations. Present remaining issues to user.

## Save Location

```
~/.claude/plans/[project-name]-plan.md
```

Create `~/.claude/plans/` if needed.

## Handoff Prompt

After saving, give the user:

```
/ftm-executor ~/.claude/plans/[project-name]-plan.md
```

Plus a summary: "[N] tasks across [M] agents in [W] waves. First wave starts immediately with [list]. Discovery: [X] L0, [Y] L1, [Z] L2, [W] L3 tasks. Top risk mitigated: [brief]. Scope: [small/medium/large]."
