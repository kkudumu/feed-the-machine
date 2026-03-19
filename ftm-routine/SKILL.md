---
name: ftm-routine
description: Execute named, recurring multi-step workflows from YAML definitions. Use when user says "routine", "run routine", "ftm-routine", "morning triage", or names a known routine.
---

# FTM Routine Runner

Routines are named, recurring multi-step workflows defined as YAML in `~/.ftm/routines/`. Each routine specifies steps that combine skill invocations, MCP operations, and approval gates.

## Routine Format

Routines are stored as YAML files in `~/.ftm/routines/`:

```yaml
name: morning-triage
description: Check all inboxes, prioritize, and plan the day
trigger: manual  # only "manual" for v1, future: "schedule", "event"
tags: [triage, daily, ops]

steps:
  - name: Check Jira backlog
    action: mcp
    tool: jira_search
    params:
      jql: "assignee = currentUser() AND status != Done ORDER BY priority DESC"
    approval: none  # no approval needed for read operations

  - name: Check Freshservice tickets
    action: mcp
    tool: get_tickets
    params:
      filter: "agent_id:me AND status:2"  # open tickets assigned to me
    approval: none

  - name: Check Slack mentions
    action: mcp
    tool: slack_get_channel_history
    params:
      channel: "general"
      limit: 20
    approval: none

  - name: Check email
    action: mcp
    tool: search_emails
    params:
      query: "is:unread"
      max_results: 10
    approval: none

  - name: Synthesize and prioritize
    action: skill
    skill: ftm-mind
    input: "Based on the above: prioritize today's work. What's urgent? What can wait?"
    approval: review  # show synthesis for user review before proceeding

  - name: Create today's plan
    action: skill
    skill: ftm-mind
    input: "Create a plan for today's top 3 priorities"
    approval: approve  # full plan approval before execution
```

## Invocation

```
/ftm-routine morning-triage
```

Or via ftm-mind when it detects a routine name:
```
/ftm run my morning triage
```

## Execution Flow

1. **Load routine** — Read `~/.ftm/routines/[name].yml`
2. **Validate** — Check all referenced MCP tools and skills are available
3. **Present as plan** — Convert routine steps to the standard plan format:
   ```
   Routine: morning-triage — "Check all inboxes, prioritize, and plan the day"

   1. Check Jira backlog (auto)
   2. Check Freshservice tickets (auto)
   3. Check Slack mentions (auto)
   4. Check email (auto)
   5. Synthesize and prioritize (review)
   6. Create today's plan (approve)

   Steps 1-4 run automatically. Step 5 pauses for your review.
   Step 6 requires your approval before execution.

   Say "go" to start.
   ```
4. **Execute** — Run steps in order, respecting approval gates:
   - `approval: none` — execute automatically, show results
   - `approval: review` — execute, show results, wait for "continue" or "stop"
   - `approval: approve` — show plan, wait for "go" before executing

## Step Types

| Action | Description | Example |
|---|---|---|
| `mcp` | Call an MCP tool directly | `jira_search`, `slack_post_message` |
| `skill` | Invoke an FTM skill | `ftm-mind`, `ftm-debug`, `ftm-brainstorm` |
| `bash` | Run a shell command | `npm test`, `git status` |

## Creating Routines

Users create routines by:
1. Writing YAML directly to `~/.ftm/routines/[name].yml`
2. Saving a successful plan as a routine: "save as routine" (future enhancement)
3. Asking ftm-mind: "create a routine for my morning triage"

## Listing Routines

```
/ftm-routine list
```
Shows all routines in `~/.ftm/routines/` with name and description.

## Example Routines

### morning-triage
Check Jira, Freshservice, Slack, email → synthesize → prioritize → plan

### deploy-checklist
Run tests → check CI → review changelog → create release tag → monitor

### new-hire-setup
Create accounts → set permissions → send welcome email → schedule onboarding

### incident-response
Check Sentry → check logs → notify channel → create Jira ticket → start investigation
