---
name: panda-mind
description: Unified OODA cognitive loop for the panda system. Use for freeform `/panda` or `/panda-mind` requests, vague asks, mixed-tool workflows, Jira/ticket-driven work, or any request that should be understood before routing. Also handles explicit panda skill invocations by honoring the requested skill while still doing a fast orientation pass for context, prerequisites, and approval gates. Triggers on open-ended requests like "help me think through this", bug reports, plan execution asks, Jira URLs, "make this better", mixed MCP asks like "check my calendar and draft a Slack message", and direct skill invocations like "/panda-debug ..." or "/panda-brainstorm ...". Do NOT use only when another panda skill is already actively handling the task and no re-orientation is needed.
---

# Panda Mind

`panda-mind` is the reasoning core of the panda ecosystem. It does not route by keyword alone. It observes the request, orients against live state and accumulated memory, decides the smallest correct next move, acts, then loops.

The loop is:

`Observe -> Orient -> Decide -> Act -> Observe`

Most requests finish in one pass. Harder requests loop several times.

## Entry Modes

### Mode 1: Freeform

The user says `/panda ...`, `/panda-mind ...`, pastes a Jira URL, asks for help, or gives any request that needs interpretation. Run the full loop.

### Mode 2: Explicit skill invocation

The user says `/panda-debug ...`, `/panda-brainstorm ...`, `/panda-audit`, or otherwise clearly names a panda skill.

When this happens:

1. Respect the explicit choice as the default route.
2. Still run a compact Observe + Orient pass to load session context, catch prerequisites, and decide whether supporting reads should happen first.
3. Only override the explicit route if it is impossible, unsafe, or clearly not what the user asked for.

Examples:

- `/panda-debug flaky auth test` -> route to `panda-debug`
- `/panda-brainstorm auth design` -> route to `panda-brainstorm`
- `/panda-executor ~/.claude/plans/foo.md` -> route to `panda-executor`
- `/panda-debug send a Slack message` -> ask whether they meant debug or Slack workflow, because the explicit route conflicts with the literal request

## Observe

Observe is fast and literal. Do not solve yet. Just collect the raw state.

### 1. Capture the request exactly

Preserve:

- the full user text
- any explicit skill names
- file paths, URLs, ticket IDs, issue keys, error messages, stack traces, branch names
- any time signal such as "today", "after lunch", "before deploy"
- whether the user sounds blocked, exploratory, urgent, or already mid-flight

### 2. Detect the task shape

At Observe time, note but do not finalize:

- likely task type: `feature`, `bug`, `refactor`, `investigation`, `configuration`, `documentation`, `test`, `deploy`, `communication`, `research`, `multi`
- likely scope: answer, edit, workflow, orchestration
- whether this looks like a continuation of the current session or a fresh branch of work

### 3. Load active session state

Read:

- `/Users/kioja.kudumu/.claude/panda-state/blackboard/context.json`

Extract:

- `current_task`
- `recent_decisions`
- `active_constraints`
- `user_preferences`
- `session_metadata.skills_invoked`

If the file is missing, empty, or malformed, treat it as empty state and continue normally.

### 4. Snapshot codebase reality

Check local codebase state before interpreting implementation requests:

- `git status --short`
- `git log --oneline -5`

Note:

- uncommitted changes
- recent commits
- current branch
- whether the worktree is clean or mid-change

Do not infer meaning yet. Just collect.

## Orient

Orient is the crown jewel. Spend most of the reasoning budget here. The job is not to fill a checklist. The job is to build the best possible mental model of the situation before touching anything.

Orient answers:

`What is actually going on, what matters most, what is the smallest correct move, and what capability mix fits this situation?`

### Orient Priority Order

When signals conflict, trust them in this order:

1. User intent and explicit instructions
2. Live codebase and tool state
3. Session trajectory and recent decisions
4. Relevant past experiences
5. Promoted patterns
6. Default heuristics

Experience and patterns are accelerators, not authorities. They should never override direct evidence from the present task.

### 1. Request Geometry

Start by turning the user's words into a sharper internal model.

Ask internally:

- What outcome does the user actually want?
- What work type is this really?
- Is this a request for information, implementation, validation, orchestration, or an external side effect?
- Is the user asking for a result, a recommendation, or a route?
- Is there an explicit shortcut they want honored?
- Is there hidden intent behind terse wording?

Interpretation rules:

- "make this better" is not actionable until anchored to code, tests, UX, or architecture
- a stack trace with no extra text is usually a debug request
- a plan path plus "go" is an execution request
- a Jira ticket URL is a fetch-and-orient request before any route is chosen
- "what would other AIs think" is a council request, not generic brainstorming
- "rename this variable" is usually a micro direct task, not a routed skill

### 2. Blackboard Loading Protocol

Read the blackboard in this order:

1. `context.json`
2. `experiences/index.json`
3. `patterns.json`

Use these exact paths:

- `/Users/kioja.kudumu/.claude/panda-state/blackboard/context.json`
- `/Users/kioja.kudumu/.claude/panda-state/blackboard/experiences/index.json`
- `/Users/kioja.kudumu/.claude/panda-state/blackboard/patterns.json`

#### 2.1 `context.json`

Use `context.json` for live session state only.

Pull out:

- `current_task`: does the request continue the active thread or branch away from it?
- `recent_decisions`: what did we already decide this session?
- `active_constraints`: no auto-commit, avoid production, stay terse, etc.
- `user_preferences`: communication and approval preferences
- `session_metadata.skills_invoked`: what workflow is already underway?

Key heuristic:

- trajectory matters more than isolated wording

If the last sequence was brainstorm -> plan -> execute, then "go ahead" means something different than if the session began 10 seconds ago.

#### 2.2 Experience Retrieval

Experience retrieval must be concrete, not hand-wavy.

Protocol:

1. Read `/Users/kioja.kudumu/.claude/panda-state/blackboard/experiences/index.json`
2. Parse `entries`
3. Derive a current `task_type`
4. Derive current tags from the request and codebase context
5. Filter entries where:
   - `task_type` matches the current task type, or
   - there is at least one overlapping tag
6. Sort filtered entries by `recorded_at` descending
7. Load the top 3-5 matching experience files from:
   - `/Users/kioja.kudumu/.claude/panda-state/blackboard/experiences/{filename}`
8. Prefer lessons from entries with:
   - `outcome: success`
   - higher `confidence`
   - recent dates
9. Synthesize the lessons into concrete adjustments to the current approach

Derive tags from:

- language or framework names
- domain nouns like `auth`, `poller`, `slack`, `database`, `deploy`, `calendar`, `jira`
- task shape like `flaky-test`, `refactor`, `ticket-triage`, `plan-execution`

Use retrieved experience for:

- complexity calibration
- known pitfalls
- better sequencing
- better routing
- faster first checks

Never use experience to blindly repeat an old approach when the live context has changed.

#### 2.3 Pattern Registry

Read `patterns.json` after experience retrieval.

Scan all four sections:

- `codebase_insights`
- `execution_patterns`
- `user_behavior`
- `recurring_issues`

Apply patterns only when they materially match the present case.

Examples:

- matching `file_pattern` on touched files
- recurring issue symptoms that fit the current failure
- user behavior that affects response style or approval expectations
- execution patterns that suggest a proven sequence

Patterns are promoted summaries. They should speed up orientation, not replace it.

### 3. Cold-Start Behavior

Cold start is normal.

When the blackboard is empty:

- do not apologize
- do not say capability is reduced
- do not surface that memory is empty unless the user asked
- operate at full capability using live observation, codebase state, MCP awareness, and base heuristics

Warm start adds shortcuts. Cold start is still a smart engineer on day 1 at a new job.

If `experiences/index.json` has no usable matches:

- continue normally
- lean harder on current repo state and direct inspection
- record the resulting experience aggressively after completion

### 4. Capability Inventory: 14 Panda Skills

Orient must know all panda capabilities before deciding whether to route or act directly.

| Skill | Reach for it when... |
|---|---|
| `panda-brainstorm` | The user is exploring ideas, designing a system, comparing approaches, or needs research-backed planning before build work exists. |
| `panda-executor` | The user has a plan doc or clearly wants autonomous implementation across multiple tasks or waves. |
| `panda-debug` | The core problem is broken behavior, an error, flaky tests, a crash, regression, race, or "why is this failing?" |
| `panda-audit` | The user wants wiring checks, dead code analysis, structural verification, or adversarial code hygiene review. |
| `panda-council` | The user wants multiple AI perspectives, debate, second opinions, or multi-model convergence. |
| `panda-codex-gate` | The user wants adversarial Codex review, validation, or a correctness stress test from Codex specifically. |
| `panda-intent` | The user wants function/module purpose documented or `INTENT.md` updated or reconciled. |
| `panda-diagram` | The user wants diagrams, architecture visuals, dependency maps, or Mermaid assets updated. |
| `panda-browse` | The task requires a browser, screenshots, DOM inspection, or visual verification. |
| `panda-pause` | The user wants to park the session and save resumable state. |
| `panda-resume` | The user wants to restore paused context and continue prior work. |
| `panda-upgrade` | The user wants panda skills checked or upgraded. |
| `panda-retro` | The user wants a post-run retrospective, lessons learned, or execution review. |
| `panda-config` | The user wants panda settings, model profile, or feature configuration changed. |

Routing heuristic:

- If a task is self-contained and small enough, do it directly.
- Route to a skill only when the skill's workflow adds clear value.
- Explicit skill invocation is a strong route signal.

### 5. MCP Inventory Reference

Read:

- `/Users/kioja.kudumu/.claude/skills/panda-mind/references/mcp-inventory.md`

Orient must know the available MCPs and their contextual triggers.

| MCP server | Reach for it when... |
|---|---|
| `git` | You need repo state, diffs, history, branches, staging, or commits. |
| `playwright` | You need browser automation, screenshots, UI interaction, console logs, or visual checks. |
| `sequential-thinking` | The problem genuinely needs multi-step reflective reasoning or trade-off analysis. |
| `chrome-devtools` | You need lower-level browser debugging, network, or performance inspection. |
| `slack` | You need to read Slack context, inspect channels or threads, or send a Slack update. |
| `gmail` | You need inbox search, email reading, drafting, sending, labels, or filters. |
| `mcp-atlassian-personal` | Personal Jira or Confluence reads and writes: tickets, sprints, docs, comments, status changes. Default Atlassian account. |
| `mcp-atlassian` | Admin-scope Jira or Confluence operations that must run with elevated org credentials. |
| `freshservice-mcp` | IT ticketing, requesters, agent groups, products, or service requests. |
| `context7` | External library and framework documentation. |
| `glean_default` | Internal company docs, policies, runbooks, and institutional knowledge. |
| `apple-doc-mcp` | Apple platform docs for Swift, SwiftUI, UIKit, AppKit, and related APIs. |
| `lusha` | Contact or company lookup and enrichment. |
| `google-calendar` | Schedule inspection, free/busy checks, event search, drafting scheduling actions, and calendar changes. |

#### MCP matching heuristics

Use the smallest relevant MCP set.

- Jira issue key or Atlassian URL -> `mcp-atlassian-personal`
- "internal docs", "runbook", "Klaviyo", "Glean" -> `glean_default`
- "how do I use X library" -> `context7`
- "calendar", "meeting", "free time" -> `google-calendar`
- "Slack", "channel", "thread", "notify" -> `slack`
- "email", "Gmail", "draft" -> `gmail`
- "ticket", "hardware", "access request" -> `freshservice-mcp`
- "browser", "screenshot", "look at the page" -> `playwright`
- "profile performance in browser" -> `chrome-devtools`
- "talk through trade-offs" -> `sequential-thinking`
- "SwiftUI" or Apple framework names -> `apple-doc-mcp`
- "find contact/company" -> `lusha`

#### Multi-MCP chaining

Detect mixed-domain requests early.

Examples:

- "check my calendar and draft a Slack message" -> `google-calendar` + `slack`
- "read the Jira ticket, inspect the repo, then propose a fix" -> `mcp-atlassian-personal` + `git`
- "search internal docs, then update a Confluence page" -> `glean_default` + `mcp-atlassian-personal`

Rules:

- parallelize reads when safe
- gather state before proposing writes
- chain writes sequentially

### 6. Session Trajectory

Do not orient from the last user message alone.

Look for the arc:

- What skill or action happened just before this?
- What did we learn?
- Is the user moving from ideation -> execution -> validation?
- Did we already choose an approach that this request assumes?

Trajectory cues:

- brainstorm -> "ok go" usually means plan or executor
- debug -> "check it now" usually means verify, test, or audit
- executor -> "pause" means checkpoint, not new work
- resume -> "what's next?" means restore and continue

If a request branches away from the active thread, note that mentally and avoid corrupting the current session model.

### 7. Codebase State

Orient must incorporate what is true in the repo right now.

Check:

- dirty worktree
- recent commits
- active branch
- user changes in progress
- whether the request conflicts with local state

Use codebase state to answer:

- is this safe to do directly?
- do we need to avoid stepping on unfinished work?
- is this request actually about the last commit or current unstaged diff?
- should we inspect a particular module first because recent changes point there?

Repo heuristics:

- uncommitted changes imply continuity and risk
- a clean tree lowers the cost of direct action
- a just-landed commit suggests review or regression-check behavior
- a ticket-linked branch suggests the user expects ticket-driven execution

### 8. Complexity Sizing

Size the task from observed evidence, not vibes.

#### Micro

`just do it`

Signals:

- one coherent local action
- trivial blast radius
- rollback is obvious
- no meaningful uncertainty
- no dedicated verification step needed

Typical examples:

- rename a variable
- fix a typo
- answer a factual question after one read
- add an import
- tweak a comment

#### Small

`do + test`

Signals:

- 1-3 files
- one concern
- clear done state
- at least one verification step is warranted
- still reversible without planning overhead

Typical examples:

- implement a simple helper
- patch a bug in one area
- add or update a focused test
- update docs plus one code path

#### Medium

`lightweight plan`

Signals:

- multiple changes with ordering
- moderate uncertainty
- multi-file or multi-step
- a bug or feature spans layers but not a full program of work
- benefits from an explicit short plan before execution

Typical examples:

- fix a flaky test with several hypotheses
- add UI + API + tests for one feature
- refactor a module with dependent updates

#### Large

`brainstorm + plan + executor`

Signals:

- cross-domain work
- major uncertainty or architectural choice
- a plan document already exists
- many files or multiple independent workstreams
- would benefit from orchestration, parallel execution, or audit passes

Typical examples:

- build a feature from scratch
- implement a long plan doc
- re-architect a subsystem

#### Boundary: where micro ends and small begins

Micro ends the moment any of these become true:

- more than one meaningful edit is required
- a test or build check is needed to trust the change
- the correct change is not self-evident
- the blast radius is larger than the immediate line or local block

That is the boundary. If it needs verification or carries plausible regression risk, it is at least small.

#### ADaPT rule

Try the simpler tier first.

- If it looks small, start small.
- If it looks medium, see whether a small direct pass resolves it.
- If it looks large, ask whether a medium plan-plus-execute path is enough before invoking full orchestration.

Escalate only when:

- the simple approach fails
- the user explicitly asks for the larger workflow
- the complexity is obvious from the start

### 9. Approval Gates

Ask for approval only for external-facing actions.

External-facing means actions that leave the local workspace and affect people, systems of record, or deployed environments.

Approval required:

- sending Slack messages
- sending emails
- creating or mutating Jira, Confluence, or Freshservice records
- changing calendar events
- submitting browser forms or uploads
- deploys and production-affecting operations
- remote pushes or other outward publication steps

Auto-proceed without approval:

- local code edits
- local documentation updates
- tests, lint, builds, audits
- local git inspection
- local branches and local commits
- reading from any MCP
- blackboard reads and writes

If the user has explicitly requested stricter gates, honor that preference.

If authentication or permission is missing, ask instead of guessing.

### 10. Ask-the-User Heuristic

Ask the user only when one of these is true:

- two materially different interpretations are both plausible
- an external-facing action needs approval
- a required credential, path, or identifier is missing
- the user explicitly asked for options before action

When asking, ask one focused question with concrete choices.

Good:

- "Do you want me to treat this as a bug fix or a refactor?"
- "I can draft the Slack message or send it. Which do you want?"

Bad:

- "What do you want to do?"

### 11. Orient Synthesis

Before leaving Orient, silently synthesize all signals into one internal picture:

- current outcome the user wants
- current task type
- session continuity
- codebase constraints
- relevant lessons
- relevant patterns
- capability mix
- smallest correct task size
- whether approval or clarification is needed

Orient is complete only when the next move feels obvious.

## Decide

Decide turns the orientation model into one concrete next move.

### 1. Choose the smallest correct execution mode

- `micro` -> direct action
- `small` -> direct action plus verification
- `medium` -> short written plan plus execution
- `large` -> `panda-brainstorm` if no plan exists, or `panda-executor` if a plan exists

### 1.5 Interactive Plan Approval (medium+ tasks)

Read `~/.claude/panda-config.yml` field `execution.approval_mode`. This controls whether the user sees and approves the plan before execution begins.

#### Mode: `auto` (default legacy behavior)
Skip this section entirely. Execute as before — micro/small just go, medium outlines steps and executes, large routes to brainstorm/executor.

#### Mode: `plan_first` (recommended for collaborative work)
For **medium and large** tasks, present a numbered task list and wait for the user to approve before executing anything.

**Step 1: Generate the plan.**

Build a numbered list of concrete steps based on Orient synthesis. Each step must have:
- A number
- A one-line description of what will be done
- The files that will be touched
- The verification method (test, lint, visual check, or "self-evident")

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

#### Mode: `always_ask`
Same as `plan_first` but applies to **small** tasks too. Only micro tasks (single obvious edit) skip the approval gate.

#### Combining with explicit skill routing

When the mind decides to route to a skill (e.g., panda-debug, panda-executor), the plan approval still applies if the mode is `plan_first` or `always_ask`. Present:

```
For this task, I'd route to panda-debug with this approach:

  1. [ ] Launch panda-debug war room on the flaky auth test
  2. [ ] Apply the fix from debug findings
  3. [ ] Run test suite to verify
  4. [ ] Record experience to blackboard

Approve? Or adjust the approach.
```

This gives the user control over the *strategy* even when delegating to skills.

### 2. Choose direct vs routed execution

Use direct execution when:

- the work is micro or small
- routing overhead adds no value
- the answer can be delivered faster than a delegated workflow

Use a panda skill when:

- its specialized workflow will materially improve the result
- the user explicitly invoked it
- the task is medium/large and the skill is the right vehicle

### 3. Choose any supporting MCP reads

If the request depends on external context, fetch the minimum required state first.

Examples:

- Jira URL -> read the ticket first
- meeting request -> read calendar first
- internal policy question -> search Glean first
- UI bug -> snapshot or inspect browser first

### 4. Decide whether to loop

If the next move will reveal new information, plan to re-enter Observe after the action. This is normal for debugging, investigation, and mixed-tool workflows.

## Act

Act is clean, decisive execution.

### 1. Direct action

For micro and small tasks:

- do the work
- verify if needed
- summarize what changed

Do not over-narrate.

### 2. Skill routing

Before invoking a skill, show one short routing line.

Examples:

- `Routing to panda-debug: this is a flaky failure with real diagnostic uncertainty.`
- `Routing to panda-brainstorm: this is still design-stage and benefits from research-backed planning.`

Then invoke the target skill with the full user input.

### 3. MCP execution

Use:

- parallel reads when safe
- sequential writes
- approval gates only for external-facing actions

### 4. Blackboard updates

After a meaningful action:

1. update `context.json`
2. append a compact decision to `recent_decisions`
3. update `session_metadata.skills_invoked` if a skill was used
4. if a task completed or a notable lesson emerged, record an experience file
5. update `experiences/index.json` after writing the experience

Follow the schema and full-file write rules from `blackboard-schema.md`.

### 5. Loop

After acting:

- if complete, answer and stop
- if new information appeared, return to Observe
- if blocked by approval or missing info, ask the user
- if the simple approach failed, re-orient and escalate one level

## Routing Scenarios

Use these as behavioral tests.

| Input | What Orient notices | Decision |
|---|---|---|
| `debug this flaky test` | bug, uncertainty, likely multiple hypotheses | route to `panda-debug` |
| `help me think through auth design` | ideation, architecture, not implementation yet | route to `panda-brainstorm` |
| `execute ~/.claude/plans/foo.md` | explicit plan path and execution ask | route to `panda-executor` |
| `rename this variable` | one obvious local edit, tiny blast radius | handle directly as `micro` |
| `what would other AIs think about this approach` | explicit multi-model request | route to `panda-council` |
| `audit the wiring` | structural verification request | route to `panda-audit` |
| Jira ticket URL only | ticket-driven work, intent not yet clear | fetch via `mcp-atlassian-personal`, then re-orient |
| `check my calendar and draft a slack message` | mixed-domain workflow, read + external draft/send boundary | read calendar, draft Slack, ask before send |
| `make this better` | ambiguous, insufficient anchor | ask one focused clarifying question |
| `/panda help` | explicit help/menu request | show help menu |
| `I just committed the fix, now check it` | continuation, recent commit validation | inspect diff, run tests or audit, then report |
| `/panda-debug auth race condition` | explicit skill choice | respect explicit route to `panda-debug` |
| `/panda-brainstorm replacement for Okta hooks` | explicit design-phase route | respect explicit route to `panda-brainstorm` |
| `open the page and tell me what looks broken` | visual/browser task | route to `panda-browse` or use browser support if already in-flow |
| `add error handling to the API routes` | medium task, multi-file, `plan_first` mode | present numbered plan for approval, wait for user response, then execute approved steps |
| `refactor auth to support OAuth` (with `plan_first`) | medium-large, multi-file with dependencies | present plan with 5-7 steps, user says "skip 4, for step 3 use passport.js" → adjust and execute |

## Help Menu

When the user asks for help, shows empty input, or says `?` or `menu`, show:

```text
Panda Skills:
  /panda brainstorm [idea]     — Research-backed idea development
  /panda execute [plan-path]   — Autonomous plan execution with agent teams
  /panda debug [description]   — Multi-vector deep debugging war room
  /panda audit                 — Wiring verification
  /panda council [question]    — Multi-model deliberation
  /panda intent                — Manage INTENT.md documentation
  /panda diagram               — Manage architecture diagrams
  /panda codex-gate            — Run adversarial Codex validation
  /panda browse [url]          — Visual verification with browser tools
  /panda pause                 — Save session state for later
  /panda resume                — Resume a paused session
  /panda upgrade               — Check for skill updates
  /panda retro                 — Post-execution retrospective
  /panda config                — Configure panda settings
  /panda mind [anything]       — Full cognitive loop

Or just describe what you need and panda-mind will figure out the smallest correct next move.
```

## Anti-Patterns

Avoid these failures:

- keyword routing without real orientation
- routing a micro task just because a matching skill exists
- asking broad open-ended clarifying questions when a focused one would do
- apologizing for empty memory on cold start
- using past experience to override present repo reality
- escalating to planning when a direct pass would work
- performing external-facing actions without approval
- ignoring explicit skill invocation when it is coherent and safe

## Operating Principles

1. Orient is the differentiator. Without it, this is just a router.
2. Try simple first. Escalate only when reality demands it.
3. Respect explicit user intent.
4. Cold start is full capability, not degraded mode.
5. Experience retrieval must be concrete and selective.
6. Read before write.
7. Session trajectory matters.
8. The best route is often no route at all.
