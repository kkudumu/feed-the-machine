# Remediation Strategies by Finding Type

When ftm-verify finds issues, remediation agents use these strategies to fix them. Each strategy includes what to fix, how to verify the fix, and when to escalate instead.

---

## Plan Fulfillment Findings

### MISSING Feature
- **Fix**: Implement the feature following the plan's acceptance criteria and file list
- **Verify**: Run relevant tests, trace the code path from entry to output
- **Escalate if**: Feature requires architectural decisions not in the plan, or touches 10+ files

### PARTIAL Feature
- **Fix**: Identify the missing acceptance criteria and implement them
- **Verify**: Check each acceptance criterion individually
- **Escalate if**: The gap is ambiguous (plan says "handle errors" but doesn't specify which errors)

### DIVERGED Feature
- **Fix**: Do NOT auto-fix. Document the divergence in the report.
- **Rationale**: Divergence may be intentional (better approach found during implementation)
- **Escalate**: Always — user decides whether to align with plan or keep divergence

---

## Documentation Findings

### Missing INTENT.md Entry
- **Fix**: Read the function's code, write a Does/Why/Relationships/Decisions entry
- **Verify**: Cross-check "Relationships" field against actual imports/callers (grep)
- **Template**:
  ```markdown
  ### `functionName` — module/file.ts
  - **Does**: [what the function actually does, based on reading the code]
  - **Why**: [business reason or technical motivation]
  - **Relationships**: Called by [X], calls [Y], depends on [Z]
  - **Decisions**: [any non-obvious choices in the implementation]
  ```

### Stale INTENT.md Entry
- **Fix**: Update the entry to match current code behavior
- **Verify**: Re-read the function and confirm the entry is accurate
- **Key rule**: Match CODE, not plan. If implementation differs from plan, document what was built.

### Missing Module in ARCHITECTURE.mmd
- **Fix**: Add a node for the module and edges for its dependencies
- **Verify**: Grep for actual import relationships to confirm edges are real

### Phantom Module in ARCHITECTURE.mmd
- **Fix**: Remove the node and its edges from the diagram
- **Verify**: Confirm the module/directory doesn't exist

### Missing Module INTENT.md or DIAGRAM.mmd
- **Fix**: Create the file following the standard templates (see ftm-intent and ftm-diagram skills)
- **Verify**: Ensure all functions in the module have entries

### Stale PROGRESS.md
- **Fix**: Update task statuses to match actual completion state
- **Verify**: Cross-reference with plan fulfillment results

---

## Build & Compile Findings

### Type Errors
- **Fix**: Read the error, fix the type annotation or value
- **Verify**: Re-run type checker, confirm zero errors
- **Escalate if**: Fix requires changing a shared type definition that affects 5+ files

### Lint Errors
- **Fix**: Apply the linter's suggested fix, or fix manually
- **Verify**: Re-run linter on the affected file
- **Escalate if**: Lint rule conflicts with project conventions

### Missing Dependencies
- **Fix**: Install the dependency (`npm install <pkg>` or equivalent)
- **Verify**: Re-run dependency resolution

### Build Failures
- **Fix**: Read the error output, fix the root cause
- **Verify**: Re-run the full build
- **Escalate if**: Build failure is in code not touched by this execution

---

## Test Quality Findings

### MISSING Tests
- **Fix**: Write test files covering the feature's acceptance criteria
- **Priority order**:
  1. Error/failure paths (what breaks?)
  2. Boundary conditions (edge cases)
  3. Happy path (basic functionality)
  4. Integration points (does it work with real dependencies?)
- **Verify**: Run the new tests, confirm they pass AND that they would fail if the feature was broken (mutation testing mindset)

### WEAK Tests (happy path only)
- **Fix**: Add test cases for:
  - Invalid input (null, undefined, empty, wrong type)
  - Boundary values (0, -1, MAX_INT, empty array, single element)
  - Error conditions (network failure, timeout, permission denied)
  - State transitions (intermediate states, invalid transitions)
- **Verify**: Each new test must fail when the relevant code is commented out or broken

### Tautological Tests
- **Fix**: Replace weak assertions with specific ones
  - `expect(result).toBeTruthy()` → `expect(result.name).toBe("expected_value")`
  - `expect(fn).not.toThrow()` → `expect(fn()).toEqual(expected_output)`
- **Verify**: Assertion would fail if the return value changed to something wrong

### Over-Mocked Tests
- **Fix**: Replace mocks with real implementations where feasible, or use realistic mock data shapes
- **Verify**: Mock data matches the actual API/function contract

---

## Wiring Findings

### Orphaned File (not imported)
- **Fix**: Add import from the appropriate parent module (check plan for intended consumer)
- **Verify**: Trace import chain from entry point to the file
- **Escalate if**: No clear parent — file might be intentionally standalone

### Orphaned Component (imported but not rendered)
- **Fix**: Add JSX rendering in the parent component
- **Verify**: Check that the component appears in the parent's render output
- **Escalate if**: Placement is ambiguous (where in the parent's JSX?)

### Orphaned Route (no route config)
- **Fix**: Add route entry to router config, infer path from component name
- **Verify**: Check route is accessible, optionally add nav link
- **Escalate if**: Route path is ambiguous

### Dead Export (nobody imports)
- **Fix**: If plan calls for this export to be used, wire it in. If truly dead, remove the export.
- **Verify**: Re-run knip or grep for the export name
- **Escalate if**: Export might be part of a public API

### Dead Store Field (written but never read)
- **Fix**: If plan calls for this field to be consumed, add the selector/hook usage. If dead, remove.
- **Verify**: Grep for reads of the field
- **Escalate if**: Store design decision needed

---

## General Remediation Rules

1. **Max 3 attempts per finding** — if you can't fix it in 3 tries, flag for manual intervention
2. **One commit per finding** — tagged with `fix(verify):` prefix for easy identification and revert
3. **No scope creep** — fix exactly what's flagged, nothing else
4. **Verify before committing** — never commit a fix you haven't tested
5. **Revert on regression** — if a fix breaks something else, revert immediately
