# Planning Engine Design

**Date**: 2026-03-10
**Status**: Approved
**Approach**: Standalone planner module with background worker, LLM planning via Claude CLI, and autonomous capability expansion

## Problem

eng-buddy's dashboard shows incoming cards from pollers, but the user must manually initiate and instruct every action. The planning engine closes this gap: when a card arrives, the planner automatically generates a step-by-step execution plan that the user audits and approves in the React dashboard.

## Design Decisions

- **Always-wait model**: Nothing executes without human approval
- **Step-by-step gating**: Each step individually approvable, editable, or skippable
- **Hybrid knowledge**: Playbooks for known patterns, LLM planning for novel cards
- **Phase grouping**: Steps grouped into logical phases (Setup, Execute, Communicate)
- **LLM via Claude CLI**: Subprocess call gets full MCP server access for free
- **Autonomous expansion**: Planner can discover, research, and install new tools when gaps are detected
- **Learning loop**: Successful LLM plans auto-save as draft playbooks

## Trigger Model

Three triggers, layered:

1. **On card creation (instant)**: Playbook matching runs immediately. If a playbook matches with confidence > 0.5, plan is generated from the playbook with no LLM call.
2. **Background queue (seconds)**: Novel cards that don't match a playbook are queued for LLM planning. Background worker processes them within 30 seconds.
3. **On demand**: Manual "Generate Plan" or "Re-plan" button for fallback or re-generation with feedback.

```
Card arrives →
  PlaybookManager.match_ticket() →
    Hit (confidence > 0.5)? → Instant plan from playbook
    Miss? → Queue for background LLM planning

User can also → "Re-plan" with optional feedback
```

## Data Models

### Plan

```python
@dataclass
class Plan:
    id: str                    # "plan-{card_id}-{timestamp}"
    card_id: int
    source: str                # "playbook" | "llm" | "hybrid"
    playbook_id: str | None    # if matched from playbook
    confidence: float          # 0.0-1.0
    phases: list[Phase]
    status: str                # "pending" | "approved" | "executing" | "completed" | "failed"
    created_at: str
    executed_at: str | None
```

### Phase

```python
@dataclass
class Phase:
    name: str                  # "Tooling Setup", "Setup", "Execute", "Communicate"
    steps: list[PlanStep]
```

### PlanStep

```python
@dataclass
class PlanStep:
    index: int                 # global index across all phases (1-based)
    summary: str               # "Create Jira ticket ITWORK2-XXXX"
    detail: str                # full description
    action_type: str           # "api" | "mcp" | "playwright"
    tool: str                  # exact MCP tool name from registry
    params: dict               # resolved parameters
    param_sources: dict        # where dynamic values come from
    draft_content: str | None  # editable text (email body, comment, etc.)
    risk: str                  # "low" | "medium" | "high"
    status: str                # "pending" | "approved" | "skipped" | "edited" | "executing" | "done" | "failed"
    output: str | None         # execution result
```

PlanStep is compatible with the existing PlaybookStep + ActionBinding format. Conversion between them is straightforward for the learning loop.

## Module Architecture

```
bin/planner/
├── __init__.py
├── models.py          # Plan, Phase, PlanStep dataclasses
├── planner.py         # Core logic: match → plan → store
├── prompter.py        # Builds Claude CLI prompts for LLM planning
├── worker.py          # Background loop: polls for unplanned cards
└── store.py           # Plan persistence (JSON files + SQLite index)
```

### planner.py — Core Flow

```
plan_card(card) →
  1. PlaybookManager.match_ticket(card.type, card.summary, card.source)
  2. If match with confidence > 0.5:
       → Convert playbook steps into Plan with phases
       → source = "playbook", confidence = match score
  3. If no match or confidence < 0.5:
       → prompter.build_planning_prompt(card, tool_registry, context)
       → Shell out to Claude CLI: `claude --print -p "$(cat prompt.txt)"`
       → Parse structured JSON response into Plan
       → source = "llm", confidence = LLM self-assessment
  4. If plan has __MISSING__ tool steps:
       → Run expansion agent (see Capability Expansion section)
       → Re-plan with proposed tools
  5. store.save_plan(plan)
  6. Broadcast SSE event: "plan_ready" with card_id
```

### prompter.py — LLM Planning Prompt

Prompt includes:
- Card context (summary, source, metadata, context_notes)
- Tool registry (available tools, capabilities, default params)
- Learned context from brain.py build_context_prompt() (rules, stakeholders, past decisions)
- 2-3 promoted playbooks as few-shot examples
- Output schema (Plan JSON format)
- Phase guidance ("group into Setup, Execute, Communicate")
- Missing tool instruction ("mark as __MISSING__ if no tool exists")

Prompt kept under 4K tokens by summarizing tools and limiting examples to 3 most-executed playbooks.

Feedback from rejected plans (via /regenerate) appended as: "Previous plan was rejected because: {feedback}"

### worker.py — Background Daemon

- LaunchAgent daemon, same pattern as existing pollers
- Polls inbox.db every 30 seconds for cards with status "pending" and no plan
- Calls plan_card() for each
- Simple file lock to avoid double-planning
- Logs to ~/.claude/eng-buddy/planner.log

### store.py — Persistence

- Plans stored as JSON: ~/.claude/eng-buddy/plans/{card_id}.json
- SQLite plans table added to inbox.db for indexing (card_id, status, source, created_at)
- On successful execution + approval, auto-saves as draft playbook via PlaybookManager.save_draft()

## Capability Expansion Agent

When the LLM planner identifies a step requiring a tool not in the registry, it marks the step with `"tool": "__MISSING__"` and a `missing_capability` descriptor.

### Expansion Flow

```
Planner first pass →
  Plan has __MISSING__ steps? →
    Yes → Spawn expansion agent (Claude CLI with web search)
      1. Search for MCP servers (npm, GitHub)
      2. Search for public APIs
      3. If neither exists, check if Playwright can reach the UI
      4. If custom script needed, draft it

      Output: expansion proposal with one of:
        a) "Install MCP server X" (npm package + config)
        b) "Use API directly" (endpoint + auth pattern)
        c) "Use Playwright" (URL + action sequence)
        d) "Write custom script" (script code + registration)

    → Planner second pass: re-plan with proposed tool
    → Expansion steps become Phase 0: "Tooling Setup"
```

### Phase 0: Tooling Setup

Appears at the top of the plan when expansion is needed:

```
Phase: Tooling Setup
  Step 1: Install okta-mcp-server        [API] [high]
          npm install -g @okta/mcp-server
          Add to Claude MCP config

  Step 2: Register in tool registry       [API] [low]
          Add okta entry to _registry.yml
          Create okta.defaults.yml

Phase: Setup (original plan continues)
  Step 3: Look up user in Okta            [MCP] [low]
  ...
```

### Safety Guardrails

- All expansion steps are risk: "high" — always requires explicit approval
- MCP server installs show exact npm package and config changes
- Custom scripts shown in full before execution
- Tool registry updates shown as diffs
- Expansion never auto-executes

### Persistence

- Approved expansion tools permanently added to registry
- Future cards needing the same tool skip Phase 0
- Custom scripts saved to ~/.claude/eng-buddy/bin/ and registered as local_scripts

## API Surface

### New Routes

**GET /api/cards/{card_id}/plan**
- Returns plan for a card, or 404 if not yet planned
- Response: `{ plan: Plan }` or `{ status: "planning" }` if worker is generating

**PATCH /api/cards/{card_id}/plan/steps/{index}**
- Update step status or content
- Body: `{ status: "approved" | "skipped", draft_content?: string }`
- If draft_content differs from original, step status becomes "edited"
- Response: `{ step: PlanStep }`

**POST /api/cards/{card_id}/plan/approve-remaining**
- Bulk approve all pending steps from given index onward
- Body: `{ from_index: number }` (defaults to 1)
- Response: `{ approved_count: number, plan: Plan }`

**POST /api/cards/{card_id}/plan/execute**
- Execute all approved/edited steps in order
- Builds Claude CLI prompt with step sequence
- Launches via osascript (same pattern as /api/playbooks/execute)
- Skipped steps omitted, edited draft_content replaces originals
- Response: `{ status: "dispatched", steps: number, skipped: number[] }`
- On completion: if plan.source == "llm", auto-save as draft playbook

**POST /api/cards/{card_id}/plan/regenerate**
- Force re-plan a card
- Body: `{ feedback?: string }`
- Deletes existing plan, queues for immediate re-planning
- Response: `{ status: "queued" }`

### New SSE Events

- `plan_ready` — `{ card_id: number }` — React fetches the plan
- `plan_step_updated` — `{ card_id: number, step_index: number, status: string }`

## Execution Model

### Step Execution

```
User approves steps →
  POST /api/cards/{card_id}/plan/execute →
    Build Claude CLI prompt with approved steps
    Phase 0 (Tooling Setup) runs first if present
    Each subsequent phase runs in order
    Skipped steps omitted
    Edited draft_content replaces originals

    Claude CLI subprocess executes with full MCP access →
      WebSocket streams output to React terminal →
        Per-step status updates via SSE
```

### Failure Handling

- Step fails → execution pauses at that step
- SSE broadcasts plan_step_updated with status "failed" and error output
- React shows error inline with: "Retry", "Skip", "Abort Plan"
- Retry re-runs just that step
- Skip marks it skipped and continues
- Abort stops everything

## Learning Loop

### Post-Execution

```
Plan completes (all steps done/skipped) →
  1. Record execution trace via WorkflowTracer
  2. If plan.source == "llm":
       → Auto-save as draft playbook via PlaybookManager.save_draft()
       → Extract trigger patterns from card metadata
       → SSE broadcasts "draft_playbook_created"
  3. If plan.source == "playbook":
       → Increment playbook execution count
       → If steps were edited, flag playbook for review
  4. If Phase 0 had expansion steps:
       → New tools already persisted in registry
       → Log expansion event
  5. brain.py capture_post_tool_learning() for each step
```

### Draft Playbook Creation

- PlanStep maps directly to PlaybookStep + ActionBinding
- Phases become metadata tags
- Trigger patterns inferred from card source, keywords, type
- Confidence starts at "low"
- Promotes to "medium" after 1 successful re-use
- Promotes to "high" after 3 cumulative successes

### Playbook Drift Detection

- If same step edited across 2+ executions of the same playbook, system flags it
- Dashboard notification: "Step 4 edited in 3 of 5 recent executions — update playbook?"

## Deferred

- Confidence-based auto-routing
- Parallel step execution within phases
- Multi-card plan deduplication (two cards about same thread)
- Plan templates (reusable plan skeletons without playbook rigidity)
