# Panda Skills

A unified intelligence layer for Claude Code. 16 skills that turn Claude from a chatbot into an autonomous development system with persistent memory, multi-model deliberation, and OODA-based reasoning.

## Install

```bash
git clone https://github.com/kkudumu/panda-skills.git ~/panda-skills
cd ~/panda-skills
./install.sh
```

That's it. The script symlinks everything into `~/.claude/skills/` where Claude Code discovers them. Run `install.sh` again after pulling updates or adding new skills.

To remove: `./uninstall.sh` (only removes symlinks, keeps your data).

## Usage

```
/panda [anything]          # The mind figures out what to do
/panda debug [problem]     # Deep debugging war room
/panda brainstorm [idea]   # Research-backed ideation
/panda execute [plan.md]   # Autonomous plan execution
/panda audit               # Wiring verification
/panda council [question]  # Claude + Codex + Gemini deliberation
/panda help                # Full menu
```

Or just describe what you need. Panda-mind reads your codebase state, checks past experiences, sizes the task, and picks the smallest correct move.

## How It Works

### The Mind (OODA Loop)

Every request goes through an Observe-Orient-Decide-Act loop:

1. **Observe** — Capture input, read session state, check git status
2. **Orient** — Load blackboard memory, retrieve relevant past experiences, scan available capabilities (15 skills + 14 MCP servers), assess codebase reality
3. **Decide** — Size complexity (micro/small/medium/large), pick execution strategy
4. **Act** — Execute directly or route to the right skill, then loop back

The Orient phase is where the intelligence lives. It doesn't match keywords — it reasons about context.

### Persistent Memory (Blackboard)

Three-tier knowledge store that makes the system smarter over time:

| Tier | What It Stores | When It's Read |
|------|---------------|----------------|
| `context.json` | Current task, recent decisions, user preferences | Every request |
| `experiences/*.json` | Cross-session learnings (one file per task) | During Orient, filtered by task type + tags |
| `patterns.json` | Promoted insights after 3+ confirming experiences | During Orient, matched to current situation |

Cold start works fine — the system operates at full capability with an empty blackboard and bootstraps memory aggressively during the first ~10 interactions.

### Complexity Sizing (ADaPT)

The mind always tries the simplest approach first:

| Size | Example | Strategy |
|------|---------|----------|
| **Micro** | Rename variable, fix typo | Just do it |
| **Small** | Add error handling, write a test | Do it + verify |
| **Medium** | Refactor a module, fix a multi-layer bug | Lightweight plan + execute |
| **Large** | Build a feature, implement a plan doc | Route to brainstorm or executor |

If simple fails, it escalates automatically.

## Skills

| Skill | What It Does |
|-------|-------------|
| **panda-mind** | OODA cognitive loop — default entry point for all freeform input |
| **panda-executor** | Autonomous plan execution with dynamically assembled agent teams |
| **panda-debug** | Multi-vector debugging war room with parallel hypothesis testing |
| **panda-brainstorm** | Socratic ideation with parallel web/GitHub research agents |
| **panda-audit** | Wiring verification — knip static analysis + adversarial LLM audit |
| **panda-council** | Multi-model deliberation — Claude, Codex, and Gemini debate to 2-of-3 consensus |
| **panda-codex-gate** | Adversarial Codex validation at executor wave boundaries |
| **panda-retro** | Post-execution retrospective + continuous micro-reflections (reflexion engine) |
| **panda-intent** | INTENT.md documentation layer — function-level contracts |
| **panda-diagram** | ARCHITECTURE.mmd mermaid diagrams — auto-updated after commits |
| **panda-browse** | Headless browser — screenshots, ARIA inspection, visual verification |
| **panda-git** | Secret scanning and credential safety gate for git operations |
| **panda-pause** | Save session state |
| **panda-resume** | Restore paused session |
| **panda-upgrade** | Self-upgrade from GitHub releases |
| **panda-config** | Configure model profiles and execution preferences |

### Event Mesh

Skills communicate through 18 typed events. Two are fast-path (always fire):
- `code_committed` → auto-triggers panda-intent + panda-diagram
- `task_completed` → auto-triggers micro-reflection

All other events are mediated by the mind based on context.

## Configuration

Copy `panda-config.default.yml` to `~/.claude/panda-config.yml` (install.sh does this automatically) and edit:

```yaml
profile: balanced    # quality | balanced | budget

profiles:
  balanced:
    planning: opus      # brainstorm, research
    execution: sonnet   # agent task implementation
    review: sonnet      # audit, debug review
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- For panda-council: [Codex CLI](https://github.com/openai/codex) + [Gemini CLI](https://github.com/google/gemini-cli)
- For panda-codex-gate: Codex CLI
- For panda-browse: Playwright (`npx @playwright/mcp@latest`)

## Research Foundations

The architecture draws from: SWE-Agent (ACI quality), OpenHands (event streams), Devin 2.0 (interactive planning), Reflexion (verbal RL — 50% to 91% on HumanEval), ADaPT (try simple first — +28%), Blackboard Architecture (shared knowledge store), MemGPT/Letta (tiered memory), and OODA loop theory.

## License

MIT
