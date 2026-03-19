# Phase 1: Parallel Investigation (the war room)

Launch all investigation agents **simultaneously**. This is the core value — attacking from every angle at once.

## Agent Selection Guide

Not every bug needs all agents. Here's when to scale down:

| Bug Type | Skip These | Keep These |
|----------|-----------|------------|
| Pure logic error (wrong output) | Instrumenter | Researcher, Reproducer, Hypothesizer, Solver, Reviewer |
| Race condition / timing | — (use all) | All — timing bugs are the hardest |
| Known library bug (error message is googleable) | Hypothesizer | Researcher (primary), Solver, Reviewer |
| UI rendering glitch | Researcher (maybe) | Instrumenter (critical), Reproducer, Hypothesizer, Solver, Reviewer (with visual verification!) |
| Terminal/CLI visual output | Researcher (maybe) | Instrumenter, Reproducer, Hypothesizer, Solver, Reviewer (with visual verification!) |
| Build / config issue | Reproducer | Researcher (check migration guides), Hypothesizer, Solver, Reviewer |
| Intermittent / flaky | — (use all) | All — flaky bugs need every angle |
| Performance regression | Researcher | Instrumenter (profiling), Reproducer (benchmark), Hypothesizer, Solver, Reviewer |

When in doubt, use all of them. The cost of a redundant agent is some compute time. The cost of missing the right angle is another hour of debugging.

## Worktree Strategy

Every agent that makes code changes gets its own worktree:

```
.worktrees/
  debug-instrumentation/     (Instrumenter's logging)
  debug-reproduction/        (Reproducer's test cases)
  debug-fix/                 (Solver's fix attempts)
```

Branch naming: `debug/<problem-slug>/<agent-role>`

Example: `debug/esm-crash/instrumentation`, `debug/esm-crash/fix`

This means:
- Every experiment is isolated and can be kept or discarded
- The Solver can have multiple fix attempts on separate branches
- The Reproducer's test stays clean from fix changes
- You can diff any agent's work against main to see exactly what they did
- **Commit after every meaningful change** — if a fix attempt fails, the commit history shows exactly what was tried

Ensure `.worktrees/` is in `.gitignore`.

After the fix is approved and merged, clean up all debug worktrees and branches.
