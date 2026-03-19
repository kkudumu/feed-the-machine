# Prerequisites: Tool Availability Checks

## Required CLI Tools

The council requires both external CLI tools to be installed and authenticated:

- **Codex**: `npm install -g @openai/codex` (authenticated via `codex login`)
- **Gemini**: `npm install -g @google/gemini-cli` (authenticated via Google)

## Availability Check

Before the first round, verify both tools are available:

```bash
which codex && which gemini
```

## Fallback Logic

| Scenario | Action |
|---|---|
| Both tools missing | Tell the user what to install and stop — don't attempt a degraded council |
| One tool missing | Report which tool is missing. A 2-model debate loses the tiebreaker benefit — ask the user if they want to proceed or install the missing tool first |
| Auth failure at runtime | Report the error to the user. Continue with the remaining models. A 2-model debate is better than nothing |
| Rate limit or sandbox error at runtime | Report the error. Continue with the remaining models |

**Do not silently proceed with a degraded council.** Always tell the user which tool is unavailable and why. The tiebreaker value of a 3-model council is significant for close decisions.

## Runtime Timeout Configuration

Set timeouts per round type:

- **Round 1 (Independent Research)**: 300s (5 minutes) — models are reading files and searching code
- **Rebuttal rounds (2-5)**: 180s — less exploration, more focused follow-up

If one model times out in any round, report it and continue with the other two.

## Working Directory

Make sure both CLI tools run from the same working directory as the current session. This ensures all models look at the same codebase.

Pass `cd {cwd} &&` before CLI commands if needed:

```bash
cd /path/to/project && codex exec --full-auto "..."
cd /path/to/project && gemini -p "..." --yolo
```
