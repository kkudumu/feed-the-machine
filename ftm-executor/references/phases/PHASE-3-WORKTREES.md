# Phase 3 — Worktree Setup

## Per-Agent Worktree Creation

Each agent in the current wave gets its own isolated worktree. Run these steps for every agent before dispatch:

**1. Ensure `.worktrees/` is in `.gitignore`**

Check the project's `.gitignore`. If `.worktrees/` is missing, add it before creating any worktrees.

**2. Create the worktree branch and directory**

```bash
git worktree add .worktrees/plan-exec-<agent-name> -b plan-exec/<agent-name>
```

Example for frontend agent handling tasks 1–4:
```bash
git worktree add .worktrees/plan-exec-frontend-tasks-1-4 -b plan-exec/frontend-tasks-1-4
```

**3. Run project setup in the worktree**

```bash
cd .worktrees/plan-exec-<agent-name>
npm install   # or yarn install / pip install / etc.
```

**4. Verify the worktree starts clean**

Run the test suite or at minimum the build. If the baseline is already failing, note it before dispatch so the agent doesn't get blamed for pre-existing failures.

## Naming Convention

Branch names: `plan-exec/<agent-name>`
Worktree paths: `.worktrees/plan-exec-<agent-name>`

Use the agent's role as the name component — e.g., `frontend`, `backend`, `testing`, `devops`. For waves with multiple agents of the same type, append a task range: `frontend-tasks-1-4`.
