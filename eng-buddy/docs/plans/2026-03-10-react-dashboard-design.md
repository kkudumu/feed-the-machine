# React Dashboard Migration Design

**Date**: 2026-03-10
**Status**: Approved
**Approach**: React-First — migrate frontend to React, then add planning layer

## Problem

eng-buddy has the capability to automate most of the user's job, but it's reactive — the user must initiate and instruct every action. The dashboard needs to become the approval surface for autonomous planning: cards arrive, eng-buddy generates step-by-step execution plans, the user audits and approves.

The current vanilla JS frontend cannot support the UX complexity required for step-by-step plan approval, inline draft editing, live Playwright views, and real-time execution feedback. A React migration is foundational infrastructure that everything else builds on.

## Design Decisions

- **Always-wait model**: Nothing executes without human approval. No auto-execution tiers.
- **Step-by-step gating**: Each plan step is individually approvable, editable, or skippable.
- **Hybrid knowledge**: Playbooks for known patterns, LLM planning for novel cards, system learns from approvals over time.
- **Predictable execution methods**: Card types map to known tool types (API, MCP, Playwright). Playbooks declare this upfront.

## Architecture

### Stack

- **Vite + React 18 + TypeScript**
- **Zustand** for UI-local state (sidebar filters, active card, expanded trays, theme)
- **TanStack Query** for server state (cards, plans, stats) with SSE-driven invalidation
- **CSS Modules + CSS custom properties** for theming (no CSS-in-JS runtime)
- **No component library** — hand-rolled components for the custom kawaii aesthetic

### Project Structure

```
dashboard/frontend/
├── src/
│   ├── api/            # API client, SSE hook, WebSocket hook
│   ├── components/     # Shared UI (Button, Card, Badge, ChibiMascot)
│   ├── features/
│   │   ├── inbox/      # Card list, filters, sidebar
│   │   ├── card-detail/# Single card view + action tray
│   │   ├── plan/       # Plan view, step approval
│   │   ├── terminal/   # WebSocket execution output
│   │   └── stats/      # Stats bar, metrics
│   ├── hooks/          # useSSE, useCards, useActions
│   ├── theme/          # CSS vars, kawaii tokens, glassmorphism mixins
│   └── App.tsx
├── vite.config.ts      # Proxy /api → localhost:7777
└── package.json
```

### Dev/Prod Strategy

- **Dev**: `vite dev` on `:5173`, proxies API to `:7777`
- **Prod**: `vite build` outputs to `dashboard/static/`, FastAPI serves it. Zero infra change.
- **Migration**: Both frontends coexist. FastAPI serves vanilla JS at `/` and React at `/app`. Once React covers all features, swap and remove vanilla JS.

## Data Flow

### Real-Time Updates

Single SSE connection at app root to `/api/events`. Events:
- `new_card` — invalidates card list query
- `card_updated` — invalidates specific card query
- `execution_started` / `execution_step` / `execution_complete` / `execution_failed` — updates execution state

No polling. TanStack Query caches handle all server state.

### Action Dispatch

```
User action (approve, edit, skip)
  → POST /api/cards/{id}/actions
    → Zustand optimistic UI update
      → Server response confirms/rejects
        → TanStack Query reconciles
```

### WebSocket (Execution Terminal)

- Opens only when viewing an active execution
- Streams stdout/stderr from Claude CLI subprocess
- Basic ANSI color rendering
- Disconnects on navigation away

### Error Resilience

- SSE auto-reconnects with exponential backoff
- TanStack Query retries failed fetches 3x
- Backend down → mascot goes sleepy, banner shows "waiting for eng-buddy backend..."

## Migration Sequence

### Wave 1: Card Inbox (core loop)

- Card list with real-time SSE updates
- Sidebar with source filters and counts
- Card detail view with progressive disclosure action tray
- Inline contenteditable drafts
- Stats bar (needs action, auto-resolved, draft accept rate, time saved)
- Chibi mascot with mood states

### Wave 2: Execution & Feedback

- WebSocket terminal for execution output
- Action dispatch (approve, deny, edit, refine)
- Toast notifications for action results
- Card status transitions (pending → approved → executing → done/failed)

After Wave 2, the React app fully replaces vanilla JS for daily use.

### Wave 3: Plan Approval UX

- Plan view component with ordered step list
- Per-step controls: approve, skip, edit, reorder
- Step type indicators (API/MCP/Playwright) with type-appropriate UX
- Playwright steps get screenshot preview and "watch live" toggle
- Draft content steps get inline editing
- "Approve All Remaining" bulk action

Built against mock data first, then wired to planner backend when it lands.

### Wave 4: Everything Else

- Playbook management tab
- Settings and preferences
- Theme switcher
- Audit log and approval history

## Design System

### Tokens

```css
--bg-deep: #1a1225
--bg-surface: #241832
--bg-glass: rgba(36, 24, 50, 0.7)
--accent-pink: #f4a8c8
--accent-mint: #90e3b2
--accent-blue: #9ac4ff
--accent-coral: #ff9b87
--text-primary: #f0e6ff
--text-muted: #8b7a9e
--radius-card: 16px
--radius-button: 10px
--glow-pink: 0 0 20px rgba(244, 168, 200, 0.3)
--glow-mint: 0 0 20px rgba(144, 227, 178, 0.3)
```

### Visual Language

- **Cards**: Glassmorphism (`backdrop-filter: blur(12px)`) with 1px glowing border color-coded by source (pink=Gmail, mint=Slack, blue=Jira, coral=Freshservice)
- **Buttons**: Solid fill primary (`accent-pink`), ghost secondary, `scale(0.96)` press
- **Step chips**: Muted outline (pending), mint fill (approved), strikethrough (skipped), yellow border (edited)
- **Typography**: Nunito 600 headings, Nunito 400 body, JetBrains Mono for code/data

### Chibi Mascot States

- **Happy** (`^ω^`): Inbox clear or action succeeded
- **Thinking** (`•ω•`): Loading or planning, tilted head with thought bubble
- **Sleepy** (`−ω−`): Many pending cards or backend down
- **Excited** (`✧ω✧`): Plan fully approved, about to execute, bouncing with sparkles

### Animations (CSS-only)

- Card entrance: fade-up with stagger `animation-delay: calc(var(--index) * 50ms)`
- Step approval: checkbox mint fill with scale bounce
- Background particles: `✿ ⋆ ♡ ✧` drifting at low opacity
- Section expand/collapse: `grid-template-rows: 0fr → 1fr`

## Plan Approval Data Model

```typescript
interface Plan {
  card_id: string
  confidence: number
  source: "playbook" | "llm" | "hybrid"
  steps: Step[]
}

interface Step {
  index: number
  summary: string
  detail: string
  action_type: "api" | "mcp" | "playwright"
  tool: string
  draft_content?: string
  inputs: Record<string, unknown>
  risk: "low" | "medium" | "high"
  status: "pending" | "approved" | "skipped" | "edited" | "executing" | "done" | "failed"
}
```

### Plan API Surface (for planner backend to implement)

- `GET /api/cards/{id}/plan` — get the generated plan for a card
- `PATCH /api/cards/{id}/plan/steps/{n}` — approve, skip, or edit a step
- `POST /api/cards/{id}/plan/approve-remaining` — bulk approve from step N onward
- `POST /api/cards/{id}/plan/execute` — start execution of approved steps

### Interaction Model

- Steps ordered top-to-bottom, approved via checkbox
- Draft content shown inline, `[edit]` toggles contenteditable
- Execution starts for consecutive approved steps, pauses at first unapproved
- Failed step pauses execution, shows error + output, allows retry or skip
- Playwright steps show thumbnail screenshots, exftmble to full view

## Deferred

- Planning engine backend (post-React migration)
- Auto-execution / autonomy tiers
- Confidence thresholds for auto-routing
- Per-playbook autonomy configuration
