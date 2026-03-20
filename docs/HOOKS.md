# FTM Hooks — Programmatic Guardrails

Hooks are shell scripts that run at specific points in Claude Code's lifecycle. Unlike skill instructions (which the model can rationalize past), hooks execute as real programs and can block actions, inject reminders, or enforce workflows.

## Installation

Hooks are installed automatically by `install.sh` into `~/.claude/hooks/`. To activate them, you need to add the hook configuration to your `~/.claude/settings.json`.

**Option A: Automatic (recommended)**
```bash
./install.sh --setup-hooks
```
This merges the FTM hook entries into your existing settings.json without overwriting your other configuration.

**Option B: Manual**
Copy the entries from `hooks/settings-template.json` into the `hooks` section of your `~/.claude/settings.json`.

## Hook Lifecycle

```
User types prompt
  └→ UserPromptSubmit hooks fire
  │    ├─ ftm-discovery-reminder.sh (nudge for external system work)
  │    ├─ ftm-pending-sync-check.sh (detect out-of-session commits)
  │    └─ ftm-map-autodetect.sh (detect unmapped projects)
  └→ Claude processes prompt
      └→ PreToolUse hooks fire before each tool
      │    ├─ ftm-plan-gate.sh (block edits without a plan)
      │    └─ ftm-drafts-gate.sh (block sends without a draft)
      └→ Tool executes
          └→ PostToolUse hooks fire after each tool
          │    ├─ ftm-event-logger.mjs (log tool use for analytics)
          │    └─ ftm-post-commit-trigger.sh (sync map + docs on commit)
          └→ Claude finishes response
              └→ Stop hook fires
                   └─ ftm-blackboard-enforcer.sh (enforce experience recording)
```

## Hooks Reference

### PreToolUse Hooks

These fire **before** a tool executes. They can inject context (nudges) or block the tool call.

---

#### ftm-plan-gate.sh

**Event:** PreToolUse | **Matcher:** `Edit|Write`

Prevents Claude from grinding through file edits without presenting a plan first. Tracks edit count per session — soft reminder on edits 1-2, escalated warning on 3+.

**How it works:**
- Checks for a plan marker at `~/.claude/ftm-state/.plan-presented`
- If no marker exists and edits are happening, injects context telling Claude to stop and plan
- Claude creates the marker after presenting a plan to the user

**Bypasses (always allowed):**
- Skill files (`~/.claude/skills/`)
- FTM state files (`~/.claude/ftm-state/`)
- Drafts (`.ftm-drafts/`)
- Documentation files (INTENT.md, ARCHITECTURE.mmd, STYLE.md, DEBUG.md, CLAUDE.md, .gitignore)

**State files:**
- `~/.claude/ftm-state/.plan-presented` — session ID marker
- `~/.claude/ftm-state/.edit-count` — edit counter per session

---

#### ftm-drafts-gate.sh

**Event:** PreToolUse | **Matcher:** `mcp__slack__slack_post_message|mcp__slack__slack_reply_to_thread|mcp__gmail__send_email`

Hard-blocks outbound messages unless a draft was saved to `.ftm-drafts/` in the last 30 minutes. Creates an audit trail of all messages Claude drafts on your behalf.

**How it works:**
- Checks for `.md` files modified in the last 30 minutes in:
  - `<project>/.ftm-drafts/` (project-level)
  - `~/.claude/ftm-drafts/` (global fallback)
- If no recent draft found: returns `permissionDecision: deny`
- If draft exists: allows through

**Pairs with:** ftm-mind section 3.5 (draft-before-send protocol)

---

### UserPromptSubmit Hooks

These fire when you press Enter on a prompt, **before** Claude sees it. They inject `additionalContext` that influences Claude's response.

---

#### ftm-discovery-reminder.sh

**Event:** UserPromptSubmit

Detects when a prompt involves external systems or stakeholder coordination and injects a reminder about the discovery interview before Claude starts work.

**Trigger patterns:**
- System changes: reroute, migrate, update integration, change endpoint, switch from/to
- Coordination: draft message, notify about, check with, coordinate with
- Workflow changes: jira automation, freshservice automation, update workflow

**Skip signals (no reminder injected):**
- "just do it", "no questions", "skip the interview"
- "here's the slack thread", "per the conversation"

**Pairs with:** ftm-mind Orient section 10 (Discovery Interview)

---

#### ftm-pending-sync-check.sh

**Event:** UserPromptSubmit

Checks for commits made outside of Claude sessions (e.g., you pushed from the terminal or another tool). If pending syncs exist, injects a reminder to run ftm-map incremental on those files.

**How it works:**
- Reads `~/.claude/ftm-state/.pending-commit-syncs`
- If the file exists and has entries, injects context with the list
- Consumes the file on read — only fires once per batch

**State files:**
- `~/.claude/ftm-state/.pending-commit-syncs` — written by external git hooks or CI

---

#### ftm-map-autodetect.sh

**Event:** UserPromptSubmit

Detects when you invoke any FTM skill in a project that hasn't been indexed by ftm-map yet. Classifies the project and injects bootstrap instructions.

**Classification:**

| Type | Criteria |
|---|---|
| Greenfield | ≤5 source files, ≤3 commits |
| Small brownfield | ≤50 source files |
| Medium brownfield | ≤200 source files |
| Large brownfield | 200+ source files |

**One-shot behavior:** Writes `.ftm-map/.offered` so it only fires **once per project**. Delete the marker to re-trigger.

**Trigger keywords:** `/ftm`, `ftm-`, `brainstorm`, `research`, `debug this`, `audit`, `deep dive`, `investigate`

---

### PostToolUse Hooks

These fire **after** a tool executes. They observe what happened and react.

---

#### ftm-event-logger.mjs

**Event:** PostToolUse | **Matcher:** (all tools — empty matcher)

Logs tool use to `~/.claude/ftm-state/events.log` as structured JSONL. This is the data source for `/ftm-dashboard`.

**Performance:**
- Debounced — only fires every 3rd tool use
- Auto-rotates logs older than 30 days into `~/.claude/ftm-state/event-archives/`

**Requires:** Node.js (runs as `node ~/.claude/hooks/ftm-event-logger.mjs`)

---

#### ftm-post-commit-trigger.sh

**Event:** PostToolUse | **Matcher:** `Bash|mcp__git__git_commit`

Detects git commits and triggers the documentation sync chain. Only fires if the project has been indexed by ftm-map (`.ftm-map/map.db` exists).

**Injects instructions to:**
1. Run ftm-map incremental on changed files
2. Update INTENT.md via ftm-intent
3. Update ARCHITECTURE.mmd via ftm-diagram

This is what keeps the documentation layer in sync with code changes automatically.

---

### Stop Hooks

These fire when Claude finishes responding (before the next user prompt).

---

#### ftm-blackboard-enforcer.sh

**Event:** Stop

Prevents Claude from ending a session without recording what it learned to the blackboard. If meaningful work was done (3+ edits or FTM skills invoked) but no experience was recorded, blocks the stop.

**How it works:**
- Checks edit counter and `context.json` for skills_invoked
- If meaningful work detected, checks for today's experience files
- If no experience recorded: blocks stop with instructions to write the blackboard
- Has infinite-loop guard via `stop_hook_active` check

**State files checked:**
- `~/.claude/ftm-state/.edit-count`
- `~/.claude/ftm-state/blackboard/context.json`
- `~/.claude/ftm-state/blackboard/experiences/` (looks for today's files)

---

## Dependencies

All shell hooks require `jq` for JSON parsing. The event logger requires Node.js.

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

## Troubleshooting

**Hook not firing:**
- Check it's in `~/.claude/settings.json` under the correct event key
- Check the script is executable: `chmod +x ~/.claude/hooks/ftm-*.sh`
- Check the matcher regex matches the tool name exactly

**Hook blocking unexpectedly:**
- Plan gate: `rm ~/.claude/ftm-state/.plan-presented` to reset
- Map autodetect: `rm .ftm-map/.offered` to re-trigger
- Blackboard enforcer: has built-in infinite-loop guard

**Testing a hook manually:**
```bash
# Test plan gate
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test.py"}}' | ~/.claude/hooks/ftm-plan-gate.sh

# Test map autodetect
echo '{"prompt":"/ftm brainstorm auth design"}' | ~/.claude/hooks/ftm-map-autodetect.sh

# Test post-commit trigger
echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' | ~/.claude/hooks/ftm-post-commit-trigger.sh
```
