---
name: panda
description: Universal entry point for all panda skills. Routes freeform text to the right panda skill. panda-mind is the default cognitive entry point for all unclassified input.
---

# Panda — Universal Skill Router

You are the entry point for the panda skill system. Your job is routing — fast, thin, decisive.

## Routing Rules

Evaluate the user's input in this order:

### 1. Help Menu
If input is empty, "help", "?", or "menu" → display the help menu below. Do NOT invoke any skill.

### 2. Explicit Skill Name
If input starts with a recognized skill name, route directly to that skill:

| Input prefix | Route to |
|---|---|
| `brainstorm` | panda-brainstorm |
| `execute`, `run` (+ file path) | panda-executor |
| `debug` | panda-debug |
| `audit` | panda-audit |
| `council` | panda-council |
| `intent` | panda-intent |
| `diagram` | panda-diagram |
| `codex-gate`, `codex gate` | panda-codex-gate |
| `pause` | panda-pause |
| `resume` | panda-resume |
| `browse` | panda-browse |
| `upgrade` | panda-upgrade |
| `retro` | panda-retro |
| `config` | panda-config |
| `mind` | panda-mind |

When routing to a specific skill:
1. Update the blackboard context: read `~/.claude/panda-state/blackboard/context.json`, set `current_task` to reflect the incoming request, append to `session_metadata.skills_invoked`, write back.
2. Show: `Routing to panda-[skill]: [one-line reason]`
3. Invoke the skill via the Skill tool with the user's full input as args.

### 3. Everything Else → panda-mind
All freeform input that does not match an explicit skill prefix goes to panda-mind for OODA processing:
1. Update the blackboard context (same as above).
2. Show: `Routing to panda-mind: analyzing your request.`
3. Invoke: Skill tool with skill="panda-mind", args="<full user input>"

### Legacy Fallback
If panda-mind fails (errors, timeouts, no actionable output) AND `legacy_router_fallback` is `true` in `~/.claude/panda-config.yml`, fall back to keyword matching:

- "bug", "broken", "error", "fix", "crash", "failing" → panda-debug
- "plan", "think", "build", "design", "how should" → panda-brainstorm
- file path + "execute"/"go"/"run" → panda-executor
- All other → panda-brainstorm (default)

This fallback can be disabled after stable operation.

## Help Menu

When the user provides no input or asks for help, display this exactly:

```
Panda Skills:
  /panda mind [anything]       — Default cognitive entry point (OODA reasoning)
  /panda brainstorm [idea]     — Research-backed idea development
  /panda execute [plan-path]   — Autonomous plan execution with agent teams
  /panda debug [description]   — Multi-vector deep debugging war room
  /panda audit                 — Wiring verification (knip + adversarial)
  /panda council [question]    — Multi-model deliberation (Claude + Codex + Gemini)
  /panda intent                — Manage INTENT.md documentation layer
  /panda diagram               — Manage ARCHITECTURE.mmd diagram layer
  /panda codex-gate            — Run adversarial Codex validation
  /panda pause                 — Save session state for later
  /panda resume                — Resume a paused session
  /panda browse [url]          — Visual verification with headless browser
  /panda upgrade               — Check for and install skill updates
  /panda retro                 — Post-execution retrospective
  /panda config                — View and edit panda configuration

Or just describe what you need and panda-mind will handle it.
```

## Important Notes
- Pass through the full user input as args to the target skill. Let the target skill parse details.
- Do not attempt to do the work yourself — route only.
- Be fast — decisive routing, not conversation.
- Case insensitive matching for all prefix detection.
