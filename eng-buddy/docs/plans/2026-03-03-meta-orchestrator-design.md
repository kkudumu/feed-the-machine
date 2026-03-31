# eng-buddy v2: Meta-Orchestrator Design
**Date**: 2026-03-03
**Status**: Approved
**Author**: Kioja Kudumu

---

## Problem Statement

eng-buddy is already smart. The failure mode is input friction. Everything useful requires manually copying and pasting Slack messages, tickets, emails, and meeting notes into a Claude Code session. By the time that happens, the context switch has already cost you.

**Goal**: Zero copy-paste. Everything that hits you in a day is automatically captured, classified, and presented for a reaction — not a conversation.

---

## Core Design Principle

> eng-buddy v2 is a **capture-first, react-second** system. You don't feed it information. It captures everything and surfaces what needs your attention. You approve, deny, or edit. Everything else is automatic.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    INGESTOR LAYER                        │
│  slack-poller  │  gmail-poller  │  fs-watcher  │  jira  │
│  (exists)      │  (exists)      │  (new)       │  (new) │
│                                                          │
│  freshservice-poller │ calendar-watcher │ screen-monitor │
│  (new)               │ (new)            │ (new)          │
│                                          ↓               │
│                                    transcribe            │
│                                    (vivekuppal/transcribe)│
└────────────────────────────┬────────────────────────────┘
                             │ all sources → events.db (SQLite)
┌────────────────────────────▼────────────────────────────┐
│                   ORCHESTRATOR DAEMON                    │
│                                                          │
│  • Polls events.db for new events                       │
│  • Classifies: urgent / needs-response / FYI / pattern  │
│  • Routes to correct LLM (see routing table below)      │
│  • Injects eng-buddy SKILL.md + memory files as context │
│  • Manages context rotation (default: 45 min)           │
│  • Auto-git-commit before destructive actions           │
│  • Self-healing: monitors subprocesses, restarts on fail│
│  • Detects stuck loops (10+ turns same task → Gemini)   │
└────────────────────────────┬────────────────────────────┘
                             │ cards → inbox.db (SQLite)
┌────────────────────────────▼────────────────────────────┐
│                  FASTAPI + WEB DASHBOARD                 │
│                                                          │
│  Inbox:    cards (Slack/email/ticket/alert)              │
│            [✓ Approve & Execute] [✗ Deny] [✎ Edit]      │
│  Activity: everything actioned today                     │
│  Agents:   active CLI processes, LLM, task, tokens      │
│  Memory:   today's eng-buddy log (live)                 │
│  Patterns: recurring issues, time sinks, skill gaps     │
└────────────────────────────┬────────────────────────────┘
                             │ decisions + actions
┌────────────────────────────▼────────────────────────────┐
│              SHARED MEMORY (exists, unchanged)           │
│  ~/.claude/eng-buddy/  — markdown files                  │
│  Claude Code sessions read the same files.              │
│  Orchestrator writes the same files.                    │
│  No sync layer. The filesystem is the integration.      │
└─────────────────────────────────────────────────────────┘
```

---

## Multi-LLM Routing

| LLM | When | Why |
|-----|------|-----|
| **Claude CLI** | Everything — drafts, responses, triage, code generation, analysis | Consistent eng-buddy voice; MCP access via `~/.claude.json` |
| **Codex CLI** | Code critic after every Claude codegen | Harsh enforcer: no stubs, no incomplete functions, matches overall plan, actually works |
| **Gemini CLI** | Tiebreaker when orchestrator detects 10+ turns on same bug unresolved | 1M context window; fresh perspective; different training, different blind spots |

**Claude is primary. Always.**

### Invocation pattern (all Claude calls)
```bash
claude --dangerously-skip-permissions -p "
$(cat ~/.claude/skills/eng-buddy/SKILL.md)

Current context:
$(cat ~/.claude/eng-buddy/daily/YYYY-MM-DD.md)
$(cat ~/.claude/eng-buddy/tasks/active-tasks.md)

Task: [specific task]
"
```

eng-buddy voice is injected every time. Consistent personality across all agent invocations.

### Code generation flow
```
Claude writes code (full implementation)
      ↓
Codex reviews: stubs? incomplete functions? breaks project structure? untested?
      ↓
Codex patches — not just flags, actually fixes
      ↓
Dashboard card: "Claude wrote X lines · Codex made Y fixes · [details]"
      ↓
[✓ Approve & Write]  [✗ Deny]  [↗ Open in editor]
```

### Stuck loop detection
```
Orchestrator tracks turns per task ID / bug reference
If same task appears in 10+ turns with no resolution signal:
  → Dump full context (all turns + memory + relevant files) to Gemini
  → Gemini response surfaces as card: "Fresh take — here's what you're missing"
  → Back to Claude to implement if suggestion looks right
```

---

## Components

### 1. Ingestor Layer

Each daemon is independent. Crashes in one don't affect others.

| Daemon | Status | Captures |
|--------|--------|----------|
| `slack-poller.py` | Exists (launchd) | DMs, mentions, channel messages |
| `gmail-poller.py` | Exists (launchd) | Inbox, watched threads |
| `freshservice-poller.py` | New | New tickets, replies, SLA breaches, assignments |
| `jira-poller.py` | New | Assigned issues, comments, transitions, mentions |
| `calendar-watcher.py` | New | Upcoming meetings → triggers transcribe |
| `fs-watcher.py` | New | `~/.claude/eng-buddy/` changes → detects Claude Code session writes |
| `screen-monitor.py` | New | Screenshots every N min while active → activity analysis |
| `transcribe` | Integrate | Auto-starts on meeting detection, transcript → events.db on completion |

All write to `events.db`. Schema: `(id, source, timestamp, raw_content, metadata, processed)`.

### 2. Orchestrator Daemon

The brain. Single Python process. Polls `events.db` every N seconds.

**Classification labels:**
- `urgent` → macOS notification fires immediately
- `needs-response` → card queued in inbox
- `FYI` → written to daily log, no card
- `automatable` → flagged for automation pipeline
- `pattern` → written to `patterns/` files

**Context rotation:**
- Every 45 minutes (configurable): write session summary to `sessions/`, kill agent, restart fresh with summary injected
- Prevents context bloat without losing continuity
- Same mechanism as existing `eng-buddy-pre-compaction.sh` hook, but orchestrator-managed

**Auto-commit protocol:**
- Before spawning any agent for a destructive task (file writes, API mutations, ticket changes):
  ```bash
  git -C ~/.claude/eng-buddy add -A && git commit -m "pre-action snapshot: [task description]"
  ```
- Not optional. Not configurable. Always.

**Self-healing:**
- Orchestrator runs its own subprocess monitor
- Any daemon or agent crash → logged to `incidents/` → restarted with last known state
- Surfaces repeated crashes as patterns (something is wrong, not just a fluke)

### 3. Action Execution Layer

```
[✓ Approve] tapped on dashboard card
      ↓
FastAPI endpoint receives approval
      ↓
Orchestrator reads proposed_actions[] from inbox.db
      ↓
For each action:
  • MCP-dependent (Freshservice reply, Jira update, Slack message)
    → spawn claude CLI with MCPs loaded from ~/.claude.json
  • Code write → spawn claude, then codex critic, then write on approval
  • Analysis only → no execution, just memory write
      ↓
On completion:
  • Card marked done in inbox.db
  • Action written to daily log automatically
  • Ticket closed / reply sent / group added
  • Outcome stored in action-log.md (learning dataset)
```

**MCP inheritance**: Claude CLI reads `~/.claude.json` automatically. All existing MCPs (Freshservice, Jira, Atlassian, Slack, Gmail, Google Calendar) available to every agent invocation. No re-integration required. New MCPs added to Claude Code are available to orchestrator automatically.

### 4. Web Dashboard

**Stack**: FastAPI (Python, consistent with existing pollers) + HTMX or minimal React frontend. No heavy build pipeline.

**Views:**

- **Inbox** — cards sorted by urgency. Each card: source icon, one-line summary, AI draft, `[✓ Approve]` `[✗ Deny]` `[✎ Edit]`. Queue persists until actioned.
- **Activity feed** — everything that came in today, actioned items, what agents did
- **Agents panel** — active CLI processes, which LLM, current task, approximate token usage
- **Memory panel** — today's `daily/YYYY-MM-DD.md` rendered live (file-watch via watchdog)
- **Patterns panel** — pulled live from `patterns/` files

**Interruption model:**
- Urgent events (keywords: blocked, critical, deadline, ASAP, escalation, down) → macOS notification via `osascript` immediately
- Everything else → silent queue. You check when you come up for air.
- Notification includes: source, one-line summary, quick-action buttons (approve/deny without opening browser)

### 5. Shared Memory

No structural changes to existing `~/.claude/eng-buddy/`.

```
~/.claude/eng-buddy/
├── daily/YYYY-MM-DD.md        ← orchestrator writes here automatically
├── tasks/active-tasks.md      ← orchestrator syncs task state
├── patterns/                  ← agents update as patterns emerge
├── capacity/                  ← screen monitor feeds time data here
├── incidents/                 ← self-healing logs crashes here
├── action-log.md              ← NEW: every approved action logged (audit + learning)
├── events.db                  ← NEW: SQLite event queue (all ingestors write here)
├── inbox.db                   ← NEW: SQLite inbox + card state
└── docs/plans/                ← NEW: design docs
```

Claude Code sessions (your existing `/eng-buddy` skill) read the same files. When you open a Claude Code session, it sees everything the orchestrator wrote. Zero sync required.

---

## Learning Loop

### Signal capture (automatic, no copy-paste)

| Signal | How captured | Written to |
|--------|-------------|-----------|
| Approve/deny/edit decisions | Dashboard interactions | `action-log.md` |
| Edit diffs (what you changed in drafts) | Dashboard captures before/after | Voice model training data |
| Time per task type | Screen monitor + action log | `capacity/time-estimates.md` |
| Meeting outcomes | Transcribe → orchestrator summary | `daily/` + `knowledge/` |
| Recurring tickets/questions | Ingestors + pattern classifier | `patterns/recurring-questions.md` |
| Code that needed Codex fixes | Codex critic output | `patterns/` + `knowledge/solutions.md` |
| Stuck loops (10+ turns) | Orchestrator loop detector | `patterns/recurring-issues.md` |

### Skill gap detection

```
Screen monitor sees: 45 min on same Freshservice ticket
→ "You've spent 45 min here. Similar tickets avg 8 min.
   Root cause: manual Okta step you haven't scripted yet."

Action log sees: you edit 80% of Codex's error handling
→ "You consistently rewrite Codex error handling.
   Update critic prompt to match your style? [✓ Yes] [✗ No]"

Pattern files see: SSO setup is ticket #4 this month
→ "SSO wizard would have saved 18 hours this month.
   Ready to build it? [✓ Start] [→ Backlog]"
```

### Voice model refinement

- Every edit to a Claude draft is captured as a diff
- Orchestrator accumulates diffs → periodically updates voice instructions in SKILL.md prompt template
- Drafts get closer to your natural voice over time
- You can also explicitly deny a draft style → orchestrator logs the rejection pattern

### Self-healing intelligence

- Repeated daemon crashes → flagged as incident pattern, not just restarts
- Consistently denied draft types → prompt pattern flagged for review
- Gemini tiebreakers that resolved stuck loops → stored as successful debugging patterns
- System surfaces its own failure modes rather than silently degrading

---

## Build Order

Phase 1 — Zero copy-paste core (highest immediate value):
1. Unified `events.db` schema + orchestrator skeleton
2. Wire existing slack + gmail pollers to events.db (they already run)
3. Freshservice poller (new)
4. Jira poller (new)
5. Basic dashboard: inbox view + approve/deny
6. Action execution via Claude CLI with MCP inheritance

Phase 2 — Code pipeline:
7. Claude codegen + Codex critic workflow
8. Auto-commit before destructive actions
9. Stuck loop detector → Gemini tiebreaker

Phase 3 — Environmental capture:
10. Calendar watcher + transcribe integration
11. Screen monitor daemon
12. Activity analysis → skill gap surfacing

Phase 4 — Learning loop:
13. Edit diff capture + voice model refinement
14. Pattern auto-write (remove remaining manual logging)
15. Self-healing intelligence layer

---

## Key Constraints

- **No API costs for primary work** — Claude CLI uses subscription. Codex + Gemini CLIs same.
- **API fallback available** — orchestrator can route to Anthropic API if Claude CLI unavailable
- **Local only** — all daemons run on macOS. No cloud infra required.
- **Run flags**: `claude --dangerously-skip-permissions`, `codex --yolo`, `gemini --yolo`
- **Safety**: auto-git-commit always runs before destructive actions. No exceptions.
- **Python throughout** — consistent with existing pollers. No second language in stack.
- **Shared memory = integration layer** — no API bridge between orchestrator and Claude Code sessions. Filesystem is the bus.
