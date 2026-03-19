# Wiring Contracts

A wiring contract is a YAML block in a plan task that declares the expected wiring for code produced by that task. It tells panda-audit exactly what to verify — instead of guessing, the audit checks specific expectations.

**Graceful degradation:**
- Full contract → audit checks every declared wire
- Partial contract → audit checks what's declared, uses heuristics for the rest
- No contract → audit falls back to pure Layer 1 + Layer 2 analysis

---

## Schema

```yaml
Wiring:
  exports:
    - symbol: ComponentName          # What's being exported
      from: src/components/Thing.tsx  # From which file

  imported_by:
    - file: src/views/Dashboard.tsx   # Which file should import it
      line_hint: "import section"     # Approximate location (optional)

  rendered_in:                        # For React components
    - parent: Dashboard               # Parent component name
      placement: "main content area"  # Where in the JSX (descriptive)

  route_path: /dashboard/thing        # For routed views (optional)

  nav_link:                           # For views that need navigation (optional)
    - location: sidebar               # Where the nav link goes
      label: "Thing"                  # Display text

  store_reads:                        # Store fields this code reads (optional)
    - store: useAppStore
      field: user.preferences

  store_writes:                       # Store fields this code writes (optional)
    - store: useAppStore
      field: user.preferences
      action: setPreferences

  api_calls:                          # API functions this code invokes (optional)
    - function: fetchUserPrefs
      from: src/api/user.ts
```

All fields are optional. Include only the dimensions relevant to the task.

---

## Contract Examples

### React Component

```yaml
### Task 3: Build UserPreferences component
**Files:** Create src/components/UserPreferences.tsx
**Wiring:**
  exports:
    - symbol: UserPreferences
      from: src/components/UserPreferences.tsx
  imported_by:
    - file: src/views/SettingsView.tsx
  rendered_in:
    - parent: SettingsView
      placement: "below profile section"
  store_reads:
    - store: useAppStore
      field: user.preferences
  api_calls:
    - function: updatePreferences
      from: src/api/user.ts
```

### API Client Functions

```yaml
### Task 5: Add billing API functions
**Files:** Create src/api/billing.ts
**Wiring:**
  exports:
    - symbol: fetchInvoices
      from: src/api/billing.ts
    - symbol: createSubscription
      from: src/api/billing.ts
  imported_by:
    - file: src/hooks/useBilling.ts
  api_calls: []  # These ARE the API functions — nothing to call downstream
```

### New Route/View

```yaml
### Task 7: Build AnalyticsDashboard view
**Files:** Create src/views/AnalyticsDashboard.tsx
**Wiring:**
  exports:
    - symbol: AnalyticsDashboard
      from: src/views/AnalyticsDashboard.tsx
  imported_by:
    - file: src/router.tsx
  rendered_in:
    - parent: RouterConfig
      placement: "route element"
  route_path: /analytics
  nav_link:
    - location: sidebar
      label: "Analytics"
      icon: BarChart
  store_reads:
    - store: useAppStore
      field: analytics.dateRange
```

---

## Verification Checks

For each field in the wiring contract, audit runs the corresponding check:

| Field | Check | Method |
|---|---|---|
| `exports` | Symbol exists as named export in specified file | `grep "export.*SymbolName"` or AST check |
| `imported_by` | Importing file contains the import statement | Check for `import { Symbol } from './path'` |
| `rendered_in` | Parent component's JSX contains `<Symbol` | Search JSX/TSX return statements |
| `route_path` | Router config contains route pointing to this component | Search router config file |
| `nav_link` | Navigation component has link with matching label and path | Search sidebar/navbar file |
| `store_reads` | Selector/hook call reads this field in the component | Search for selector usage |
| `store_writes` | Dispatch/action call writes this field | Search for action dispatch |
| `api_calls` | Function is imported and called in component or its hooks | Search for call sites |

Each check produces: `✅ VERIFIED file:line` or `❌ NOT FOUND — [what was expected] [where it was expected]`

**Rendering special cases:** Lazy imports (`React.lazy(() => import(...))`), conditional rendering (`{condition && <Component/>}`), render props, and HOCs all count as valid rendering for Dimension 2.
