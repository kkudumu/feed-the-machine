# Edge Cases, Anti-Patterns & Fallback Handling

---

## Anti-Pattern: Asking the User to Do Agent Work

This is the single most important rule of the war room: **never ask the user to perform a verification step that an agent could perform**.

Examples of violations:
- "Restart the application and check if the doom head appears" — an agent can launch the app, capture a screenshot, read the output, verify the rendering
- "Run `tail -f /tmp/debug.log` and look for entries" — an agent can read that file
- "Open a browser and check the UI" — an agent can use Playwright/Puppeteer to screenshot and inspect the DOM
- "Try running this command and let me know what happens" — an agent can run the command
- "All 103 tests pass!" without verifying the actual feature works — tests are a proxy, not proof. The agent must also verify runtime behavior matches expectations

Examples of legitimate user asks:
- "Does this visual design match what you wanted?" — subjective human judgment
- "Is this the business logic you intended?" — domain knowledge only the user has
- "Should we merge this to main?" — permission/authority decision

When in doubt: if it can be executed by running a command, reading a file, or checking output, an agent does it. The user reviews the evidence the agent collected, not the raw behavior.

---

## Anti-Pattern: Collapsing Solver and Reviewer Into One

A common failure mode: the session reads this skill, does good investigation work, writes a fix, then presents results directly to the user — skipping the Reviewer agent entirely. The Solver says "Restart X to see the change" and declares victory.

This defeats the entire verification system. The Solver is biased toward their own fix. They wrote the code and believe it works. The Reviewer exists as an independent check.

**The rule**: After the Solver commits their fix, you MUST spawn a separate Reviewer agent. The Reviewer reads FIX-SUMMARY.md, runs the verification gate, and either approves or sends it back. Only after the Reviewer approves do you present results to the user.

If you find yourself writing "Root Cause / What Changed / How to Verify" without having spawned a Reviewer — stop. You're doing the anti-pattern. Spawn the Reviewer.

---

## Anti-Pattern: Structural Verification Masquerading as Live Verification

Another common failure: the session verifies the fix by grepping the patched file for expected strings, checking that function references exist, or confirming config values are set. This is structural verification — it proves the code was written, not that it works.

Example of structural verification pretending to be live:
```
✓ grep -c "doom_status patch start" cli.js → 1
✓ grep -c "doomStatuslineBackend" cli.js → 6
✓ node -e "require('cli.js')" → parses
```

This proves the patch was applied and the file isn't syntactically broken. It does NOT prove the doom head renders visually. The grep checks are necessary but they are Phase 4 Step 3 (regression checks), not Phase 4 Step 4 (live verification).

Live verification for this bug would be: launch Claude Code, wait for the statusline to render, capture a screenshot, confirm the doom head is visible. That's what the Reviewer must do for visual bugs.

---

## Fallback: Reviewer Cannot Restart the Process

If the Reviewer literally cannot restart because it's running inside the process being fixed (e.g., debugging Claude Code from within Claude Code), try these alternatives before flagging BLOCKED:

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

Only if ALL of these are impossible: flag as BLOCKED, tell the user exactly what to look for, why you couldn't verify it yourself, and what the expected visual result should be (with specifics, not "check if it works").

---

## Fallback: panda-browse Not Installed

When visual verification is needed for a web UI bug:

```bash
PB="$HOME/.claude/skills/panda-browse/bin/panda-browse"
```

If the binary does NOT exist at that path:
- Fall back to Playwright MCP, Puppeteer, or screencapture
- Do NOT fail the review
- Record in REVIEW-VERDICT.md Verification Gate section: "Visual verification skipped — panda-browse not installed."
- Use whatever alternative is available

---

## Fallback: Exhausted All Hypotheses Without a Fix

If the Solver exhausts all hypotheses and no fix is approved after 3 Solver-Reviewer iterations:

1. Do NOT invent new hypotheses without evidence
2. Present everything to the user: all hypotheses tested, all fix attempts, all review feedback
3. Ask for direction — the user may have domain context not available to the agents
4. If the user provides new information, restart from Phase 1 with the updated context
5. If the user wants to pair, switch to interactive debugging with all instrumentation and research as context
