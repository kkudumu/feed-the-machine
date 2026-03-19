# Phase 2 — Agent Assembly

## Matching Domain Clusters to Agents

For each domain cluster identified in Phase 1, select the best-fit agent from the table below:

| Domain | Likely Agent |
|--------|-------------|
| React/UI/CSS/components | frontend-developer |
| API/server/database | backend-architect |
| CI/CD/deploy/infra | devops-automator |
| Tests/coverage | test-writer-fixer |
| Mobile/native | mobile-app-builder |
| AI/ML features | ai-engineer |
| General coding | general-purpose |

Check available agent types in the Agent tool. Map each cluster to the closest fit before considering custom creation.

## Creating Custom Agents

When no existing agent covers a task cluster adequately — for example, "theme system with CSS custom properties and dark mode" or "WebSocket terminal integration" — create a purpose-built agent prompt.

Write a focused agent definition with these sections:

- **Domain expertise**: What this agent knows deeply
- **Task context**: The specific tasks from the plan it will handle
- **Standards**: Coding conventions from the project (infer from existing code)
- **Constraints**: Don't touch files outside your scope

The prompt text becomes the `prompt` parameter when spawning the agent in Phase 4.

## Building the Agent Library

Store custom agent prompts in the skill workspace as reference prompts so they can be reused across projects. A "theme-engineer" agent created for one project's CSS system can be reused next time themes come up. Over time, the agent library grows with battle-tested specialists.
