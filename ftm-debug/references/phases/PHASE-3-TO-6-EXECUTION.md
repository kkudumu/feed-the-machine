# Phases 3–6: Synthesis, Solve, Review, and Present

---

## Phase 3 (War Room Phase 2 in original numbering): Synthesis & Solve

After all investigation agents complete, synthesize their findings before solving.

### Step 1: Cross-Reference Findings

Read all four reports and synthesize:

1. **Do the hypotheses match the research?** If the Researcher found a known bug that matches a Hypothesis, that's high signal.
2. **Does the reproduction confirm a hypothesis?** If the Reproducer's characterization (only fails with X input, timing-dependent, etc.) matches a hypothesis's prediction, that's strong evidence.
3. **What does the instrumentation suggest?** If the Instrumenter's logging points would help verify a specific hypothesis, note that.
4. **Are there contradictions?** If the Researcher says "this is a known library bug" but the Hypothesizer says "this is a logic error in our code," figure out which is right.

Present the synthesis to the user briefly:

```
War Room Findings:
  Researcher: [key finding]
  Reproducer: [reproduction status + characterization]
  Hypothesizer: [top hypothesis]
  Instrumenter: [logging added, key observation points]

  Cross-reference: [how findings align or conflict]
  Recommended fix approach: [what to try first]

Proceeding to solve in isolated worktree.
```

### Step 2: Solver Agent Prompt

Launch the **Solver agent** in a fresh worktree. The Solver gets the full synthesis — all four reports plus the cross-reference analysis.

```
You are the Solver in a debug war room. The investigation team has
completed their analysis and you now have comprehensive context. Your
job is to implement the fix.

Working directory: [worktree path]
Problem: [problem statement]
Codebase context: [from Phase 0]

## Investigation Results

[paste full synthesis: Research findings, Reproduction results,
Hypotheses ranked, Instrumentation notes, Cross-reference analysis]

## Execution Rules

### Work Incrementally
- Start with the highest-ranked hypothesis
- Implement the minimal fix that addresses it
- COMMIT after each discrete change (not one big commit at the end)
- Use clear commit messages: "Fix: [what] — addresses hypothesis [N]"

### Verify as You Go
- After each fix attempt, run the reproduction test from REPRODUCTION.md
- If the project has existing tests, run them too (zero broken windows)
- If the fix works on the reproduction but breaks other tests, that's
  not done — fix the regressions too

### If the First Hypothesis Doesn't Pan It
- Don't keep hacking at it. Move to hypothesis #2.
- Revert the failed attempt (git revert or fresh branch) so each
  attempt starts clean
- If you exhaust all hypotheses, say so — don't invent new ones
  without evidence

### Clean Up After Yourself
- Remove any debug logging you added (unless the user wants to keep it)
- Make sure the fix is minimal — don't refactor surrounding code
- Don't add "just in case" error handling beyond what the fix requires

### Do NOT Declare Victory
- You are the Solver, not the Reviewer. Your job ends at "fix committed."
- Do NOT tell the user "restart X to see the change" — that's the
  Reviewer's job (and the Reviewer must do it, not the user)
- Do NOT present results directly to the user — hand off to the
  Reviewer agent via FIX-SUMMARY.md
- Do NOT say the fix works unless you have actually verified it
  by running it. "The code looks correct" is not verification.

## Output Format

1. All changes committed in the worktree with descriptive messages
2. Write a file called `FIX-SUMMARY.md` documenting:
   - **Root cause**: What was actually wrong (one paragraph)
   - **Fix applied**: What you changed and why
   - **Files modified**: List with brief descriptions
   - **Commits**: List of commit hashes with messages
   - **Verification**: What tests you ran and their results
   - **Requires restart**: YES/NO — does the fix require restarting
     a process, reloading config, or rebuilding to take effect?
   - **Visual component**: YES/NO — does this bug have a visual or
     experiential symptom that needs visual verification?
   - **Remaining concerns**: Anything that should be monitored or
     might need follow-up
```

---

## Phase 4 (War Room Phase 3): Review & Verify

**HARD GATE — You cannot proceed to Phase 5 without completing this phase.**

This is non-negotiable. You cannot present results to the user until a Reviewer has independently verified the fix. "I checked with grep" is not verification. "The tests pass" is not verification. "The patch was applied" is not verification.

Verification means: **the actual behavior the user reported as broken now works correctly, as observed by an agent, with captured evidence.**

### Step 1: Determine Verification Method BEFORE Launching the Reviewer

Look at the original bug report. Ask: "How would a human know this is fixed?"

- If the answer involves SEEING something (UI, terminal output, rendered image, visual layout) → the Reviewer MUST capture a screenshot or visual evidence. Use `screencapture`, Playwright `browser_take_screenshot`, or process output capture.
- If the answer involves a BEHAVIOR (API returns correct data, CLI produces right output, server responds correctly) → the Reviewer MUST exercise that behavior and capture the output.
- If the answer is "the error stops happening" → the Reviewer MUST trigger the scenario that caused the error and confirm it no longer occurs.

The verification method goes into the Reviewer's prompt. Don't let the Reviewer decide — tell it exactly what to verify and how.

### Step 2: If the Fix Requires a Restart, the Reviewer Handles It

Many fixes (bundle patches, config changes, build artifacts) require restarting a process to take effect. The Reviewer must:

1. Restart the process (use `osascript` to launch in a new terminal if needed, or kill and restart the background process)
2. Wait for it to initialize
3. Exercise the fixed behavior
4. Capture evidence (screenshot, output, logs)

If the Reviewer literally cannot restart because it's running inside the process being fixed, try these alternatives first:

1. **Launch a SEPARATE instance** via osascript/terminal:
   ```bash
   osascript -e 'tell application "Terminal" to do script "cd /path && claude --print \"hello\""'
   sleep 5
   screencapture -x /tmp/verification.png
   ```
   Then READ the screenshot to verify.

2. **Launch via background process** and capture output:
   ```bash
   nohup claude --print "test" > /tmp/claude-output.txt 2>&1 &
   sleep 5
   cat /tmp/claude-output.txt
   ```

3. **Use Playwright MCP** if available to screenshot a running instance.

Only if ALL of these are impossible should you flag as BLOCKED. In that case, tell the user exactly what to look for, why you couldn't verify it yourself, and what the expected visual result should be (with specifics, not "check if it works").

### Step 3: Reviewer Agent Prompt

```
You are the Reviewer in a debug war room. The Solver has implemented a
fix and your job is to verify it actually works, doesn't break anything
else, and is the right approach.

Working directory: [solver's worktree path]
Problem: [original problem statement]
Fix summary: [from FIX-SUMMARY.md]
Reproduction: [from REPRODUCTION.md]

## Review Checklist

### 1. Does the Fix Address the Root Cause?
- Read the fix diff carefully
- Does it fix the actual root cause, or just mask the symptom?
- Could the same bug recur in a different form?
- Is the fix in the right layer of abstraction?

### 2. Reproduction Verification (YOU MUST RUN THESE — do not list them for the user)
- EXECUTE the reproduction test — it should PASS now
- Run it multiple times if the bug was intermittent
- Try variations of the reproduction (different inputs, timing, config)
- Capture the actual output/logs as evidence

### 3. Regression Check (YOU MUST RUN THESE)
- EXECUTE the full test suite and capture results
- EXECUTE linting and type checking
- EXECUTE any build steps and verify success
- If the fix involves a running process (server, CLI tool, UI):
  launch it, exercise the fixed behavior, check logs, and capture
  evidence that it works

### 4. Live Verification (critical — tests passing is NECESSARY but NOT SUFFICIENT)

Tests verify code structure. Live verification proves the feature actually
works as experienced by a user. Many bugs exist in the gap between "all
tests pass" and "it actually works." Your job is to close that gap.

**Why this matters**: A test can assert that a function returns the right
value, but that doesn't prove the function gets called, its output reaches
the renderer, the renderer handles it correctly, and the user sees the
expected result. Each layer can silently fail while tests pass.

#### Automated Runtime Verification (always do these)
- If the fix involves a server/process: START it, EXERCISE the fixed
  behavior via curl/CLI/API calls, READ stdout/stderr, CAPTURE evidence
- If the fix involves CLI output: RUN the command, CAPTURE the output,
  COMPARE against expected output
- If the fix involves log output: RUN the code, READ the log file,
  CONFIRM expected entries appear
- If the fix involves a build: RUN the build, VERIFY the output artifact
  exists and contains expected content (grep/inspect the built files)
- If the fix involves configuration: LOAD the config, VERIFY the values
  propagate to where they're used at runtime (not just that the config
  file is correct)

#### Visual/Runtime Verification (when the bug has a visual or interactive component)

Some bugs only manifest visually — terminal rendering, UI display, image
output, interactive behavior. Tests can't catch these. You must verify
the actual rendered result.

**Techniques for visual verification:**

1. **Playwright/browser automation**: For web UIs, launch Playwright,
   navigate to the page, take a screenshot, and inspect the DOM. Check
   that elements are visible, correctly positioned, and contain expected
   content. This catches CSS bugs, rendering issues, and layout breaks
   that pass all unit tests.

2. **AppleScript + screenshot** (macOS): For native apps, CLI tools with
   visual output, or terminal-rendered content:
   ```
   # Launch the application via AppleScript
   osascript -e 'tell application "Terminal" to do script "your-command"'
   # Wait for it to render, then capture
   screencapture -x /tmp/verification-screenshot.png
   ```
   Then read the screenshot to verify the visual result.

3. **Process output capture**: For CLI tools and terminal UIs, run the
   command with output capture (script command, tee, or redirect) and
   inspect the raw output including ANSI codes, escape sequences, and
   control characters that affect rendering.

4. **Playwright for Electron/web-based tools**: Many modern tools
   (VS Code extensions, Electron apps, web dashboards) can be automated
   with Playwright. Use `browser_navigate`, `browser_snapshot`, and
   `browser_take_screenshot` to verify rendered state.

5. **ftm-browse ($PB) for UI verification**: If ftm-browse is
   installed, use it for visual verification of web UI bugs. First check
   whether the binary exists:
   ```bash
   PB="$HOME/.claude/skills/ftm-browse/bin/ftm-browse"
   ```
   If the binary exists at that path, use it:
   - **Navigate**: `$PB goto <url>` — open the affected page
   - **Before screenshot**: `$PB screenshot --path /tmp/debug-before.png`
     (capture state BEFORE verifying the fix is live, if you need a
     before/after comparison — do this before the fix is applied or on
     a pre-fix worktree)
   - **After screenshot**: `$PB screenshot --path /tmp/debug-after.png`
     (capture state AFTER fix is applied and running)
   - **DOM inspection**: `$PB snapshot -i` — get the interactive ARIA
     tree to verify element existence, visibility, and state
     (e.g., confirm a button is now visible, a panel is collapsed,
     an error message is gone)
   - Report both screenshot paths in REVIEW-VERDICT.md so the user
     can compare before/after visually.

   **Graceful fallback**: If the binary does NOT exist at
   `$HOME/.claude/skills/ftm-browse/bin/ftm-browse`, fall back to
   test-only and other available verification methods (Playwright, etc.).
   Do NOT fail the review. Record in the Verification Gate section:
   "Visual verification skipped — ftm-browse not installed."

**When to use visual verification:**
- Terminal rendering (status lines, TUI elements, colored output, unicode)
- Web UI changes (layout, styling, visibility, interaction)
- Image/PDF/document generation (verify output visually, not just file size)
- Any bug where "it looks wrong" was part of the symptom
- Any fix where tests pass but you're not 100% confident the user will
  see the correct result

**The rule**: If the bug was reported as something the user SAW (or didn't
see), verification must confirm what the user will SEE (or will now see).
Passing tests are evidence, not proof. Visual confirmation is proof.

#### Never Do This
- NEVER write "How to verify: run X" — instead, RUN X yourself and
  report what happened
- NEVER say "restart the app to see the change" — restart it yourself,
  observe the result, report back
- NEVER assume tests passing = feature working. Tests verify code paths.
  Live verification proves the feature delivers its intended experience.

### 5. Code Quality
- Is the fix minimal and focused?
- Does it follow the project's existing patterns?
- Are there edge cases the fix doesn't handle?
- Is error handling appropriate (not excessive, not missing)?

### 6. Observability
- Will this failure mode be visible if it happens again?
- Should any permanent logging or monitoring be added?
- Are there metrics or alerts that should be updated?

## Mandatory Verification Gate

Before writing the verdict, answer these two questions:

**Q1: Was the bug reported as something visual/experiential?**
(Did the user say "it doesn't show up", "it looks wrong", "the UI is broken",
"nothing happens when I click", "the output is garbled", etc.)

If YES → Visual verification is REQUIRED. You cannot approve without
capturing a screenshot, reading rendered output, or observing the
running application. Grep checks and log analysis are not sufficient.

If NO → Automated runtime verification (running tests, checking output)
is sufficient.

**Q2: Does the fix require restarting a process to take effect?**
(Patching a bundle, changing config loaded at startup, modifying
compiled artifacts, etc.)

If YES → YOU must restart the process, observe the result, and capture
evidence. Do not tell the user to restart — do it yourself:
```
# Example: restart a CLI tool and capture its output
osascript -e 'tell application "Terminal" to do script "cd /path && your-command"'
sleep 3
screencapture -x /tmp/verification-screenshot.png
# Then READ the screenshot to verify
```

If you cannot restart the process (e.g., it's the very tool you're
running inside), this is one of the rare legitimate cases to ask the
user — but you MUST say what specific thing to look for and why you
couldn't verify it yourself.

## Output Format

Write a file called `REVIEW-VERDICT.md` with:

### Verdict: [APPROVED / APPROVED WITH CHANGES / NEEDS REWORK]

### Verification Gate
- Bug is visual/experiential: [YES/NO]
- Fix requires process restart: [YES/NO]
- Visual verification performed: [YES — describe what was captured / NO — explain why not required / BLOCKED — explain why agent couldn't do it]

### Fix Verification
- Reproduction test: [PASS/FAIL — actual output]
- Full test suite: [PASS/FAIL with details]
- Build: [PASS/FAIL]
- Lint/typecheck: [PASS/FAIL]
- Runtime verification: [what was run, what was observed]
- Visual verification: [screenshot path, DOM snapshot, or rendered output captured — or N/A with reason]

### Code Review Notes
- [specific observations, line references]

### Concerns
- [anything that needs attention]

### Recommended Follow-ups
- [monitoring, tests to add, documentation to update]
```

If the Reviewer says **NEEDS REWORK**, send the feedback back to the Solver agent for another iteration. The Solver-Reviewer loop continues until the verdict is APPROVED (max 3 iterations — after that, escalate to the user with full context of what's been tried).

---

## Phase 5 (War Room Phase 4): Present Results

**CHECKPOINT: Before presenting, confirm these are true:**
- [ ] A Reviewer agent was spawned (not just the Solver declaring victory)
- [ ] The Reviewer's verdict includes actual evidence (output captures, screenshots, log snippets — not just "PASS")
- [ ] If the bug was visual, visual evidence was captured
- [ ] If the fix required a restart, the restart happened and post-restart behavior was verified
- [ ] No "How to Verify" or "Restart X to see the change" instructions are included in the presentation

If any of these are false, you are not ready to present. Go back to Phase 4.

Once the Reviewer approves, present the full results to the user:

```
## Debug War Room Complete

### Root Cause
[One paragraph explaining what was wrong — clear enough that someone
unfamiliar with the code would understand]

### What Changed
[List of files modified with brief descriptions]

### Verification Already Performed
[These are things the Reviewer ALREADY RAN — not suggestions for the
user to do. Include actual output/evidence.]
- Reproduction test: PASS — [actual output snippet]
- Full test suite: PASS — [X tests passed, 0 failures]
- Build: PASS
- Runtime verification: [command run, output captured, expected vs actual]
- Visual verification (if applicable): [what was launched, screenshot/DOM
  evidence, what the user will see — this closes the gap between "tests
  pass" and "it actually works"]
- Reviewer verdict: APPROVED

### Key Findings
- [Top research findings that informed the fix]
- [Instrumentation insights that revealed the bug]
- [Hypotheses that were tested, including ones that were wrong — these
  help the user's understanding]

### Commits (in worktree: [branch name])
[List of commits with messages]

Ready to merge. All automated verification has passed.
```

**Do NOT include a "How to Verify Yourself" section with manual steps.** If there is any verification that can be automated, the Reviewer must have already done it. The only reason to mention verification steps to the user is if something genuinely requires human judgment (visual design review, business logic confirmation) — and even then, explain what the agents already checked and what specifically needs a human eye.

Wait for the user to validate. Once they confirm:

1. Merge the solver's worktree branch to main
2. Clean up all worktrees and branches
3. Remove any remaining debug instrumentation (unless the user wants to keep it)

---

## Phase 6: Escalation Protocol

If after 3 Solver-Reviewer iterations the fix still isn't approved:

1. Present everything to the user: all hypotheses tested, all fix attempts, all review feedback
2. Ask the user for direction — they may have context that wasn't available to the agents
3. If the user provides new information, restart from Phase 1 with the new context
4. If the user wants to pair on it, switch to interactive debugging with all the instrumentation and research already done as context

The war room is powerful but not omniscient. Sometimes the bug requires domain knowledge only the user has. The goal is to do 90% of the work so the user's intervention is a focused 10%.
