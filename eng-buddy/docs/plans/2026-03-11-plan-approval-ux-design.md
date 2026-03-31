# Wave 3: Plan Approval UX — Design Document

**Date**: 2026-03-11
**Scope**: React dashboard inline plan view with per-step approval controls, execution dispatch, and edit learning

## Overview

Add plan approval UX to the React dashboard as an inline expansion within CardItem. Users review auto-generated plans, approve/skip/edit high-risk steps, and dispatch execution to a Warp terminal session while watching progress inline.

## Component Architecture

```
CardItem (existing, expanded)
└── PlanView
    ├── PlanHeader (confidence, plan status, "Execute" + "Approve All" buttons)
    ├── PhaseAccordion[] (one per phase, collapsible)
    │   └── StepRow[]
    │       ├── StepStatus (icon: auto-approved/pending/approved/edited/skipped/running/done/failed)
    │       ├── StepSummary (description + risk badge)
    │       ├── StepControls (approve/skip/edit — high-risk pending only)
    │       └── StepEditor (inline textarea + "Regenerate" button)
    │           └── LearningChip ("Learned: ..." indicator)
    └── PlanFooter (Execute button, progress bar)
```

**State management**: Extend Zustand store with `expandedPlanCards: Set<number>` and `editingStep: {cardId, stepIndex} | null`. React Query handles plan data keyed by card ID.

## Risk-Based Auto-Approval

Three risk tiers determine default approval behavior:

| Risk | Examples | Default State |
|------|----------|---------------|
| **Low** | Read-only: `jira_get_issue`, `search_emails`, `list_events` | Auto-approved |
| **Medium** | Create/draft: create Jira ticket, draft email, write comment | Auto-approved |
| **High** | External-facing: send email, post Slack, publish portal changes, browser automation on live systems | Pending — requires explicit approval |

Low and medium risk steps render as muted, checkmarked rows with no controls. High-risk steps show full approve/skip/edit controls.

## Approval & Edit Flow

### Step Lifecycle

```
[Auto-approved]  low/medium risk → checkmark, muted row, no interaction
[Pending]        high-risk → amber dot, full controls
  ├── "Approve" → green checkmark, controls hide
  ├── "Skip" → strikethrough, grayed out
  └── "Edit" → StepEditor opens inline
       ├── Textarea pre-filled with draft_content
       ├── User types refinement feedback (natural language)
       ├── "Regenerate" → PATCH /plan/steps/{step} with feedback
       ├── Spinner during regen, new content replaces old
       ├── Status → "edited", LearningChip fades in
       └── Still needs explicit "Approve" after regen
```

### Approve All

- PlanHeader button: "Approve All (N remaining)"
- Calls `POST /plan/approve-remaining`
- All pending high-risk steps flip to approved simultaneously

### Execute Gate

- Execute button disabled until zero pending steps remain
- Tooltip: "N steps still need approval"
- Activates when all steps are approved, edited+approved, or skipped
- Shows "Execute (N steps)" with count of non-skipped steps

## Learning From Edits

When a user edits a step and regenerates:

1. **LearningChip** appears inline below the step: "Learned: use #general not #engineering for announcements"
2. Chip visible for ~10 seconds, then collapses to a small icon (click to re-expand)
3. Learning persisted to the Learnings management area (existing LearningsView in dashboard)
4. Future plan generation incorporates learned preferences automatically

## Execution & Terminal Integration

### Trigger

User clicks "Execute" → `POST /plan/execute`:
1. Backend builds step prompt, writes to temp file
2. Launches Warp terminal via osascript with Claude Code temp session
3. Returns `{status: "dispatched", session_id}`

### Dual Output

**Inline progress** — SSE events stream step status:
```
event: plan_step_update
data: {"card_id": 42, "step_index": 3, "status": "completed", "output": "..."}

event: plan_complete
data: {"card_id": 42, "status": "completed", "steps_succeeded": 10, "steps_failed": 1}
```

- StepRow transitions: approved → spinner → completed/failed
- PlanFooter progress bar: "4/11 steps complete"
- PhaseAccordion headers update: "Phase 2 — 3/5 done"

**Warp terminal** — Full interactive Claude Code session:
- User can watch execution in real-time
- User can intervene/steer mid-execution
- Terminal is source of truth; dashboard is read-only mirror

### Post-Execution States

- All green → PlanHeader: "Completed" with timestamp
- Mixed → "Completed with errors", failed steps highlighted with retry button
- Failed steps individually retryable or full plan regenerable with feedback

## Styling

All within existing design system, no new dependencies or tokens.

- **PlanView**: `bg-surface`, left border accent (mint = ready, coral = needs attention)
- **PhaseAccordion**: Collapsible chevron, `font-mono` phase name, step count badge
- **StepRow**: status icon | summary | risk badge | controls
  - Auto-approved: opacity 0.7, no hover
  - Pending: full opacity, amber left border
  - Failed: coral background tint
- **Risk badges**: `Badge` component — no badge (low), mint (medium), coral (high)
- **StepEditor**: `bg-deep`, `font-mono`, fadeUp animation
- **LearningChip**: `accent-blue` pill, fadeUp → collapses to icon after 10s
- **Progress bar**: Thin mint bar in PlanFooter, animated width
- **Execute button**: `Button` mint variant (ready) / ghost variant (disabled)

**Animations**: PhaseAccordion height transition, StepRow icon crossfade (0.2s), StepEditor fadeUp, LearningChip fadeUp/fadeOut, progress bar smooth width (0.3s).

## Backend API (Already Exists)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/cards/{id}/plan` | Fetch plan |
| PATCH | `/api/cards/{id}/plan/steps/{step}` | Approve/edit step |
| POST | `/api/cards/{id}/plan/approve-remaining` | Bulk approve |
| POST | `/api/cards/{id}/plan/execute` | Dispatch to terminal |
| POST | `/api/cards/{id}/plan/regenerate` | Regenerate with feedback |

## Out of Scope

- Playbook browsing/management UI (separate feature)
- Plan creation UI (plans generated by backend/pollers)
- PlanStore implementation (backend task, not frontend)
