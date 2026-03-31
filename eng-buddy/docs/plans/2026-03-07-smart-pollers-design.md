# eng-buddy Smart Pollers, Dashboard Tabs & Learning Engine

**Date**: 2026-03-07
**Status**: Approved

---

## Overview

Upgrade eng-buddy from a notification triage tool into an intelligent work automation platform with:
- Smart Slack/Gmail/Calendar tabs with two-section layouts (needs-action vs no-action)
- Claude CLI classification with context-enriched draft responses
- Morning briefing with cognitive load analysis and pep talk
- Adaptive Gmail filtering that learns from user behavior
- Persistent learning engine that captures work patterns, stakeholder context, and automation opportunities
- Architecture designed so future "hands" (bots) can be attached to the "brain"

---

## Section 1: Shared Architecture

### Pipeline

All three sources follow the same flow:
1. **Poller** runs on schedule via LaunchAgent, collects raw data
2. **Claude CLI batch call** classifies each item and drafts responses for needs-action items. Enriches with cross-MCP context (Jira, Freshservice, Calendar, stakeholder graph)
3. Results written to **inbox.db** with section, draft, and context fields
4. **Dashboard** renders two sections per tab, SSE pushes new cards live
5. **Learning engine** parses Claude response for new patterns, stakeholder updates, automation opportunities

### Polling Frequencies
- Slack: every 5 min
- Gmail: every 10 min
- Calendar: every 30 min
- All pollers skip Claude call if no new items found

### inbox.db Schema Additions

```sql
ALTER TABLE cards ADD COLUMN section TEXT DEFAULT 'needs-action';
ALTER TABLE cards ADD COLUMN draft_response TEXT;
ALTER TABLE cards ADD COLUMN context_notes TEXT;
ALTER TABLE cards ADD COLUMN responded INTEGER DEFAULT 0;
ALTER TABLE cards ADD COLUMN filter_suggested INTEGER DEFAULT 0;
```

### Stats Table

```sql
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    date TEXT,
    metric TEXT,
    value REAL,
    details TEXT
);
```

Tracks: drafts_sent, drafts_refined, cards_triaged, filters_created, context_switches_saved, response_time_avg.

### Classification Categories

| Classification | Description | Example |
|---------------|-------------|---------|
| `needs-action` | Requires user response or decision | Slack question, email needing reply |
| `alert` | FYI, good to know, no action | Offboarding notification, cert alert |
| `noise` | Filtered, hidden by default | Marketing emails, duplicate alerts |
| `auto-executable` | Future: bot can handle with approval gate | Known-issue ticket, cert renewal |
| `learning` | Eng-buddy detected a new pattern | "You did this 3 times, want a playbook?" |

---

## Section 2: Slack Tab

### Poller Changes (slack-poller.py)
- Expand scope: unread messages + all threads user participated in within last 3 days
- Track responded status: if user_id has a reply after the last message, mark responded
- Detect @here mentions in addition to direct @mentions
- After collecting, batch call Claude CLI with full context prompt
- Write to inbox.db with section, draft_response, context_notes

### Dashboard Layout — Two Sections
- **NEEDS ACTION / UNREAD**: Messages requiring response, with Claude-drafted replies
- **RESPONDED / NO ACTION**: Conversations user already replied to or that need no action

### Card Actions
- **SEND DRAFT**: Calls Slack MCP to post response in correct thread
- **REFINE**: Opens refine panel to edit draft with Claude
- **DISMISS**: Moves card to no-action section

### Draft Response Behavior
- Claude drafts responses with cross-MCP context (B approach — full context enrichment)
- Example: someone asks about a Freshservice ticket -> Claude looks up ticket status and drafts response with current status
- All drafts require user approval before sending

---

## Section 3: Gmail Tab

### Poller Changes (gmail-poller.py)
- Remove watch-file dependency — scan all inbox emails
- Scope: all emails in inbox from last 3 days
- Claude CLI classifies as: action-needed, alert/fyi, or noise
- For action-needed: Claude drafts response with cross-MCP context
- For alerts: Claude writes one-line summary

### Dashboard Layout — Three Sections
- **ACTION NEEDED**: Emails requiring response or decision
- **ALERTS / FYI**: Informational emails worth knowing about
- **FILTERED / NOISE**: Collapsed by default, marketing/spam/duplicates

### Card Actions
- **SEND DRAFT**: Sends email reply via Gmail MCP
- **OPEN IN GMAIL**: Opens email in browser
- **ACK**: Acknowledge alert, mark as seen
- **SNOOZE**: Snooze alert for later
- **DISMISS**: Move to noise

### Adaptive Filtering (Gmail only)
- Track card interactions: opened, dismissed, approved, ignored
- After 10+ ignored cards from same sender/pattern, surface suggestion
- CREATE FILTER: calls Gmail MCP create_filter to auto-label + skip inbox
- Suggestion stored in db so it doesn't re-suggest if dismissed with NOT NOW
- User can also say NEVER to permanently suppress suggestions for that pattern

---

## Section 4: Google Calendar Tab

### New Poller (calendar-poller.py)
- Fetches today's events via Google Calendar MCP every 30 min
- One Claude CLI call to enrich events with context from Jira/Freshservice/email
- Matches events to related work: attendee names -> recent Slack threads, meeting titles -> Jira tickets

### Dashboard Layout — Agenda + Context
- **TODAY**: Timeline of events with prep notes per event
- **TOMORROW**: Preview of next day
- **WEEK AHEAD**: Collapsible summary (Mon: 3 events, Tue: 5 events...)

### Card Actions
- **JOIN**: Opens meeting link (Google Meet/Zoom URL from event)
- **PREP NOTES**: Foldout where Claude generates briefing pulling from Jira, email, Slack related to meeting attendees/topic

---

## Section 5: Morning Briefing

### Trigger
- First dashboard load each day, or manual "Briefing" button
- `GET /api/briefing` endpoint

### Content
1. **Today's meetings** with prep notes for each
2. **Needs your response** — top items across Slack + Gmail
3. **Alerts** — offboarding, cert expirations, SLA warnings
4. **Sprint status** — from Jira cache
5. **Cognitive load assessment** — meeting density, pending action count, deep work windows
6. **Eng-buddy stats** — drafts sent, cards triaged, time saved yesterday/this week
7. **Heads up** — stakeholder wait times, SLA deadlines, overdue items, sprint blockers
8. **Pep talk** — personalized based on workload and recent velocity

### Implementation
- Single Claude CLI call with: today's calendar, pending cards, sprint data, stakeholder graph, stats
- Stored in db (one per day), regenerate on demand
- Rendered as modal overlay on first load

---

## Section 6: Learning Engine & Persistent Context

### Three Knowledge Stores

#### 1. Stakeholder Graph (`memory/stakeholders.json`)
- Per-person: role, relationship, communication style, priority weight, response expectations, recent topics, notes
- Auto-updated on every Slack/email card processing

#### 2. Patterns & Playbooks (`memory/patterns.json`)
- Captured patterns with: trigger, steps observed, automation level, times used
- Automation opportunities detected but not yet confirmed
- Pattern promotion pipeline: observe -> suggest -> playbook -> automatable

#### 3. Work Context & Preferences (`memory/context.json`)
- Role, team, company, manager, tools, response tone preferences
- Current priorities (synced from Jira sprint)
- Learned rules (e.g., "offboarding hire-rescinded emails never need action")
- Deep work hours, standup time, other scheduling preferences

### Prompt Injection
Every Claude CLI call gets injected with:
- Relevant stakeholders for the current batch
- Matching playbooks
- Learned rules
- Current priorities
- User preferences

### Self-Healing Hooks
After every Claude classification call, parse response for:
- NEW_PATTERNS: New repeating workflows detected
- STAKEHOLDER_UPDATES: Changed roles, communication patterns
- AUTOMATION_OPPORTUNITIES: Steps that could be automated
- LEARNED_RULES: New classification rules from user behavior

These get merged into the respective memory files automatically.

### Dashboard Surfacing
- New patterns and automation opportunities appear as special cards
- User controls: [YES, AUTOMATE] [NOT YET] [NEVER]
- Automation levels: observe -> suggest -> playbook -> automatable (user must explicitly promote each level)

---

## Section 7: Automation-Ready Brain

### Work Trace Log (`memory/traces.json`)
Every action flowing through eng-buddy is recorded with:
- Trigger (what started it)
- Trigger pattern (regex/template for matching future instances)
- Category (offboarding, sso-setup, access-request, etc.)
- Steps observed (sequence of actions taken)
- Total time, outcome
- Links to similar traces

### Trace Capture Methods
- **Passive**: Every classification call, Claude notes what changed (Jira status moves, ticket updates, email replies, Slack resolutions)
- **Active**: When user approves/executes a card, execution output is parsed for action steps

### Pattern Promotion Pipeline
```
observe -> suggest -> playbook -> automatable
```

Key fields for future bot-building:
- `required_inputs`: What the bot needs to start
- `required_tools`: What MCPs/APIs the bot needs
- `steps`: The playbook sequence
- `promotion_criteria`: When it's safe to automate (e.g., 10 observations with < 20% deviation)

### Classification Prompt Addition
Every Claude call also asks:
- WORK_TRACE: What step in the workflow is this? What came before, what comes next?
- PATTERN_MATCH: Does this match a known pattern?
- PATTERN_NEW: Is this a repeating workflow seen 2+ times not yet captured?
- AUTOMATION_READINESS: Could the next step be auto-drafted or auto-executed?

### Weekly Brain Digest
Once per week, Claude reviews all traces and patterns:
- Patterns strengthened (closer to promotion)
- New patterns detected (capture as playbook?)
- Automation savings potential (hrs/week if top patterns automated)
- Stakeholder insights (response times, collaboration frequency)

---

## Implementation Order

**Week 1**: Slack/Gmail/Calendar tabs + morning briefing + learning engine
**Week 2+**: Iterate on bots as patterns mature and get promoted to automatable

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Classification engine | Claude CLI for everything (option B) | Smarter classification, context-aware drafts |
| Gmail filtering | Adaptive (Claude suggests filters over time) | Learns from behavior, no upfront config |
| Calendar view | Agenda + context (option C) | Links meetings to Jira/email, actionable prep |
| Draft responses | Context-enriched, approval required (option B) | Cross-MCP context is the killer feature, no auto-send risk |
| Polling | Slack 5m, Gmail 10m, Calendar 30m + morning briefing (option C) | Balanced freshness vs cost, briefing is the main UX |
| Adaptive filtering | Gmail only | Slack already scoped to user's conversations, Calendar is own events |
