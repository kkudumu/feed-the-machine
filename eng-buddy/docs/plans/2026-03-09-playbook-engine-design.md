# Playbook Engine for eng-buddy

**Date**: 2026-03-09
**Status**: Approved
**Goal**: Transform eng-buddy from an assistant that helps you work into one that works for you — observing how you handle tickets, distilling repeatable processes into playbooks, and executing them autonomously with human-in-the-loop approval.

---

## 1. Playbook Data Model

A playbook is a versioned, executable document with action-bound steps.

**Location**: `~/.claude/eng-buddy/playbooks/{playbook-name}.yml`

```yaml
id: sso-onboarding
name: SSO Onboarding
version: 3
confidence: high  # high | medium | low
trigger_patterns:
  - ticket_type: "Service Request"
    keywords: ["SSO", "SAML", "single sign-on", "SCIM"]
    source: ["freshservice", "jira"]
created_from: session  # session | dictated | pattern-detection
executions: 5
last_executed: 2026-03-08
last_updated: 2026-03-08
update_history:
  - version: 2
    reason: "auto-update: added SCIM provisioning step"
  - version: 3
    reason: "user-approved: reordered steps for IdP-initiated flow"

steps:
  - id: 1
    name: "Create Jira implementation ticket"
    action:
      tool: mcp__mcp-atlassian__jira_create_issue
      params:
        project: ITWORK2
        summary: "[SSO] {{app_name}} - DUE: {{due_date}}"
        epic: ITWORK2-4644
      param_sources:
        app_name: { from: "trigger_ticket", field: "subject", extract: "app name" }
        due_date: { calculate: "today + 30 days" }
    auth_required: false
    human_required: false

  - id: 2
    name: "Configure SAML in IdP"
    action:
      tool: playwright
      navigate_to: "https://{{idp_url}}/admin/applications"
      prefill: ["app name", "ACS URL from ticket"]
    auth_required: true
    auth_method: stored_session  # or "human_handoff" if no creds
    human_required: false  # becomes true if no stored auth

  - id: 3
    name: "Send configuration details to requester"
    action:
      tool: mcp__slack__slack_post_message
      params:
        channel: "{{requester_slack_channel}}"
        text: "{{generated_from_template: sso-config-details}}"
    auth_required: false
    human_required: false
```

**Key properties:**
- Steps have explicit **action bindings** (tool + params + param sources)
- `auth_required` and `human_required` flags control execution flow
- `param_sources` define where dynamic values come from (trigger ticket, calculations, user input)
- `confidence` reflects how battle-tested the playbook is (low/medium/high)
- `trigger_patterns` enable automatic matching from pollers

---

## 2. Tool Registry

A modular catalog of available tools, their capabilities, auth requirements, and per-task defaults.

**Location**: `~/.claude/eng-buddy/playbooks/tool-registry/`

```
tool-registry/
  _registry.yml              # Core tool catalog (types, prefixes, auth)
  jira.defaults.yml          # Jira-specific defaults, field mappings
  freshservice.defaults.yml
  slack.defaults.yml
  gmail.defaults.yml
  playwright.defaults.yml    # Per-domain browser configs
  confluence.defaults.yml
  scripts.defaults.yml       # Local script conventions
```

### Core Registry (_registry.yml)

```yaml
tools:
  jira:
    type: mcp
    prefix: mcp__mcp-atlassian__jira_
    capabilities: [create_issue, update_issue, transition_issue, add_comment, search]
    auth: persistent
    domains: [ticket_management, project_tracking]

  freshservice:
    type: mcp
    prefix: mcp__freshservice-mcp__
    capabilities: [create_ticket, update_ticket, send_ticket_reply, filter_tickets]
    auth: persistent
    domains: [ticket_management, service_desk]

  slack:
    type: mcp
    prefix: mcp__slack__
    capabilities: [post_message, reply_to_thread, get_channel_history]
    auth: persistent
    domains: [communication, notifications]

  gmail:
    type: mcp
    prefix: mcp__gmail__
    capabilities: [send_email, search_emails, draft_email]
    auth: persistent
    domains: [communication, notifications]

  google_calendar:
    type: mcp
    prefix: mcp__google-calendar__
    capabilities: [create_event, list_events, update_event]
    auth: persistent
    domains: [scheduling]

  confluence:
    type: mcp
    prefix: mcp__mcp-atlassian__confluence_
    capabilities: [create_page, update_page, search]
    auth: persistent
    domains: [documentation]

  playwright:
    type: browser
    prefix: mcp__playwright__
    capabilities: [navigate, click, fill_form, screenshot, snapshot]
    auth: per_domain
    auth_store: ~/.claude/eng-buddy/auth/sessions.enc
    domains: [web_admin, sso_config, any_web_ui]
    fallback: human_handoff

  local_scripts:
    type: script
    path: ~/.claude/eng-buddy/bin/
    discovery: automatic
    auth: none
    domains: [data_processing, automation, utilities]

  claude:
    type: ai
    capabilities: [generate_text, analyze_data, draft_response, extract_fields]
    auth: none
    domains: [content_generation, analysis, decision_making]
```

### Per-Tool Defaults (e.g., jira.defaults.yml)

```yaml
create_issue:
  assignee: "kioja.kudumu@klaviyo.com"
  board_id: 70
  sprint: current  # resolved at execution time via API
  epic: null       # set per-playbook
  labels: []

transition_issue:
  notify: true

field_mappings:
  sprint_field: "customfield_10020"
  story_points: "customfield_10028"
```

**How the registry is used:**
- **Playbook creation**: When brain.py observes a tool call, it binds the step to the registry entry
- **Draft playbooks**: For unknown ticket types, checks which tools cover needed domains and proposes bindings
- **Auth gating**: Checks `persistent` (proceed), `per_domain` (check stored sessions), or `human_handoff`
- **Default merging**: Playbook params + tool defaults + dynamic param_sources merged at execution time
- **Discovery**: `local_scripts` auto-discovers new scripts; new `.defaults.yml` files auto-discovered

---

## 3. Continuous Playbook Extraction

### Expanded Observation (beyond tool calls)

| Signal | Example | What it captures |
|--------|---------|-----------------|
| Tool calls | `jira_create_issue` | Concrete actions taken |
| User instructions | "always add the SSO label" | Rules and preferences |
| User corrections | "no, use the other sprint board" | Refinements to defaults |
| Manual actions reported | "I just configured SAML in Okta" | Human steps eng-buddy can't see |
| Decisions explained | "I chose SAML over OIDC because..." | Decision rationale |
| Questions asked | "what's the ACS URL format?" | Knowledge gaps to pre-fill next time |
| Conversation flow | User asks about X before doing Y | Natural task ordering |
| Things skipped | "skip the Slack notification" | Conditional steps |

### Trace Format

```yaml
# traces/active/ITWORK2-9740.json
events:
  - type: user_instruction
    content: "Let's do the SSO onboarding for Linear"
    inferred_intent: "Execute SSO onboarding playbook"

  - type: user_rule
    content: "Always set due date to 30 days out"
    applies_to: [jira.create_issue]
    persist: true

  - type: tool_call
    tool: jira_create_issue
    params: { ... }

  - type: user_manual_action
    content: "I configured SAML in the Linear admin panel"
    inferred_step: "Configure SAML in target app"
    action_binding: playwright
    auth_note: "needs Linear admin access"

  - type: user_correction
    content: "No, assign it to the next sprint, not current"
    corrects: tool_defaults.jira.create_issue.sprint
    new_value: "next"

  - type: user_decision
    content: "Using SCIM because Linear supports it"
    context: "SCIM vs manual provisioning"
    decision: "SCIM"
    rationale: "Linear supports it"

  - type: question_asked
    content: "What's the entity ID for Linear?"
    resolution: "Found in Linear SAML settings page"
    prefill_next_time: true
```

### Pattern Detection (continuous)

After each tool use, brain.py compares the current trace against existing playbooks and past traces. Three signals trigger extraction:

- **Completion**: Ticket resolved/transitioned - full trace available
- **Similarity**: Current trace matches 70%+ of a previous trace
- **Repetition**: Same sequence of 3+ tool types seen across 2+ sessions

### Extraction Pipeline

1. Brain.py groups tool calls into logical steps
2. Identifies ticket-specific params (dynamic) vs. consistent params (defaults)
3. Generates draft playbook YAML with action bindings from tool registry
4. Assigns confidence: `low` (first seen), `medium` (seen twice), `high` (3+ successful executions)
5. Writes to `~/.claude/eng-buddy/playbooks/drafts/{name}.yml`
6. Pushes dashboard card: "New playbook drafted — Review & approve"

---

## 4. Approval Interface

### Dashboard — "Playbooks" tab

**Section 1: Pending Review** — Draft playbooks awaiting confirmation
- Shows: playbook name, confidence level, source sessions, numbered steps
- Actions: Edit steps, approve, reject, merge with existing playbook

**Section 2: Ready to Execute** — Incoming tickets matched to approved playbooks
- Shows: ticket title, matched playbook, pre-filled step list with resolved params
- Approval commands via input field:
  - `approve all`
  - `approve all but #3, #5`
  - `approve all but ask me before sending slack messages`
  - `approve #1-#4, hold on #5 until I finish the manual config`
- Dispatches execution to a visible terminal session

**Section 3: Active Executions** — Currently running playbooks
- Progress bar, current step, completed (green), waiting (amber), failed (red)
- Live updates via SSE from execution engine
- "Pause" and "Cancel" buttons
- Human-required steps show notification with context and "Done" button

**Dashboard card states:**
- **Draft (amber)** — Extracted from traces, needs review
- **Approved (green)** — Reviewed and confirmed
- **Suggested (blue)** — Matched to incoming ticket, awaiting dispatch
- **Executing (purple)** — Currently running
- **Needs attention (red)** — Hit a human-required step or error

### Claude Code Session — Manual Invocation

```
You: "Run SSO onboarding for Linear"

eng-buddy:
  Matched playbook: SSO Onboarding (v3, high confidence)
  Ticket: FS-4521 - Linear SSO Setup Request

  1. Create Jira ticket [SSO] Linear - DUE: 4/8/26    -> jira API
  2. Configure SAML in Okta                            -> playwright (stored session)
  3. Configure SAML in Linear admin                    -> playwright (human handoff)
  4. Test SSO login flow                               -> playwright
  5. Send config details to requester via Slack         -> slack API
  6. Update Freshservice ticket to resolved             -> freshservice API

  Type your approval:
```

### Execution Dispatch

- Approval triggers a new Claude Code session in the user's active terminal (visible, interactive)
- The session opens with playbook context pre-loaded, shows each step as it executes
- User can intervene mid-execution ("skip #4", "wait, let me do this part")
- Dashboard shows parallel progress view for at-a-glance monitoring

### Human-Required Steps (Guided Handoff)

- eng-buddy opens the browser via Playwright to the correct page
- Pre-fills what it can (app name, URLs, config values)
- Pauses: "Your turn for the auth/config part"
- Watches for completion signal
- For recurring tasks, offers to store credentials for full automation next time

---

## 5. Playbook Evolution

### Auto-Updates (silent, minor corrections)
- Param correction during execution -> tool default updated, playbook step patched
- Step skipped consistently -> marked `optional: true` after 2 occurrences
- Resolved values change (new sprint, new team member) -> handled by dynamic param sources

### Proposed Revisions (structural, needs approval)
- New step added -> dashboard card: "Add step 3.5: Verify SCIM connection? [approve/reject]"
- Steps reordered -> "Reorder: move Slack notification before Jira transition? [approve/reject]"
- Different tool used for same step -> "Change step 2 from Playwright to API call? [approve/reject]"
- Proposals queue up, don't block current version execution

### Confidence Progression

```
low (draft) -> medium (1 successful execution) -> high (3+ without corrections)
```

- Structural revision resets confidence one level
- Auto-updates don't affect confidence
- Failed executions drop confidence one level

### Versioning
- Each approved revision increments version number
- Previous versions archived in `playbooks/archive/{name}/v{n}.yml`
- Dashboard shows version history with diffs, supports rollback

---

## 6. Three Creation Paths

### Path 1: Watch and Learn (automatic)
- Work a ticket in a Claude Code session
- Brain.py captures full trace (tools, instructions, corrections, manual actions, decisions)
- On completion, extraction pipeline drafts a playbook
- Dashboard card: "New playbook drafted from your ITWORK2-9740 session"
- Review, edit, approve -> playbook is live

### Path 2: Describe and Codify (dictated)
- Tell eng-buddy: "Create a playbook for offboarding. Steps are: disable Okta, remove from Slack, archive Jira, notify manager"
- eng-buddy expands each step with action bindings, fills defaults, identifies auth requirements
- Presents full YAML for review
- Starts at `medium` confidence; first execution validates and promotes to `high`

### Path 3: Pattern Detection (proactive)
- Brain.py runs periodic analysis across traces, task-execution logs, session snapshots
- Detects: "You've handled 4 certificate renewal tickets with similar steps"
- Dashboard card: "Suggested playbook: Certificate Renewal (from 4 sessions) — Review"
- Starts at `low` confidence until reviewed
- Shows source sessions for verification

### Convergence
- All paths produce playbooks in `~/.claude/eng-buddy/playbooks/` as YAML
- Same approval interface, execution engine, and evolution rules
- `created_from` field tracks origin: `session`, `dictated`, or `pattern-detection`
