# eng-buddy

> Your on-call engineering assistant with a React dashboard, AI planner, playbook engine, and background pollers.

A Claude Code skill + local web dashboard that turns your `~/.claude/` directory into an intelligent engineering operations center. Background pollers watch Gmail, Slack, Jira, Google Calendar, and Freshservice — surfacing actionable cards you can approve, hold, refine, or execute as full Claude sessions. A built-in planner decomposes cards into executable plans, and a learning engine captures patterns from every interaction.

## What You Get

- **React dashboard** at `localhost:7777` — tabbed UI with inbox, Jira sprint, calendar, tasks, daily log, learnings, knowledge base, suggestions, and playbooks
- **Background pollers** — Gmail (10m), Slack (5m), Jira (5m), Calendar (30m) feed cards into a local SQLite queue
- **AI planner** — decomposes cards into multi-phase plans with tool calls, risk levels, and approval gates
- **Playbook engine** — reusable machine-executable workflows extracted from successful executions
- **One-click execution** — approve a card/plan and watch Claude execute it in a streaming terminal
- **Refine before acting** — chat with Claude about a card before approving
- **Open Session** — spawn a full interactive Claude session in Terminal.app for complex tasks
- **Learning engine** — brain module captures patterns, stakeholder insights, and automation opportunities from every session
- **7-hook automation** — auto-logging, context preservation across compaction, session snapshots, learning capture
- **3 themes** — Midnight Ops, Neon Dreams, Soft Kitty (each with dark/light modes)
- **Skill integration** — `/eng-buddy` auto-launches the dashboard and loads your full context
- **Comprehensive tracking** — passive data collection on energy, decisions, context switches, patterns

## Quick Start

```bash
# 1. Clone the repo (if you haven't already)
git clone https://github.com/kkudumu/clod.git ~/.claude

# 2. Install hooks (optional but recommended)
bash ~/.claude/skills/eng-buddy/bin/install-hooks.sh

# 3. Start the dashboard
cd ~/.claude/eng-buddy/dashboard
./start.sh
# Opens at http://localhost:7777

# 4. Invoke the skill in Claude Code
/eng-buddy
```

The dashboard auto-creates a Python venv and installs dependencies on first run.

## Architecture

```
~/.claude/skills/eng-buddy/          # Source repo (kkudumu/eng-buddy)
├── dashboard/                       # FastAPI web dashboard
│   ├── server.py                    # API: cards, SSE, WebSocket, plans, playbooks, settings
│   ├── migrate.py                   # Database migrations
│   ├── frontend/                    # React + TypeScript (Wave 2)
│   │   └── src/
│   │       ├── features/            # Feature modules
│   │       │   ├── inbox/           # Card queue, triage, Gmail actions
│   │       │   ├── plan/            # Plan viewer with phase accordion + step editor
│   │       │   ├── terminal/        # Embedded xterm.js terminal
│   │       │   ├── refine/          # Card refinement chat
│   │       │   ├── jira/            # Jira sprint board view
│   │       │   ├── calendar/        # Calendar event view
│   │       │   ├── tasks/           # Task management
│   │       │   ├── daily/           # Daily log viewer
│   │       │   ├── learnings/       # Pattern insights
│   │       │   ├── knowledge/       # Knowledge base browser
│   │       │   ├── suggestions/     # AI-generated suggestions
│   │       │   ├── playbooks/       # Playbook management + execution
│   │       │   ├── briefing/        # Meeting briefing modal with cognitive load
│   │       │   ├── stats/           # Metrics bar
│   │       │   ├── header/          # Theme picker, mode toggle, poller timers
│   │       │   └── debug/           # Debug drawer
│   │       ├── components/          # Badge, Button, ChibiMascot, Toast
│   │       ├── stores/              # Zustand state (ui, toast, debug)
│   │       ├── hooks/               # useCards, useSSE, usePlan, useSettings
│   │       ├── api/                 # API client + types
│   │       └── theme/               # tokens, animations, glassmorphism, themes
│   ├── static/                      # Vanilla JS fallback
│   ├── tests/                       # pytest suite
│   ├── requirements.txt             # fastapi, uvicorn, ptyprocess
│   └── start.sh                     # One-command launcher (LaunchAgent + health check)
├── bin/                             # Background pollers + engines
│   ├── gmail-poller.py              # OAuth2 email scanning → cards (collection-only)
│   ├── slack-poller.py              # DMs, @mentions, thread signals → cards (collection-only)
│   ├── jira-poller.py               # Jira REST sprint sync → cards
│   ├── calendar-poller.py           # Google Calendar API weekly sync → cards
│   ├── freshservice-poller.py       # Freshservice REST ticket sync → cards
│   ├── freshservice-enrichment.py   # Collection-only shim for legacy LaunchAgent
│   ├── brain.py                     # Learning engine: context builder + response parser
│   ├── planner/                     # AI plan generation
│   │   ├── planner.py               # Playbook match → LLM decomposition → Plan
│   │   ├── models.py                # PlanStep, Phase, Plan data models
│   │   ├── store.py                 # Plan persistence (JSON)
│   │   ├── prompter.py              # Planning prompt builder
│   │   ├── expander.py              # Tool gap filler
│   │   ├── converter.py             # Playbook → Plan converter
│   │   ├── learner.py               # Success/failure pattern extraction
│   │   └── worker.py                # Plan step executor
│   ├── playbook_engine/             # Reusable workflow system
│   │   ├── models.py                # PlaybookStep, Playbook, Trace models
│   │   ├── manager.py               # CRUD + trigger matching
│   │   ├── tracer.py                # Execution trace capture
│   │   ├── registry.py              # Tool capability catalog
│   │   └── extractor.py             # Auto-generate playbooks from traces
│   ├── install-hooks.sh             # One-shot hook installer
│   ├── start-pollers.sh             # Launch all pollers via LaunchAgent
│   └── start-planner.sh             # Launch planner daemon
├── hooks/                           # Claude Code hook scripts (7 hooks)
│   ├── eng-buddy-session-manager.sh # Session gate (start/stop/status)
│   ├── eng-buddy-auto-log.sh        # Progress detection + heartbeat
│   ├── eng-buddy-pre-compaction.sh  # Pre-compaction state flush
│   ├── eng-buddy-post-compaction.sh # Post-compaction context reload
│   ├── eng-buddy-learning-capture.sh# Learning extraction on tool use
│   ├── eng-buddy-session-snapshot.sh# End-of-session conversation capture
│   ├── eng-buddy-session-end.sh     # Marker cleanup
│   └── eng-buddy-task-sync.sh       # Task state sync with dashboard
├── docs/plans/                      # Design documents
├── SKILL.md                         # Skill definition + system prompt
├── INSTALL.md                       # Hook installation guide
└── README.md                        # This file
```

**Runtime directory** (`~/.claude/eng-buddy/`):
```
├── inbox.db              # SQLite card queue (auto-created)
├── playbooks/            # Executable workflow JSON files
│   ├── drafts/           # Draft playbooks pending review
│   └── archive/          # Archived playbooks
├── memory/               # Brain module persistent data
│   ├── context.json      # Working context
│   ├── stakeholders.json # People + interaction patterns
│   ├── patterns.json     # Recurring patterns
│   └── traces.json       # Execution traces
├── daily/                # Daily logs (YYYY-MM-DD.md)
├── weekly/               # Weekly summaries
├── sessions/             # Conversation snapshots
├── knowledge/            # Infrastructure, team, preferences
├── patterns/             # Success/failure patterns
├── tasks/                # Active task state
├── stakeholders/         # Communication logs
└── capacity/             # Time tracking, burnout indicators
```

## Dashboard

### Tabs

| Tab | What it shows |
|-----|---------------|
| **Inbox** | Card queue from all pollers — filter by source, classify, approve/hold/refine |
| **Jira** | Active sprint board with issue priorities and status |
| **Calendar** | This week's events with meeting prep briefings |
| **Tasks** | Active task tracking and management |
| **Daily** | Today's log with automatic entries from hooks |
| **Learnings** | Patterns and insights extracted by the brain module |
| **Knowledge** | Your knowledge base (infrastructure, team, preferences) |
| **Suggestions** | AI-generated action suggestions (refreshes every 30m) |
| **Playbooks** | Browse, manage, and execute reusable workflows |

### Key UI Features

- **Real-time updates** via Server-Sent Events (SSE) — new cards appear instantly
- **Streaming execution** via WebSocket — watch Claude execute plans step-by-step in an embedded xterm.js terminal
- **Plan viewer** — phase accordion with step-level approve/skip/edit controls and risk indicators
- **Refine chat** — discuss a card with Claude before committing to execution
- **Briefing modal** — meeting prep with cognitive load display and context links
- **Gmail actions** — inline reply, archive, and thread collapsing
- **Poller timers** — header countdown showing next poll cycle per source
- **Theme picker** — 3 themes (Midnight Ops, Neon Dreams, Soft Kitty) with dark/light modes
- **Debug drawer** — inspect API calls, SSE events, and state
- **Stats bar** — card counts, completion rates, and source breakdown
- **Toast notifications** — non-blocking feedback for actions
- **Chibi mascot** — animated companion in empty states

### API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Dashboard UI |
| `/api/health` | GET | Health check |
| `/api/cards` | GET | List cards (filter by status, source, classification) |
| `/api/cards/{id}/hold` | POST | Hold a card for later |
| `/api/cards/{id}/status` | POST | Update card status |
| `/api/cards/{id}/analyze` | POST | AI analysis of card content |
| `/api/cards/{id}/resolve-related` | POST | Mark related/duplicate cards resolved |
| `/api/events` | GET | SSE stream for real-time card updates |
| `/ws/execute/{id}` | WebSocket | Stream Claude execution output |
| `/api/cards/{id}/refine` | POST | Chat about a card before execution |
| `/api/cards/{id}/open-session` | POST | Spawn interactive Claude in Terminal.app |
| `/api/playbooks` | GET | List approved playbooks |
| `/api/playbooks/{id}` | GET | Get playbook details |
| `/api/playbooks/drafts` | GET | List draft playbooks |
| `/api/settings` | GET/POST | Dashboard settings (theme, terminal, notifications) |
| `/api/cache-invalidate` | POST | Clear cache on poller updates |
| `/api/notify` | POST | Fire macOS notification |

## Pollers

### Gmail Poller (every 10 minutes)
- Scans all inbox emails from last 3 days via OAuth2
- Classifies each: action-needed, alert, or noise
- Generates draft replies using Claude CLI
- Tracks ignored senders for adaptive filter suggestions
- Thread-based deduplication and collapsing

### Slack Poller (every 5 minutes)
- Fetches DMs, @mentions, and thread participation from last 3 days
- Classifies messages: needs-action vs no-action
- Generates contextual draft responses with full thread context
- Excludes broadcast messages (@channel/@here/@everyone)
- Priority scoring (needs-action=4, responded=2, draft=1, notes=1)
- Rate limiting with exponential backoff

### Jira Poller (every 5 minutes)
- Fetches assigned issues from active sprint via Atlassian MCP
- Maps Jira priority to card classification
- Tracks by status, priority, last updated
- Returns top 30 issues sorted by priority

### Calendar Poller (every 30 minutes)
- Fetches events for today through end of week via Google Calendar MCP
- Enriches events with Jira links and meeting prep context
- Identifies meetings vs all-day events
- Extracts attendees, location, Meet/Zoom links

### Freshservice Poller
- Monitors assigned tickets via Freshservice MCP
- Creates action cards with priority classification

### Writing Your Own Poller

Any script that writes rows to `inbox.db` becomes a card source:

```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,                    -- 'gmail', 'slack', 'jira', 'calendar', 'freshservice'
    timestamp TEXT,                 -- ISO 8601 UTC
    summary TEXT,                   -- Card title shown in dashboard
    classification TEXT,            -- 'needs-response', 'fyi', 'needs-action'
    status TEXT DEFAULT 'pending',  -- 'pending', 'held', 'approved', 'completed', 'failed'
    proposed_actions TEXT,          -- JSON array of action objects
    draft_response TEXT,            -- Claude-generated response draft
    context_notes TEXT,             -- Why this card needs attention
    analysis_metadata TEXT,         -- JSON with category, labels, reasoning
    section TEXT,                   -- 'needs-action', 'no-action'
    responded INTEGER DEFAULT 0,   -- 1 if already responded to
    execution_status TEXT DEFAULT 'not_run',
    execution_result TEXT,
    executed_at TEXT
);
```

**Minimal Python example**:
```python
import sqlite3, json
from datetime import datetime, timezone
from pathlib import Path

db = Path.home() / ".claude" / "eng-buddy" / "inbox.db"
conn = sqlite3.connect(db)
conn.execute("""INSERT INTO cards
    (source, timestamp, summary, classification, status, proposed_actions, execution_status)
    VALUES (?, ?, ?, ?, 'pending', ?, 'not_run')""",
    ("my-custom-source",
     datetime.now(timezone.utc).isoformat(),
     "Something happened that needs attention",
     "action-required",
     json.dumps([{"type": "custom", "draft": "Do the thing"}])))
conn.commit()
conn.close()
```

## Planner

The planner decomposes inbox cards into executable multi-phase plans:

1. **Playbook matching** — checks if an existing playbook covers the task
2. **LLM decomposition** — if no match, calls Claude CLI with tool registry + learned context to generate a plan
3. **Tool gap expansion** — fills `__MISSING__` tool markers with concrete tool calls
4. **Plan persistence** — stores plans as JSON linked to their source card

Each plan has:
- **Phases** with named groups of steps
- **Steps** with tool name, params, risk level, and approval requirements
- **Status tracking** — pending, approved, executing, done, failed per step
- **Learning capture** — success/failure patterns feed back into future planning

## Playbook Engine

Playbooks are reusable, machine-executable workflows:

```
playbooks/
├── fs-hide-catalog-el.json    # Hide Freshservice portal elements via Playwright
├── drafts/                    # Drafts pending review
└── archive/                   # Archived playbooks
```

Each playbook contains:
- **Trigger keywords** — auto-match against incoming card text
- **Steps** — exact MCP tool name, exact params, exact code
- **Confidence score** — updated based on execution success rate
- **Execution count** — tracks usage

The engine also:
- **Traces** execution to capture tool call sequences
- **Extracts** new playbook drafts from successful traces
- **Promotes** drafts to approved playbooks after review

## Learning Engine (Brain)

The brain module (`bin/brain.py`) builds persistent memory from every interaction:

- **Context builder** — injects stakeholder info, patterns, and preferences into planner/poller prompts
- **Response parser** — extracts patterns, automation opportunities, and stakeholder updates from Claude outputs
- **Auto-categorization** — routes learning into categories: playbook, stakeholder, troubleshooting, success-pattern, failure-pattern, recurring-question, documentation-gap

Memory persists across sessions in JSON files under `memory/`.

## Hook System

Seven Claude Code hooks provide session automation. All hooks are session-gated — they only activate during `/eng-buddy` sessions.

| Hook | Trigger | Purpose |
|------|---------|---------|
| `session-manager` | Manual (STEP 0) | Gate all hooks via `.session-active` marker |
| `auto-log` | UserPromptSubmit | Detect progress phrases + heartbeat checks |
| `pre-compaction` | UserPromptSubmit | Flush state to daily log before context fills |
| `post-compaction` | UserPromptSubmit | Reload context after compaction detected |
| `learning-capture` | PostToolUse | Extract learning from Write/Edit/Bash/MCP results |
| `session-snapshot` | SessionEnd | Capture last 15 exchanges as dated markdown |
| `session-end` | SessionEnd | Remove `.session-active` marker |

Install with one command:
```bash
bash ~/.claude/skills/eng-buddy/bin/install-hooks.sh
```

See [INSTALL.md](INSTALL.md) for detailed hook configuration.

## Skill Commands

In a `/eng-buddy` session:

| Say this | Get this |
|----------|----------|
| "what happened today" | Narrative analysis with data backing |
| "what's blocking me?" | Active blockers with aging and escalation suggestions |
| "am I overcommitted?" | Capacity analysis and recommendations |
| "what patterns do you see?" | Recurring issues, questions, success/failure patterns |
| "show my stats" | Key metrics: completion rate, energy, context switches |
| "draft status update" | Generate stakeholder communication |
| "wrap up" | Summarize day, roll forward open items |

## Requirements

- **macOS** (LaunchAgents, Terminal.app, osascript — Linux support possible with cron + alternatives)
- **Python 3.11+**
- **Node.js 18+** (for React dashboard frontend)
- **Claude Code CLI** (`claude` in PATH)
- **MCP servers** configured for the pollers you want:
  - Gmail MCP — for email polling
  - Slack API token — for Slack polling
  - Atlassian MCP — for Jira polling
  - Google Calendar MCP — for calendar polling
  - Freshservice MCP — for ticket polling
  - Playwright MCP — for browser automation playbooks

## Plugging In Your Own Stuff

eng-buddy ships empty — you populate it with your own integrations, knowledge, and credentials.

### Gmail Poller Setup
```bash
# Set up Gmail MCP credentials
# Follow: https://github.com/anthropics/gmail-mcp-server
# Credentials: ~/.gmail-mcp/credentials.json and gcp-oauth.keys.json

# Create your watch list
cp ~/.claude/eng-buddy/email-watches.md.example ~/.claude/eng-buddy/email-watches.md
```

### Slack Poller Setup
```bash
# Edit the poller and set your Slack user token
# Get from: https://api.slack.com/apps
# Scopes: channels:history, groups:history, im:history, mpim:history, users:read
```

### Jira Poller Setup
Requires Claude Code CLI + [Atlassian MCP server](https://github.com/sooperset/mcp-atlassian) configured in `.claude.json`. The poller calls `claude --dangerously-skip-permissions --print` to query via MCP.

### Calendar Poller Setup
Requires [Google Calendar MCP server](https://github.com/anthropics/google-calendar-mcp) configured in `.claude.json`.

### LaunchAgent Installation

All pollers run as macOS LaunchAgents. Example for Gmail (10-min interval):

```bash
cat > ~/Library/LaunchAgents/com.engbuddy.gmailpoller.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.engbuddy.gmailpoller</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${HOME}/.claude/eng-buddy/bin/gmail-poller.py</string>
  </array>
  <key>StartInterval</key><integer>600</integer>
  <key>StandardOutPath</key><string>${HOME}/.claude/eng-buddy/gmail-poller.log</string>
  <key>StandardErrorPath</key><string>${HOME}/.claude/eng-buddy/gmail-poller.log</string>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.engbuddy.gmailpoller.plist
```

Or use the bulk launcher:
```bash
bash ~/.claude/eng-buddy/bin/start-pollers.sh
```

## Checking Poller Status

```bash
# See all running pollers
launchctl list | grep engbuddy

# Check logs
tail -f ~/.claude/eng-buddy/gmail-poller.log
tail -f ~/.claude/eng-buddy/slack-poller.log
tail -f ~/.claude/eng-buddy/jira-poller.log
tail -f ~/.claude/eng-buddy/calendar-poller.log
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLite3, ptyprocess, uvicorn |
| Frontend | React + TypeScript, xterm.js, CSS Modules |
| Pollers | Python 3.11+, Claude CLI, OAuth2 |
| Planning | Claude CLI, tool registry, JSON persistence |
| Automation | macOS LaunchAgents, zsh/bash scripts |
| Integration | Slack MCP, Gmail MCP, Atlassian MCP, Google Calendar MCP, Freshservice MCP, Playwright MCP |

## License

MIT — see [LICENSE](../LICENSE)
