# Phase 0.7 — Model Profile Loading

## Reading ftm-config.yml

Read `~/.codex/ftm-config.yml` to determine which models to use when spawning agents. If the file doesn't exist, use these balanced defaults:

| Role | Default Model |
|------|--------------|
| Planning agents | opus |
| Execution agents | sonnet |
| Review/audit agents | sonnet |

## Model Assignment by Phase

When spawning agents in subsequent phases, pass the `model` parameter based on role:

| Phase | Agent Role | Model Key |
|-------|-----------|-----------|
| Phase 0.5 (plan checking) | Planning | `planning` |
| Phase 2 (team assembly) | Planning | `planning` |
| Phase 4 (task execution) | Execution | `execution` |
| Phase 4.5 (audit) | Review | `review` |

If the profile specifies `inherit` for a role, omit the `model` parameter entirely — the agent uses the session default.

## Example ftm-config.yml Structure

```yaml
active_profile: balanced

profiles:
  balanced:
    planning: opus
    execution: sonnet
    review: sonnet
  fast:
    planning: sonnet
    execution: sonnet
    review: sonnet
  quality:
    planning: opus
    execution: opus
    review: opus
```
