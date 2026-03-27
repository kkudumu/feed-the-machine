# Test Quality Rating Rubrics

How to evaluate whether tests are actually useful — meaning they would catch real bugs, not just produce green checkmarks.

---

## Rating Scale

### STRONG
Tests cover happy path, error paths, edge cases, and boundary conditions. A bug introduced into this feature would likely be caught by the existing test suite.

**Indicators:**
- Tests for invalid/missing input (null, undefined, empty, wrong type)
- Tests for boundary values (0, -1, max, empty collection, single element)
- Tests for error conditions (network failure, timeout, bad response)
- Tests for state edge cases (concurrent access, race conditions, stale state)
- Assertions are specific (check exact values, not just truthiness)
- Mocks are realistic (match real API shapes and behaviors)

### ADEQUATE
Tests cover the main scenarios but miss some edge cases. Common bugs would be caught; subtle ones might slip through.

**Indicators:**
- Happy path tested with specific assertions
- Some error cases tested (but not exhaustive)
- Basic boundary testing (but missing some edge values)
- Mocks are reasonable (but might not cover all response shapes)

### WEAK
Tests exist but only cover the happy path. Most real-world bugs would NOT be caught.

**Indicators:**
- Only "it works" tests — call function, check it returns something
- Assertions use toBeTruthy/toBeDefined instead of specific value checks
- No error path testing
- No boundary condition testing
- Over-mocked — the test is really testing the mock, not the code
- Tests that would pass even if the implementation was fundamentally broken

### MISSING
No tests exist for this feature.

---

## Failure Mode Checklist

For each feature, check whether tests cover these categories:

### Input Validation
- [ ] Empty/null/undefined input
- [ ] Wrong type input (string where number expected, etc.)
- [ ] Oversized input (very long strings, huge arrays)
- [ ] Malformed input (invalid JSON, bad date format, SQL injection attempts)

### Boundary Conditions
- [ ] Zero / empty / single element
- [ ] Maximum values / overflow
- [ ] Off-by-one (first, last, one-past-end)
- [ ] Unicode / special characters

### Error Handling
- [ ] Network failure / timeout
- [ ] Permission denied / authentication failure
- [ ] Resource not found (404, missing file, missing DB record)
- [ ] Malformed response from dependency
- [ ] Dependency throws unexpected error

### State Management
- [ ] Initial state (before any interaction)
- [ ] State after error (does it recover?)
- [ ] Concurrent modifications (if applicable)
- [ ] State persistence (survives refresh/restart if expected)

### Integration Points
- [ ] API contract matches (request shape, response shape)
- [ ] Database queries return expected shapes
- [ ] Event handlers fire correctly
- [ ] Component renders with real (not mocked) data shapes

---

## Anti-Patterns to Flag

### Tautological Tests
```javascript
// BAD: This always passes regardless of implementation
test('should return result', () => {
  const result = doSomething();
  expect(result).toBeDefined();
});
```

### Mock-Everything Tests
```javascript
// BAD: Testing the mock, not the code
test('should call API', () => {
  const mockApi = jest.fn().mockResolvedValue({ data: [] });
  const result = fetchData(mockApi);
  expect(mockApi).toHaveBeenCalled(); // proves nothing about fetchData
});
```

### Implementation-Coupled Tests
```javascript
// BAD: Tests internal implementation, not behavior
test('should use Array.map', () => {
  const spy = jest.spyOn(Array.prototype, 'map');
  transform(data);
  expect(spy).toHaveBeenCalled();
});
```

### Snapshot Abuse
```javascript
// BAD: Snapshot of entire component output — any change triggers failure
// but you can't tell if the change is a bug or expected
test('renders correctly', () => {
  expect(render(<Component />)).toMatchSnapshot();
});
```

---

## Writing Good Remediation Tests

When writing tests to strengthen WEAK coverage, follow this pattern:

1. **Identify the failure mode** — what could go wrong in production?
2. **Write the test name as a sentence** — "should throw ValidationError when email is empty"
3. **Set up the failing condition** — provide the bad input or broken dependency
4. **Assert the specific expected behavior** — not just "doesn't crash" but "returns error X with message Y"
5. **Verify the test catches the bug** — mentally (or actually) remove the relevant code and confirm the test would fail

Every test you write should answer: "If someone introduced a bug here, would this test catch it?"
