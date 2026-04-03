# Interactive Plan Approval Protocol

Read `~/.claude/ftm-config.yml` field `execution.approval_mode`. This controls whether the user sees and approves the plan before execution begins.

## Mode: `auto` (default legacy behavior)
Skip this section entirely. Execute as before — micro/small just go, medium outlines steps and executes, large routes to brainstorm/executor.

## Mode: `plan_first` (recommended for collaborative work)
For **medium and large** tasks, present a numbered task list and wait for the user to approve before executing anything.

**Step 1: Generate the plan.**

Build a numbered checkbox list. This format is **mandatory** — no narrative steps, no prose paragraphs, no bullet-point summaries. Every plan, whether it's code, ops, comms, or infrastructure, MUST use this exact format:

```
  N. [ ] One-line action → target (file, channel, system, or person)
```

Each step must have:
- A number
- A `[ ]` checkbox (literal characters, not rendered)
- A one-line description of what will be done
- An arrow `→` pointing to the target: file path for code, channel/email for comms, system name for infra, or "self-evident" for simple actions
- If applicable, a verification method after the target: `verify: test / lint / visual check / confirmation`

**This applies to ALL task types, not just code:**
- Code tasks: `3. [ ] Add OAuth validation → src/middleware/oauth.ts  verify: npm test`
- Ops/comms tasks: `1. [ ] Reply to Everett requesting domain mapping → Braintrust support thread`
- Infra tasks: `2. [ ] Create Freshservice webhook trigger → freshservice admin / workflows`
- Admin tasks: `4. [ ] Close out ITWORK2-9772 → Jira`

**NEVER produce:**
- Narrative paragraphs describing steps
- Numbered steps without `[ ]` checkboxes
- Steps with sub-bullets explaining details (put that in execution, not the plan)
- Headers like "Step 1:" or "### Step 1" — use the numbered checkbox format only

Present it like this:

```
Here's my plan for this task:

  1. [ ] Read auth middleware and map dependencies → src/middleware/auth.ts
  2. [ ] Add OAuth token validation endpoint → src/routes/auth.ts, src/middleware/oauth.ts
  3. [ ] Update existing auth tests for new flow → src/__tests__/auth.test.ts
  4. [ ] Run full test suite → verify: pytest / npm test
  5. [ ] Update INTENT.md for changed functions → docs/INTENT.md

Approve all? Or tell me what to change.
  - "approve" or "go" → execute all steps in order
  - "skip 3" → execute all except step 3
  - "for step 2, use passport.js instead" → modify step 2, then execute all
  - "only 1,2" → execute only steps 1 and 2
  - "add: step between 2 and 3 to update the config" → insert a step
  - "deny" or "stop" → cancel entirely
```

**Ops example:**

```
Here's my plan for the Braintrust post-SSO setup:

  1. [ ] Reply to Everett requesting domain mapping + group mappings → Braintrust support thread
  2. [ ] Reply to Spencer with admin process answer → #proj-braintrust
  3. [ ] Request API key from Everett or Spencer → Braintrust org settings
  4. [ ] Build Freshservice webhook → Braintrust API integration → freshservice workflows + Lambda
  5. [ ] Reconcile existing users vs Okta groups → Braintrust API + Okta
  6. [ ] Close out ITWORK2-9772 → Jira

Approve all? Or tell me what to change.
```

**Step 2: Parse the user's response.**

| User says | Action |
|-----------|--------|
| `approve`, `go`, `yes`, `lgtm`, `ship it` | Execute all steps in order |
| `skip N` or `skip N,M` | Remove those steps, execute the rest |
| `only N,M,P` | Execute only the listed steps in order |
| `for step N, [instruction]` | Replace step N's approach with the user's instruction, then execute all |
| `add: [description] after N` or `add: [description] before N` | Insert a new step at that position, renumber, then execute all |
| `deny`, `stop`, `cancel`, `no` | Cancel. Do not execute anything. Ask what the user wants instead. |
| A longer message with mixed feedback | Parse each instruction. Apply all modifications to the plan. Present the revised plan and ask for final approval. |

**Step 3: Execute the approved plan.**

Work through the approved steps sequentially. After each step:
- Show a brief completion message: `Step 2/5 done: OAuth endpoint added.`
- If a step fails, stop and report. Ask: "Step 3 failed: [error]. Fix and continue, skip this step, or stop?"
- After all steps complete, show a summary of what was done.

**Step 4: Post-execution update.**

Update the blackboard with decisions made and experience recorded, same as normal Act phase.

## Mode: `always_ask`
Same as `plan_first` but applies to **small** tasks too. Only micro tasks (single obvious edit) skip the approval gate.

## Combining with explicit skill routing

When the mind decides to route to a skill (e.g., ftm-debug, ftm-executor), the plan approval still applies if the mode is `plan_first` or `always_ask`. Present:

```
For this task, I'd route to ftm-debug with this approach:

  1. [ ] Launch ftm-debug war room on the flaky auth test
  2. [ ] Apply the fix from debug findings
  3. [ ] Run test suite to verify
  4. [ ] Record experience to blackboard

Approve? Or adjust the approach.
```

This gives the user control over the *strategy* even when delegating to skills.
