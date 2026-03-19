# Auto-Fix Strategies

Layer 3 applies fixes for each finding type, re-verifies, and produces a changelog. This document defines the fix strategy for each finding type and when to skip auto-fix.

---

## Fix Strategies by Finding Type

| Finding Type | Fix Strategy | Fallback |
|---|---|---|
| `UNUSED_FILE` | If created by the current task, add import from the appropriate parent module. If pre-existing dead code, flag for removal. | Flag for manual review — might be intentionally standalone (config, script) |
| `UNUSED_EXPORT` | If another module should consume it (check wiring contract), add the import. If truly unnecessary, remove the export keyword. | Flag for manual review |
| `UNWIRED_COMPONENT` | Add `<ComponentName />` to the parent component's JSX return. Determine placement from component name and parent structure. | Flag — can't determine correct placement |
| `ORPHAN_ROUTE` | Add route entry to the router config. Infer path from component name (e.g., `SettingsView` → `/settings`). Add nav link to sidebar/navbar if one exists. | Flag — route path ambiguous |
| `DEAD_STORE_FIELD` | If a component should read this field (check wiring contract), add the selector/hook usage. If truly unused, remove the field. | Flag — store design decision needed |
| `UNCALLED_API` | If a hook or component should call this (check wiring contract), add the invocation. If truly unused, remove the function. | Flag — API integration decision needed |
| `UNUSED_DEP` | Remove from `package.json` `dependencies` or `devDependencies`. | Flag if it might be used in scripts, config files, or CLI |
| `UNLISTED_DEP` | Run `npm install <package>` (or appropriate package manager command). | Flag if the import might be wrong |

---

## Fix Protocol

For each finding, follow this sequence:

1. **Report** — Log the finding with type, file:line, and evidence
2. **Determine fix** — Match finding type to fix strategy above. Check wiring contract for WHERE to wire, if available.
3. **Show proposed fix** — Display the exact code change before applying:
   ```
   FIX: [UNWIRED_COMPONENT] NewWidget in Dashboard.tsx
   Proposed: Add <NewWidget /> to Dashboard.tsx return JSX after line 45
   ```
4. **Apply fix** — Use Edit tool to make the change
5. **Re-verify** — Run the specific check that found the issue:
   - For knip findings: re-run `npx knip --reporter json`
   - For adversarial findings: re-trace the specific wiring dimension
6. **Log to changelog** — Record: timestamp, finding, fix applied, verification result

---

## When Auto-Fix Is Not Safe

Some findings cannot be auto-fixed without risking incorrect behavior:

- **Ambiguous placement** — cannot determine where exactly in a component the new element should render
- **Design decision needed** — whether a store field should exist at all requires product judgment
- **Cross-cutting changes** — fix requires modifying 5+ files simultaneously
- **Test-only code** — might be intentionally not wired into the app

For these, flag clearly:

```
MANUAL_INTERVENTION_NEEDED:
- [ORPHAN_ROUTE] src/views/AdminPanel.tsx — cannot determine route path or nav placement
  Suggested action: Add route to router config and nav link to sidebar
  Reason auto-fix skipped: Multiple possible route paths (/admin, /settings/admin, /dashboard/admin)
```

---

## Re-Verification Loop

After all auto-fixes are applied:

1. Re-run Layer 1 (knip) — confirm no new unused code introduced by fixes
2. Re-run Layer 2 (adversarial audit on the fix diff) — confirm fixes actually wire correctly
3. If re-verification finds new issues, fix those too

**Loop limit:** Maximum 3 iterations to prevent infinite fix cycles. If issues persist after 3 iterations, stop and flag all remaining issues for manual intervention with a note explaining the loop was capped.
