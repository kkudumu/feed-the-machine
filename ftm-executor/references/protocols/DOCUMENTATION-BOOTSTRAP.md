# Phase 1.5 — Documentation Layer Bootstrap

## Purpose

Before dispatching any agents, ensure the project has the required documentation layer. This bootstrap runs once at the start of execution. If all files already exist, skip this phase entirely.

## Files to Check and Create

**1. INTENT.md** (project root)

If missing, bootstrap from the plan's Vision and Architecture Decisions sections. Use the ftm-intent skill's root template format.

**2. ARCHITECTURE.mmd** (project root)

If missing, bootstrap by scanning the codebase for modules and their import relationships. Use the ftm-diagram skill's root template format.

**3. STYLE.md** (project root)

If missing, copy from `~/.claude/skills/ftm-executor/references/STYLE-TEMPLATE.md` into the project root.

**4. DEBUG.md** (project root)

If missing, create with this header:

```markdown
# Debug Log

Failed approaches and their outcomes. Append here — never retry what's already logged.
```

## Bootstrap Rules

- Check all four files first, then create only the ones that are missing
- Do not overwrite existing files — presence check only
- Creation order: STYLE.md (copy) → DEBUG.md (header only) → INTENT.md (plan-derived) → ARCHITECTURE.mmd (scan-derived)
- Bootstrap content is minimal scaffolding — agents will expand it as they work
