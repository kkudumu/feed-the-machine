# Code Style — Optimized for AI Agents

> This file defines the code standards for this project. It is read by Codex during adversarial review
> and enforced automatically. Humans set it once; AI agents follow it on every commit.

## Hard Limits

| Rule | Limit | Rationale |
|---|---|---|
| Max lines per file | 1000 | Any AI agent can read one file and understand it without needing 10 others as context |
| Max lines per function | 50 | Trace a bug by following imports without blowing context window |
| Exports per component file | 1 (co-located helpers OK) | One responsibility per file, clear import targets |
| Barrel files (index.ts re-exports) | Forbidden | Direct imports only — barrel files obscure dependency graphs |

## Structure Rules

- **Naming over comments**: If a function needs a comment to explain what it does, it's named wrong
- **Max 3 nesting levels**: If a file has more than 3 levels of nesting, split it
- **Co-locate related functions**: If two functions always get called together, they should be in the same module
- **Max 5 dependencies per module**: If a module has 5+ imports from different modules, it's doing too much — split it

## Why These Rules

These aren't aesthetic preferences. They exist so any AI agent can:
- **Read one file** and understand it without needing 10 others as context
- **Trace a bug** by following imports without blowing context window
- **Modify one function** without risking side effects in a 5000-line file
- **Review changes** against INTENT.md without getting lost in complexity

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Files (components) | PascalCase | `UserProfile.tsx` |
| Files (utilities) | camelCase | `formatDate.ts` |
| Files (hooks) | camelCase with `use` prefix | `useAuth.ts` |
| Functions | camelCase | `validateInput()` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Types/Interfaces | PascalCase | `UserSession` |
| CSS classes | kebab-case | `.nav-container` |

## Error Handling

- **Fail fast, fail explicitly**: Detect and report errors immediately with meaningful context
- **Never suppress silently**: All errors must be logged, handled, or escalated
- **Context preservation**: Error messages include what was attempted, what failed, and where

## Testing Standards

- Tests live next to the code they test: `Component.test.tsx` alongside `Component.tsx`
- Test file names mirror source file names with `.test.` or `.spec.` suffix
- Each test file focuses on one module — no cross-module test files
- Mock data must match real API contracts (see project CLAUDE.md)

## Import Order

1. External packages (react, next, etc.)
2. Internal absolute imports (@/components, @/utils)
3. Relative imports (./Component, ../utils)
4. Type imports (import type { ... })
5. Style imports (import './styles.css')

Blank line between each group.

## Customization

This is a starting template. Projects should customize:
- **Naming conventions**: Adapt to your language/framework conventions
- **Hard limits**: Adjust thresholds if your domain requires longer functions (e.g., complex algorithms)
- **Testing standards**: Add framework-specific patterns (Jest, Vitest, pytest, etc.)
- **Import order**: Adapt to your project's module resolution strategy

When customizing, keep the "Why These Rules" section — it reminds both humans and AI agents why the constraints exist.
