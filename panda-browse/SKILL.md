---
name: panda-browse
description: Headless browser daemon for visual verification and web interaction. Gives agents the ability to navigate, screenshot, click, fill forms, and inspect ARIA trees via CLI commands. Use when user says "browse", "screenshot", "visual", "look at the app", "open browser", "check the page", "navigate to", "take a screenshot", "visual verification".
---

## Events

### Emits
- `task_completed` — when a visual verification or interaction workflow finishes successfully

### Listens To
(none — panda-browse is invoked on demand and does not respond to events)

# panda-browse

panda-browse is a persistent headless Chromium daemon controlled via a CLI binary at `~/.claude/skills/panda-browse/bin/panda-browse`. Each CLI invocation communicates with the daemon over a local HTTP server (bearer-auth, random port), so the browser stays alive across commands without the per-invocation startup penalty. The daemon auto-starts on first use and shuts itself down after 30 minutes of idle. This CLI-to-HTTP model is 4x more token-efficient than driving Playwright MCP directly, because tool calls remain terse and outputs are structured JSON rather than raw browser protocol noise.

---

## Setup

**First run — install the browser engine:**

```bash
npx playwright install chromium
```

**Define the alias in any shell session before use:**

```bash
PB="$HOME/.claude/skills/panda-browse/bin/panda-browse"
```

**Verify the installation:**

```bash
$PB goto https://example.com && $PB screenshot
```

The first `goto` command will start the daemon (up to 10 seconds for cold start). All subsequent commands respond in ~100ms because the browser process stays alive.

---

## Command Reference

### WRITE commands — state-mutating

These commands change browser state. Never retry blindly; check the returned `success` field.

**`goto <url>`** — Navigate to a URL. Waits for `domcontentloaded`.

```bash
$PB goto https://example.com
$PB goto http://localhost:3000/dashboard
```

Returns: `{ success, data: { url, title, status } }`

**`click <@ref>`** — Click an interactive element by its `@e` ref. Performs a 5ms staleness check before clicking; fails immediately if the ref is stale rather than waiting.

```bash
$PB click @e3
$PB click @e12
```

Returns: `{ success, data: { url, title } }` — includes the URL after any resulting navigation.

**`fill <@ref> <value>`** — Fill a text input, textarea, or other fillable element. Values with spaces do not need quoting — remaining CLI args are joined.

```bash
$PB fill @e2 hello world
$PB fill @e5 user@example.com
```

Returns: `{ success, data: { ref, value } }`

**`press <key>`** — Send a keyboard key to the active page. Accepts any Playwright key name.

```bash
$PB press Enter
$PB press Tab
$PB press Escape
$PB press ArrowDown
```

Returns: `{ success, data: { key, url } }`

---

### READ commands — safe to retry

These commands do not change browser state. Safe to call multiple times.

**`text`** — Get visible page text via `document.body.innerText`.

```bash
$PB text
```

Returns: `{ success, data: { text } }`

**`html`** — Get full page HTML via `page.content()`.

```bash
$PB html
```

Returns: `{ success, data: { html } }`

---

### META commands

**`snapshot`** — Full ARIA accessibility tree of the current page. Includes both interactive and structural elements (headings, nav, main, etc.).

```bash
$PB snapshot
```

Returns: `{ success, data: { url, title, interactive_only: false, tree, refs, aria_text? } }`

**`snapshot -i`** — Interactive elements only, each labeled with an `@e1`, `@e2`... ref. Use this before clicking or filling — never guess a ref.

```bash
$PB snapshot -i
```

Returns: same shape as `snapshot` with `interactive_only: true`; the `refs` map contains the locator entries for each `@eN`.

**`screenshot`** — Capture a viewport screenshot (1280x800). Saves to `~/.panda-browse/screenshots/screenshot-<timestamp>.png` by default and returns the path.

```bash
$PB screenshot
$PB screenshot --path /tmp/before.png
$PB screenshot --path /tmp/after.png
```

Returns: `{ success, data: { path, url, title } }`

**`tabs`** — List all open browser tabs.

```bash
$PB tabs
```

Returns: `{ success, data: { tabs: [{ index, url, title, active }] } }`

**`chain '<json-array>'`** — Execute multiple commands in sequence in a single CLI invocation. The chain stops at the first failure. Use this to reduce round-trips for multi-step operations.

```bash
$PB chain '[
  {"command":"goto","args":{"url":"https://example.com"}},
  {"command":"snapshot","args":{"interactive_only":true}},
  {"command":"screenshot","args":{}}
]'
```

Returns: `{ success, data: { results: [{ command, result }] } }`. On failure: adds `failed_at` field.

**`health`** — Check that the daemon is alive and responding.

```bash
$PB health
```

Returns: `{ status: "ok", pid }` (wrapped in standard result envelope from the daemon's health handler — note this endpoint bypasses `executeCommand` and returns directly).

**`stop`** (alias: `shutdown`) — Send SIGTERM to the daemon. The daemon cleans up its state file and exits.

```bash
$PB stop
```

---

## The @e Ref System

Refs are short handles (`@e1`, `@e2`, ...) that identify interactive elements. They are assigned fresh on each `snapshot` call and map to stable Playwright locator strategies (by label, by role+name, by placeholder, by name attribute, or by nth-position CSS fallback).

**Getting refs:**

```bash
$PB snapshot -i
# Output includes tree nodes like:
# { "ref": "@e3", "role": "button", "name": "Submit", "interactive": true }
# { "ref": "@e5", "role": "textbox", "name": "Email", "interactive": true }
```

**Using refs:**

```bash
$PB fill @e5 user@example.com
$PB click @e3
```

**Staleness rule:** After any navigation event — whether from `goto`, a `click` that follows a link, or `press Enter` submitting a form — the current ref map is invalidated. The daemon detects stale refs in ~5ms and returns an error asking you to re-snapshot. Always re-run `snapshot -i` after navigation before using refs again.

**Typical interaction workflow:**

```bash
# 1. Navigate to the page
$PB goto http://localhost:3000/login

# 2. Get interactive refs
$PB snapshot -i

# 3. Identify target elements from the output, then interact
$PB fill @e2 admin@example.com
$PB fill @e3 password123
$PB click @e4          # "Sign in" button

# 4. Page navigated — refs are stale; re-snapshot
$PB snapshot -i

# 5. Continue on the new page
$PB screenshot
```

---

## Common Workflows

### Visual smoke test

```bash
PB="$HOME/.claude/skills/panda-browse/bin/panda-browse"
$PB goto http://localhost:3000
$PB screenshot --path /tmp/smoke.png
# Read /tmp/smoke.png to verify layout
```

### Form filling

```bash
$PB goto http://localhost:3000/signup
$PB snapshot -i
# Identify: @e1=name input, @e2=email input, @e3=password, @e4=submit button
$PB fill @e1 Jane Doe
$PB fill @e2 jane@example.com
$PB fill @e3 s3cret!
$PB click @e4
$PB screenshot --path /tmp/after-signup.png
```

### Navigation verification

```bash
$PB goto http://localhost:3000
$PB snapshot -i
# Find nav links
$PB click @e7          # "Dashboard" link
$PB text               # Verify content changed
$PB screenshot
```

### Before/after comparison

```bash
$PB goto http://localhost:3000/widget
$PB screenshot --path /tmp/before.png
# ... make changes in code ...
$PB goto http://localhost:3000/widget   # reload after change
$PB screenshot --path /tmp/after.png
# Compare /tmp/before.png and /tmp/after.png visually
```

### Multi-step with chain (fewer round-trips)

```bash
$PB chain '[
  {"command":"goto","args":{"url":"http://localhost:3000/login"}},
  {"command":"fill","args":{"ref":"@e2","value":"admin@example.com"}},
  {"command":"fill","args":{"ref":"@e3","value":"password"}},
  {"command":"click","args":{"ref":"@e4"}},
  {"command":"screenshot","args":{}}
]'
```

Note: When using `chain` with refs, you must have called `snapshot -i` first in a separate command to populate the ref map. Refs set by a `snapshot` inside the same chain are available to subsequent steps in that chain.

---

## Integration with Other Panda Skills

**panda-debug** — Use panda-browse to visually verify bug fixes. Take a screenshot before applying a fix, apply the fix, reload, screenshot again. Compare before/after to confirm the fix is visible. Also use `snapshot` to inspect DOM state when debugging rendering issues — the ARIA tree reveals whether components have mounted and populated correctly.

**panda-audit** — Use panda-browse to verify runtime wiring. Navigate to each route the audit is checking, call `snapshot` to confirm the component appears in the ARIA tree with the correct role and name, and screenshot for documentation. This catches hydration failures, missing route registrations, and components that render blank.

**panda-executor** — After completing a task that touches frontend code, use panda-browse as the post-task smoke test harness. If the project has a dev server running, `goto` the affected route, take a screenshot, and verify the page renders without errors. Include the screenshot path in the task completion report.

---

## Error Handling

| Symptom | Cause | Fix |
|---|---|---|
| First command hangs up to 10s | Daemon cold start | Normal — wait for it |
| `Ref @eN not found. The page may have changed` | Stale ref after navigation | Re-run `snapshot -i` |
| `Ref @eN no longer exists on the page` | Element removed from DOM | Re-run `snapshot -i` |
| `Timeout` on goto | Page slow to load or wrong URL | Check URL, verify server is running |
| `Browser not installed` or Chromium launch error | Playwright Chromium missing | Run `npx playwright install chromium` |
| `Daemon failed to start within 10 seconds` | Bun or binary issue | Check `~/.panda-browse/` for logs; verify binary is executable |
| Connection refused | Daemon died (idle timeout or crash) | Next command will auto-restart it |
| `commands must be an array` | Bad JSON passed to chain | Validate JSON before passing to chain |

---

## Tips

- Always run `snapshot -i` before `click` or `fill` — never guess or hardcode a ref number.
- Use `chain` for multi-step flows to reduce round-trip overhead; each step result is available in the returned array.
- Screenshots are cheap — take them liberally at key points (before interaction, after submit, after navigation) as a natural audit trail.
- The daemon persists across all commands in a session. Cold start only happens once per 30-minute idle window.
- `$PB text` is the fastest way to assert page content without parsing HTML.
- `$PB html` is useful when you need to inspect the raw DOM, check for hidden elements, or verify server-rendered markup.
- The daemon uses a 1280x800 headless Chromium viewport with a standard Mac Chrome user-agent, so most sites render predictably.
- To stop the daemon explicitly: `$PB stop`. It will auto-restart on next use.
