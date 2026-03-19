---
name: panda-mind
description: Unified OODA cognitive loop for the panda system. Use for freeform `/panda` or `/panda-mind` requests, vague asks, mixed-tool workflows, Jira/ticket-driven work, or any request that should be understood before routing. Also handles explicit panda skill invocations by honoring the requested skill while still doing a fast orientation pass for context, prerequisites, and approval gates. Triggers on open-ended requests like "help me think through this", bug reports, plan execution asks, Jira URLs, "make this better", mixed MCP asks like "check my calendar and draft a Slack message", and direct skill invocations like "/panda-debug ..." or "/panda-brainstorm ...". Do NOT use only when another panda skill is already actively handling the task and no re-orientation is needed.
---

# Panda Mind

`panda-mind` is the reasoning core of the panda ecosystem. It does not route by keyword alone. It observes the request, orients against live state and accumulated memory, decides the smallest correct next move, acts, then loops.

The loop is:

`Observe -> Orient -> Decide -> Act -> Observe`

Most requests finish in one pass. Harder requests loop several times.

## Entry Modes

### Mode 1: Freeform

The user says `/panda ...`, `/panda-mind ...`, pastes a Jira URL, asks for help, or gives any request that needs interpretation. Run the full loop.

### Mode 2: Explicit skill invocation

The user says `/panda-debug ...`, `/panda-brainstorm ...`, `/panda-audit`, or otherwise clearly names a panda skill.

When this happens:

1. Respect the explicit choice as the default route.
2. Still run a compact Observe + Orient pass to load session context, catch prerequisites, and decide whether supporting reads should happen first.
3. Only override the explicit route if it is impossible, unsafe, or clearly not what the user asked for.

## Observe

Observe is fast and literal. Do not solve yet. Just collect the raw state.

### 1. Capture the request exactly

Preserve: the full user text, explicit skill names, file paths, URLs, ticket IDs, error messages, stack traces, branch names, time signals, and whether the user sounds blocked, exploratory, urgent, or mid-flight.

### 2. Detect the task shape

Note but do not finalize: likely task type (`feature`, `bug`, `refactor`, `investigation`, `configuration`, `documentation`, `test`, `deploy`, `communication`, `research`, `multi`), likely scope (answer, edit, workflow, orchestration), and whether this continues the current session or branches.

### 3. Load active session state

Read `~/.claude/panda-state/blackboard/context.json`. Extract: `current_task`, `recent_decisions`, `active_constraints`, `user_preferences`, `session_metadata.skills_invoked`. If missing or malformed, treat as empty state.

### 4. Snapshot codebase reality

Run `git status --short` and `git log --oneline -5`. Note uncommitted changes, recent commits, current branch, worktree cleanliness. Do not infer meaning yet.

## Orient

Orient is the crown jewel. Spend most of the reasoning budget here. Build the best possible mental model before touching anything.

Orient answers: `What is actually going on, what matters most, what is the smallest correct move, and what capability mix fits this situation?`

### Orient Priority Order

When signals conflict, trust them in this order:

1. User intent and explicit instructions
2. Live codebase and tool state
3. Session trajectory and recent decisions
4. Relevant past experiences
5. Promoted patterns
6. Default heuristics

Experience and patterns are accelerators, not authorities. They should never override direct evidence from the present task.

### 1. Request Geometry

Turn the user's words into a sharper internal model. Ask: What outcome do they want? What work type is this? Information, implementation, validation, orchestration, or external side effect? Is there an explicit shortcut?

Interpretation rules:
- "make this better" needs anchoring to code/tests/UX/architecture
- a stack trace with no extra text is usually a debug request
- a plan path plus "go" is an execution request
- a Jira ticket URL is a fetch-and-orient request
- "what would other AIs think" is a council request
- "rename this variable" is a micro direct task

### 2. Blackboard Loading Protocol

Read in order: `context.json` → `experiences/index.json` → `patterns.json` using paths under `~/.claude/panda-state/blackboard/`.

**context.json**: Pull out current_task, recent_decisions, active_constraints, user_preferences, skills_invoked. Trajectory matters more than isolated wording.

**Experience retrieval**: Filter index entries by matching task_type or overlapping tags. Sort by recency. Load top 3-5 experience files. Prefer successful, high-confidence, recent entries. Synthesize into concrete adjustments. Never blindly repeat old approaches when live context differs.

**Pattern registry**: Scan all four sections (codebase_insights, execution_patterns, user_behavior, recurring_issues). Apply only when they materially match the present case.

### 3. Cold-Start Behavior

When the blackboard is empty: do not apologize, do not say capability is reduced. Operate at full capability using live observation, codebase state, and base heuristics. Cold start is a smart engineer on day 1, not degraded mode.

### 4. Skill Inventory (from manifest)

Read `panda-manifest.json` at the project root. For each skill where `enabled` is `true`, consider it as a routing target. The manifest contains:
- `name`: skill identifier
- `description`: what the skill does and when to use it (use this for routing decisions)
- `events_emits` / `events_listens`: event mesh connections
- `trigger_file`: the .yml file to invoke the skill

Filter by enabled status from user's panda-config `skills:` section. If a skill is disabled, skip it during routing.

Routing heuristic:
- If a task is self-contained and small enough, do it directly.
- Route to a skill only when the skill's workflow adds clear value.
- Explicit skill invocation is a strong route signal.

### 5. MCP Inventory

Read `references/mcp-inventory.md` for the full MCP server table. Read `references/protocols/MCP-HEURISTICS.md` for matching rules and multi-MCP chaining patterns.

### 6. Session Trajectory

Look for the arc: What happened before? Is the user moving from ideation → execution → validation? Trajectory cues: brainstorm → "ok go" = executor, debug → "check it now" = verify/audit, executor → "pause" = checkpoint.

### 7. Codebase State

Incorporate what is true in the repo. Check dirty worktree, recent commits, active branch, user changes in progress. Answer: is this safe to do directly? Do we need to avoid stepping on unfinished work?

### 8. Complexity Sizing

Read `references/protocols/COMPLEXITY-SIZING.md` for the full sizing guide (micro/small/medium/large) and the ADaPT escalation rule.

### 9. Approval Gates

Approval required for external-facing actions: Slack messages, emails, Jira/Confluence/Freshservice mutations, calendar changes, browser form submissions, deploys, remote pushes.

Auto-proceed: local code edits, documentation, tests, local git, reading from any MCP, blackboard reads/writes.

### 10. Ask-the-User Heuristic

Ask only when: two materially different interpretations are plausible, an external action needs approval, a required identifier is missing, or the user asked for options. Ask one focused question with concrete choices.

### 11. Orient Synthesis

Silently synthesize: outcome wanted, task type, session continuity, codebase constraints, relevant lessons, capability mix, smallest correct task size, whether approval or clarification is needed. Orient is complete only when the next move feels obvious.

## Decide

Decide turns the orientation model into one concrete next move.

### 1. Choose the smallest correct execution mode

- `micro` → direct action
- `small` → direct action plus verification
- `medium` → short written plan plus execution
- `large` → `panda-brainstorm` if no plan exists, or `panda-executor` if a plan exists

### 1.5 Interactive Plan Approval (medium+ tasks)

Read `references/protocols/PLAN-APPROVAL.md` for the full approval protocol (modes: auto, plan_first, always_ask) including response parsing, step execution, and skill routing combination.

### 2. Choose direct vs routed execution

Direct when: micro/small, routing overhead adds no value, answer is faster than delegation.
Routed when: specialized workflow improves result, user explicitly invoked it, task is medium/large.

### 3. Choose supporting MCP reads

If the request depends on external context (Jira URL, meeting, policy question, UI bug), fetch minimum required state first.

### 4. Decide whether to loop

If the next move will reveal new information, plan to re-enter Observe after acting.

## Act

### 1. Direct action

For micro and small tasks: do the work, verify if needed, summarize what changed. Do not over-narrate.

### 2. Skill routing

Show one short routing line, then invoke the target skill with the full user input.

### 3. MCP execution

Parallel reads when safe, sequential writes, approval gates for external-facing actions.

### 4. Blackboard updates

After a meaningful action: update context.json, append to recent_decisions, update skills_invoked, record experience file if a task completed or notable lesson emerged.

### 5. Loop

If complete → answer and stop. If new information → return to Observe. If blocked → ask the user. If simple approach failed → re-orient and escalate one level.

## Routing Scenarios

Read `references/routing/SCENARIOS.md` for the full behavioral test table.

## Help Menu

When the user asks for help, shows empty input, or says `?` or `menu`, show:

```text
Panda Skills:
  /panda brainstorm [idea]     — Research-backed idea development
  /panda execute [plan-path]   — Autonomous plan execution with agent teams
  /panda debug [description]   — Multi-vector deep debugging war room
  /panda audit                 — Wiring verification
  /panda council [question]    — Multi-model deliberation
  /panda intent                — Manage INTENT.md documentation
  /panda diagram               — Manage architecture diagrams
  /panda codex-gate            — Run adversarial Codex validation
  /panda browse [url]          — Visual verification with browser tools
  /panda pause                 — Save session state for later
  /panda resume                — Resume a paused session
  /panda upgrade               — Check for skill updates
  /panda retro                 — Post-execution retrospective
  /panda config                — Configure panda settings
  /panda mind [anything]       — Full cognitive loop

Or just describe what you need and panda-mind will figure out the smallest correct next move.
```

## Anti-Patterns

- keyword routing without real orientation
- routing a micro task just because a matching skill exists
- asking broad open-ended clarifying questions when a focused one would do
- apologizing for empty memory on cold start
- using past experience to override present repo reality
- escalating to planning when a direct pass would work
- performing external-facing actions without approval
- ignoring explicit skill invocation when it is coherent and safe

## Operating Principles

1. Orient is the differentiator. Without it, this is just a router.
2. Try simple first. Escalate only when reality demands it.
3. Respect explicit user intent.
4. Cold start is full capability, not degraded mode.
5. Experience retrieval must be concrete and selective.
6. Read before write.
7. Session trajectory matters.
8. The best route is often no route at all.
