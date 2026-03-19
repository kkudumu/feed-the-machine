# Runtime Wiring Verification

Phase 3 of the audit: verify that components and routes that passed static analysis actually render in the running application. Catches bugs static analysis cannot detect.

---

## Prerequisites

This phase runs only when ALL of the following conditions are met:

1. The ftm-browse binary exists at `$HOME/.claude/skills/ftm-browse/bin/ftm-browse`
2. A dev server is running — detected via:
   - `lsof -i :3000` (Create React App, Next.js default)
   - `lsof -i :5173` (Vite default)
   - `lsof -i :8080` (various)
3. The wiring contracts for the audited tasks include at least one `route_path` entry

If any prerequisite is not met, skip this phase and log: `Phase 3 (Runtime Wiring) skipped — [reason: no browse binary | no dev server | no route_path in contracts]`. Do NOT fail the overall audit.

---

## Process

For each wiring contract that includes a `route_path`:

1. **Navigate** — `$PB goto <dev_server_url><route_path>`
2. **Snapshot** — `$PB snapshot -i` to get the ARIA tree of interactive elements
3. **Verify components render** — Check that expected components from the wiring contract appear in the ARIA tree:
   - Expected buttons, links, inputs by their labels/roles
   - Expected headings and landmarks
   - Expected form fields
4. **Screenshot** — `$PB screenshot` as evidence of the render state
5. **Report findings:**
   - `PASS` — All expected components found in ARIA tree
   - `WARN` — Page renders but some expected components are missing
   - `FAIL` — Page doesn't render (blank, error page, 404)

Where `$PB` is `$HOME/.claude/skills/ftm-browse/bin/ftm-browse`.

---

## What Runtime Wiring Catches

Static analysis (Layers 1-2) cannot detect these failure modes:

| Failure Mode | Example | Detection |
|---|---|---|
| Conditional render always false | `{isAdmin && <AdminPanel />}` where `isAdmin` is hardcoded `false` | Component missing from ARIA tree |
| Component crashes on mount | Runtime error in `useEffect` causes blank render | Error page or blank instead of expected content |
| CSS visibility hidden | `display: none` or `visibility: hidden` | Component in ARIA tree but not visually accessible |
| Server-side data dependency fails | `getServerSideProps` throws → component in error state | Error boundary rendered instead of component |
| Route registered but redirects | Route exists in config but always redirects away | Final URL differs from expected `route_path` |

These are flagged as **runtime-only findings** in the audit report if found after Layers 1-2 both passed.

---

## Integration with Layers 1-2

Runtime wiring is additive — it extends static analysis, not replaces it. The layer execution order is:

```
Layer 1 (knip) → Layer 2 (adversarial) → Layer 3 (auto-fix) → Phase 3 (runtime, if prerequisites met)
```

Runtime findings that survive after Layers 1-2 are clean represent genuine runtime-only bugs. Flag them separately so the developer knows they cannot be caught by future static checks alone.
