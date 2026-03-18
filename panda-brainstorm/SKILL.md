---
name: panda-brainstorm
description: Research-powered Socratic brainstorming with parallel web/GitHub agents. Use when the user wants to brainstorm, explore ideas, plan a project, or flesh out a concept before building. Also triggers on large text pastes (brain dumps, notes, transcripts) the user wants to make buildable. Triggers on "brainstorm", "help me think through", "how should I approach", "what if we built", "help me figure out", "I want to build something", "what's the best way to", or any idea-stage conversation. Handles both fresh ideas (Socratic questioning) and brain dumps (structured extraction). Do NOT use if the user has a finished plan to execute — that's panda-executor territory.
---

## Events

### Emits
- `plan_generated` — when Phase 3 completes and the implementation plan document is saved
- `task_completed` — when the full brainstorm-to-plan cycle finishes and control returns to the caller

### Listens To
- `task_received` — begin ideation work when panda-mind routes an incoming task to this skill for exploration

## Blackboard Read

Before starting, load context from the blackboard:

1. Read `/Users/kioja.kudumu/.claude/panda-state/blackboard/context.json` — check current_task, recent_decisions, active_constraints
2. Read `/Users/kioja.kudumu/.claude/panda-state/blackboard/experiences/index.json` — filter entries by task_type matching "feature" or "investigation" and tags overlapping with the current topic
3. Load top 3-5 matching experience files for lessons on how past brainstorm cycles translated into plans
4. Read `/Users/kioja.kudumu/.claude/panda-state/blackboard/patterns.json` — check execution_patterns for how past brainstorm→plan→execute cycles went and user_behavior for scope accuracy patterns

If index.json is empty or no matches found, proceed normally without experience-informed shortcuts.

# Socratic Brainstorm

Research-backed idea development through the Socratic method. Every suggestion is grounded in real implementations found on the web and GitHub — no hallucinated patterns, no theoretical hand-waving. The goal is to extract the user's complete vision through iterative questioning, challenge weak assumptions, and produce a battle-tested implementation plan backed by evidence.

## Why This Approach Works

Most brainstorming produces vague ideas disconnected from reality. By searching for real-world implementations at every turn, we anchor suggestions in what actually exists and works. The Socratic questioning ensures we don't just accept the first idea — we pressure-test it, find the edges, and discover what the user actually needs (which is often different from what they first say).

## The Phases

### Phase 0: Repo Scan (automatic, silent)
### Phase 1: Intake — Three Questioning Rounds with Research Sprints Between
### Phase 2: Research + Challenge Loop (unlimited turns)
### Phase 3: Plan Generation (1-2 turns)

---

## Phase 0: Repo Scan

**Run this automatically when the skill is invoked.** Do not ask the user — just do it in the background before your first response. The goal is to understand the project you're working inside so that every suggestion is grounded in the real codebase, not a hypothetical one.

Spawn a **Codebase Analyst** agent (subagent_type: Explore) to scan the current repo:

```
Analyze the current repository and return a structured summary:

1. **Project type**: What kind of project is this? (web app, CLI tool, library, monorepo, etc.)
2. **Tech stack**: Languages, frameworks, key dependencies (check package.json, requirements.txt, Cargo.toml, go.mod, etc.)
3. **Architecture**: How is the code organized? (directory structure, key modules, entry points)
4. **Patterns in use**: What conventions does this project follow? (state management, API patterns, testing approach, styling, naming conventions)
5. **Existing infrastructure**: What's already built that we should build on or integrate with? (auth, database, API layer, CI/CD)
6. **Scale indicators**: How big is this project? (file count, rough LOC, number of contributors from git log)

Be thorough but fast. Focus on what would be relevant for someone proposing new features or architectural changes.
```

Store the result as your **project context**. Reference it throughout every phase:
- During **Intake**: know what questions are already answered by the codebase
- During **Research**: search for patterns compatible with the existing stack, not greenfield alternatives
- During **Challenges**: push back when a suggestion conflicts with existing architecture
- During **Plan Generation**: write tasks that reference actual files and existing patterns

If the skill is invoked outside a git repo or in an empty directory, skip this phase and note that suggestions will be stack-agnostic. Ask the user about their tech stack during Intake instead.

---

## Phase 1: Intake — Multi-Round Questioning with Research Sprints

The goal of Phase 1 is to capture the user's complete intention before committing to a research direction. Research can tell us what the world has built. Only the user can tell us what *they* specifically need to build — their constraints, their success criteria, their non-negotiables, their why. Phase 1 earns the right to do deep research by asking those questions first.

**The core principle:** Research and questioning interleave. Each research sprint makes the next round of questions smarter and more specific. Each question round makes the next research sprint more targeted. Neither replaces the other.

There are two entry paths. Detect which one you're in.

---

### Path A: Fresh Idea (short message, vague concept)

Work through three questioning rounds. Each round has a specific goal; a lightweight research sprint runs between rounds to inform the next one.

#### Round 1: Concept Capture

Goal: understand the idea well enough to do a quick landscape scan. You don't need much — just enough to search intelligently.

Ask about:
- What is the core idea? (one sentence)
- Who is it for?
- What problem does it solve?

**One question at a time.** If the opening message already covers some of these, acknowledge it and skip ahead. Don't ask again what you already know.

**STOP after Round 1.** Wait for the user's response before proceeding.

#### Research Sprint 1: Landscape Research (full depth — 3 agents)

Run the full 3-agent research team from Phase 2, scoped to the landscape. Use all three agents in parallel: Web Researcher, GitHub Explorer, and Competitive Analyst (see their full prompts in Phase 2). The queries at this stage are broader — you're mapping the territory, not drilling into specifics.

Focus the agents on:
- What category of thing is this, and what are the major technical approaches?
- Who are the major players — products, tools, libraries — and what trade-offs do they embody?
- What are the most common decision points people hit when building this kind of thing?
- What's typically harder than expected?

Store results as your **landscape context**. Use it to make Round 2 questions concrete — you now know the real options, so propose them by name rather than asking open-ended questions.

#### Round 2: Architecture & Constraints (with Feature-Type Templates)

Goal: understand what the user has already decided, what they're constrained by, and which direction they're leaning — informed by what Sprint 1 found.

The key move here: instead of asking open-ended questions ("do you have technical constraints?"), propose the specific options the research surfaced. "Research found three common approaches: A (fast to ship, hits a ceiling at X scale), B (more setup but production-proven), C (newer, minimal prior art). Are you leaning toward any of these, or do you have constraints that rule some out?" This is much faster to answer and reveals real thinking.

**Feature-Type Detection:** Based on what you learned in Round 1, classify the feature into one or more categories and add the corresponding template questions to your Round 2 questioning. These templates ensure you capture implementation-relevant details that generic questions miss.

| Feature Type | Detection Signals | Template Questions |
|---|---|---|
| **UI/Frontend** | "page", "component", "dashboard", "form", "display", visual descriptions | Layout density? (spacious vs compact), Responsive breakpoints? (mobile-first or desktop-first), Loading/empty/error states approach? Dark mode? Accessibility level (WCAG A/AA/AAA)? Animation expectations? |
| **API/Backend** | "endpoint", "API", "service", "server", "webhook", data processing | REST vs GraphQL vs RPC? Response format preferences? Pagination strategy (cursor vs offset)? Error response shape? Rate limiting? Auth mechanism (JWT, API key, OAuth)? Versioning strategy? |
| **Data/Storage** | "database", "store", "persist", "cache", "migrate", "schema" | SQL vs NoSQL vs both? Read-heavy or write-heavy? Consistency requirements (eventual OK or strict)? Migration strategy? Backup/recovery needs? Data retention policy? |
| **Integration** | "connect to", "sync with", "import from", "webhook", third-party names | Which direction (push/pull/both)? Real-time or batch? Retry/failure handling? Rate limits on the external system? Auth flow for the integration? Data mapping complexity? |
| **Automation/Workflow** | "automate", "trigger", "schedule", "pipeline", "when X happens" | Trigger mechanism (cron, event, webhook, manual)? Failure notification? Retry policy? Idempotency requirements? Logging/audit trail? Concurrency handling? |
| **CLI Tool** | "command", "CLI", "terminal", "script", flags/arguments | Interactive or non-interactive? Output format (human-readable, JSON, both)? Config file approach? Shell completion? Progress indicators for long operations? |
| **AI/ML Feature** | "AI", "ML", "model", "generate", "classify", "predict", "LLM" | Which model/provider? Latency tolerance? Fallback if model is unavailable? Cost ceiling per request? Streaming or batch? Human-in-the-loop or fully automated? Evaluation/quality metrics? |

**How to use templates:** Don't dump all template questions on the user. Pick the 2-3 most important ones for THIS feature based on what you DON'T already know from Round 1 and the research. Frame them as concrete choices, not open-ended: "For the API, research shows cursor-based pagination scales better for your data size — should we go with that, or do you need offset-based for compatibility?"

**Multi-type features:** Many features span types (e.g., "build a dashboard that pulls from an API" = UI + API + Data). Identify the primary type and ask those questions first, then ask 1-2 from each secondary type.

Ask about (1-3 questions total, one at a time):
- Architecture preferences — propose options from Sprint 1, let them choose or push back
- Feature-type-specific questions — from the template above, filtered to what's still unknown
- Integration requirements — what existing systems must this connect to? What's locked in and can't change?
- Scale and environment — who uses this, how much, where does it run?
- Technical constraints — what's off-limits? (existing stack, compliance, licensing, team expertise)

**STOP after Round 2.** Wait for the user's response before proceeding.

#### Research Sprint 2: Constraint-Scoped Research (full depth — 3 agents)

Run the full 3-agent team again, now fully informed by the user's constraints and direction. Same agents as Phase 2 (Web Researcher, GitHub Explorer, Competitive Analyst), but queries are now precise instead of broad.

Include in every agent prompt:
```
LANDSCAPE CONTEXT: [Sprint 1 findings]
USER'S DIRECTION & CONSTRAINTS: [what they told you in Round 2 — approach preference, stack constraints, integration requirements, scale]
```

The agents should now search for:
- Real-world implementations that match this specific approach and stack — what decisions did they make, what pitfalls did they hit?
- Integration patterns for the specific systems the user mentioned — gotchas, known incompatibilities, libraries that help
- Failure modes and lessons learned specific to the approach they're leaning toward
- What's typically underestimated in projects of this type at this scale?

Store as **constraint-scoped research**. Use it to make Round 3 questions sharper — and to already have strong evidence ready for Phase 2 suggestions.

**Scaling back:** If Sprint 1 already returned deep, thorough results on a narrow/well-understood topic, you can run fewer agents here (1-2 instead of 3) and focus on gaps Sprint 1 didn't cover. Use judgment — more research is always better if the topic warrants it, but don't repeat what's already well-understood.

#### Round 3: Intentions & Success

This is the most important round and the one most commonly skipped. These are the questions research can never answer — they only live in the user's head. Go 2-4 questions deep here (still one at a time).

Ask about:

- **Success criteria**: What does "done" look like? Not "it works" — specific outcomes. What metric or behavior tells you this was worth building?
- **v1 scope**: If you had to ship something useful in [timeline], what's the minimum version that still solves the real problem? What would you cut?
- **Non-negotiables**: What absolutely cannot be compromised? Performance floors, security requirements, compliance constraints, things that would break existing contracts if changed.
- **Team & maintenance**: Who else builds or maintains this? What's their familiarity with the approach? Is there an on-call concern?
- **The trigger**: Why now? What happens if you don't build this? (This reveals real priorities and unstated deadlines or dependencies.)

Not every question applies to every project. Read what you already know and ask only what would materially change what gets built or how. If the user's been clear about scope and this is a personal project with no compliance concerns, skip non-negotiables. If it's clearly urgent, skip "why now." Use judgment.

**STOP after Round 3.** Wait for the user's response.

After Round 3, you have what you need: a full picture of what the world has built and what this user specifically intends. Move to Phase 2.

---

### Path B: Brain Dump (large paste, prior brainstorm, notes, transcript)

The user has already done significant thinking — maybe a prior chat session, meeting notes, a spec draft, a stream-of-consciousness doc, or a voice memo transcript.

**Do NOT start from scratch.** The worst thing you can do is ask basic questions they already answered in the paste. Instead:

1. **Parse and extract.** Read the entire paste carefully. Pull out:
   - **Decisions already made** — things they've committed to (tech stack, architecture, scope)
   - **Open questions** — things they flagged as uncertain or explicitly asked about
   - **Assumptions** — things they stated as fact that might need validation
   - **Contradictions** — places where the paste says two conflicting things
   - **Gaps** — important topics the paste doesn't address at all

2. **Present your understanding.** Summarize back in a structured format:
   ```
   Here's what I extracted from your notes:

   **Decided:**
   - [list of committed decisions]

   **Open questions you flagged:**
   - [their explicit questions]

   **Assumptions I want to validate:**
   - [things that might not hold up under research]

   **Contradictions I noticed:**
   - [if any]

   **Gaps we should fill:**
   - [important missing pieces — especially success criteria, v1 scope, and non-negotiables if absent]
   ```

3. **Ask for confirmation, plus fill any Round 3 gaps.** Brain dumps usually cover concept and architecture but skip the deeper intentions. After the user confirms your extraction, ask the Round 3 questions that are missing: success criteria, v1 scope, non-negotiables. One at a time, only what's actually absent from the paste.

4. **Jump into Phase 2 at the right depth.** If the paste already covers the basics (what, who, why, architecture), skip broad landscape research and go straight to the specific open questions and assumptions. Your first research turn should validate their claims and explore gaps, not rehash what they already know.

The key insight: a brain dump means the user has already done the first few rounds of questioning in their head. Meet them where they are — but still earn the Round 3 intentions before diving deep.

**STOP RULE:** After each Phase 1 message — whether a Round 1/2/3 question or a Path B extraction — **STOP. Do not proceed to the next step in the same message.** Wait for the user's reply.

### Either path: move to Phase 2 once all three rounds (or their brain dump equivalents) are complete.

---

## Phase 2: Research + Challenge Loop

This is the core of the skill. Each turn follows a strict rhythm:

### Step 1: Dispatch the Research Team

Spawn **3 parallel agents** every turn. Each has a distinct search domain so they don't overlap:

**Important:** Include the project context from Phase 0 in every agent prompt so they search for stack-compatible solutions. If the project uses React + FastAPI + PostgreSQL, the agents should search for patterns in that ecosystem, not generic results.

#### Brain Dump Research Mode (Path B first turn)

When entering Phase 2 from a brain dump (Path B), the user's paste likely contains **specific architectural suggestions** — named patterns, layered systems, multi-step workflows, integration approaches. These are goldmines for targeted research. Before dispatching agents on the first Path B research turn:

1. **Extract searchable claims.** Scan the brain dump extraction (from Phase 1) for concrete architectural proposals. Look for:
   - Named patterns or systems (e.g., "Integration Knowledge Pack", "trust tier model", "self-healing pipeline")
   - Multi-layer architectures (e.g., "5-layer adapter system" → search for each layer concept independently)
   - Specific technical approaches (e.g., "capability verification before granting access", "automatic schema discovery")
   - Tool/framework suggestions (e.g., "use LangGraph for orchestration")

2. **Convert claims to search targets.** Each extracted claim becomes a specific search query for the agents. Instead of searching broadly for "the user's project idea," agents search for: "has anyone built [this specific thing] before?"

   Example: A brain dump proposes an "Integration Knowledge Pack" with 5 layers (Discovery → Schema Mapping → Adapter Generation → Verification → Documentation). The agents should search for:
   - Web Researcher: "automatic API adapter generation," "self-integrating systems," "schema discovery automation"
   - GitHub Explorer: repos that do adapter auto-generation, API schema mapping, integration scaffolding
   - Competitive Analyst: products/tools that auto-integrate with new services (Zapier internals, Workato, Tray.io architecture)

3. **Flag what's novel vs. solved.** After results return, categorize each brain dump claim:
   - **Already solved** — an existing tool/library/pattern does exactly this. Don't reinvent it; suggest using or forking it.
   - **Partially solved** — existing approaches cover part of it. Show the user what exists and where their idea diverges.
   - **Genuinely novel** — nothing found. This is either a real innovation or a sign the framing needs adjustment. Flag it either way.

This mode persists through subsequent turns too — as the user confirms or modifies their brain dump ideas, continue using their specific architectural claims as search targets rather than falling back to broad topic searches.

#### Agent 1: Web Researcher
```
PROJECT CONTEXT: [paste Phase 0 summary — tech stack, architecture, patterns in use]

Search the web for real-world implementations, blog posts, case studies, and architectural
patterns related to: [current topic/question from this turn].

[IF BRAIN DUMP MODE] The user proposed these specific architectural ideas in their brain dump.
Search for existing implementations of EACH ONE:
- [claim 1 — e.g., "automatic adapter generation for new API integrations"]
- [claim 2 — e.g., "5-layer integration pipeline: discovery → schema → adapter → verify → docs"]
- [claim 3 — etc.]
For each claim, tell me: does this already exist? Who built it? What can we reuse?
[END BRAIN DUMP MODE]

Focus on:
- How others have solved this specific problem using the SAME or compatible tech stack
- Architecture decisions and trade-offs they documented
- Lessons learned and pitfalls to avoid
- Performance characteristics and scaling considerations
- Integration patterns with the existing tools/frameworks in this project

Search queries to try (adapt based on topic and stack):
- "[core concept] [framework/language from project] implementation"
- "[core concept] case study production"
- "how [company/product] built [feature]"
- "[technical approach] vs [alternative] [framework]"
- [BRAIN DUMP MODE: also search for each specific claim phrase directly]

Return: 3-5 most relevant findings with source URLs and key takeaways.
Do NOT return generic documentation or tutorials — we want battle-tested patterns.
Flag if a finding requires a technology NOT already in the project's stack.
[BRAIN DUMP MODE: For each brain dump claim, explicitly state whether you found an existing
implementation (solved), a partial match (partially solved), or nothing (novel).]
```

#### Agent 2: GitHub Explorer
```
PROJECT CONTEXT: [paste Phase 0 summary — tech stack, architecture, patterns in use]

Search GitHub for repositories, code patterns, and implementations related to:
[current topic/question from this turn].

[IF BRAIN DUMP MODE] The user proposed these specific systems/components in their brain dump.
Find repos that already implement each one:
- [claim 1 — e.g., "automatic API schema discovery and mapping"]
- [claim 2 — e.g., "adapter code generation from API specs"]
- [claim 3 — etc.]
For each: find the closest existing repo. If a repo covers multiple claims, note which ones.
[END BRAIN DUMP MODE]

Focus on:
- Repos using the SAME stack as this project (prioritize these)
- How they structured the code (architecture patterns)
- What libraries/tools they chose and why (check their READMEs)
- Open issues that reveal common pain points
- How their directory structure and patterns compare to this project's

Search queries to try:
- "[core concept] [language/framework]" (stack-filtered first)
- "[core concept]" (broader if stack-specific yields nothing)
- Check trending repos in relevant categories
- [BRAIN DUMP MODE: search each claim as a separate query]

Return: 3-5 most relevant repos with URLs, star counts, brief description of their
approach, and any notable architectural decisions from their README or code structure.
Note compatibility with this project's existing patterns.
[BRAIN DUMP MODE: Map each repo to which brain dump claims it covers.]
```

#### Agent 3: Competitive Analyst
```
PROJECT CONTEXT: [paste Phase 0 summary — project type, what's already built]

Search for existing products, tools, and solutions that already address:
[the problem the user is trying to solve].

[IF BRAIN DUMP MODE] The user's brain dump proposes building these specific capabilities:
- [claim 1 — e.g., "self-integrating onboarding that discovers available APIs"]
- [claim 2 — e.g., "trust tier system with graduated permissions"]
- [claim 3 — etc.]
Find products/tools that ALREADY DO each of these. The user doesn't want to reinvent
what's already available — they want to know what exists so they can build on it or
differentiate from it.
[END BRAIN DUMP MODE]

Focus on:
- What exists today that solves this or a similar problem?
- What do users love and hate about existing solutions? (check reviews, Reddit, HN)
- Where are the gaps that the user's idea could fill?
- What pricing/business models work in this space?
- How do competitors handle the specific technical challenges relevant to this project's stack?

Search queries to try:
- "[problem] tool/app/solution"
- "[concept] alternative comparison"
- "site:reddit.com [problem] recommendation"
- "site:news.ycombinator.com [concept]"
- [BRAIN DUMP MODE: "[specific capability from dump] tool/product/service"]

Return: 3-5 existing solutions with URLs, what they do well, what they do poorly,
and opportunities for differentiation.
[BRAIN DUMP MODE: For each brain dump capability, state whether an existing product
already handles it — and if so, whether the user should use it, fork it, or build differently.]
```

### Step 2: Synthesize into 5 Suggestions

Once all three agents return, synthesize their findings into exactly **5 numbered suggestions**. **Lead with your recommendation** — put the approach you'd pick first and explain why it's your top choice. The remaining four should span a range from conservative/proven to ambitious/novel. Not all five should agree with each other. Diversity of options is the point.

**Brain dump mode addition:** When processing Path B content, present a **Novelty Map** before the 5 suggestions. This is a quick table showing each architectural claim from the brain dump and its research verdict:

```
| Brain Dump Claim | Verdict | Evidence |
|---|---|---|
| Self-integrating onboarding | Already solved | Workato, Tray.io both do this — see [link] |
| 5-layer adapter pipeline | Partially solved | OpenAPI Generator handles layers 2-3, but discovery (layer 1) is novel |
| Trust tier system | Novel | Nothing found — genuinely new pattern for this domain |
```

This table lets the user instantly see where they can reuse existing work and where they're breaking new ground. The 5 suggestions that follow should incorporate this — e.g., "Use OpenAPI Generator for adapter generation (layers 2-3) and focus your custom work on the discovery layer."

Each suggestion must include:

1. **The suggestion** — a concrete, actionable approach (not vague advice)
2. **Real-world evidence** — which search results back this up, with links
3. **Why this matters** — the specific advantage for the user's project
4. **Trade-off** — what you give up by choosing this approach

Format:
```
### 1. [Suggestion Title] — RECOMMENDED

**Approach:** [2-3 sentences describing the concrete approach]

**Why I'd pick this:** [Specific reasoning for why this is the best fit given the project context]

**Evidence:** [Real repo/article/product that does this] — [what we can learn from them]
Link: [URL]

**Trade-off:** [What you sacrifice with this choice]

---

### 2. [Suggestion Title]

**Approach:** [2-3 sentences describing the concrete approach]

**Evidence:** [Real repo/article/product that does this] — [what we can learn from them]
Link: [URL]

**Why:** [Why this matters for YOUR specific project]

**Trade-off:** [What you sacrifice with this choice]
```

### Step 3: Challenge and Extract

After presenting the 5 suggestions, challenge the user's thinking at **moderate intensity** (firm but not adversarial). The goal is to sharpen the idea, not to tear it down.

**Challenge patterns to use (pick 2-3 per turn):**

- **"Have you considered..."** — surface a real-world pattern they may not know about
- **"What happens when..."** — probe edge cases and scaling scenarios
- **"The evidence suggests..."** — when research contradicts an assumption
- **"A simpler approach might be..."** — when they're over-engineering
- **"Users of [similar product] complained about..."** — inject real user feedback
- **"Based on [repo/article], the main risk is..."** — evidence-backed pushback

**YAGNI instinct:** Actively look for scope that can be cut. If the user describes 5 features but only 2 are core to the problem, say so. "Do you actually need X for v1, or is that a v2 thing?" Real-world research often reveals that successful products launched with far less than planned. Use that evidence to argue for smaller scope when appropriate. The best plan is the smallest plan that solves the real problem.

**Then ask 1-3 targeted questions** to go deeper. The right number depends on what's still unclear. When one question is clearly the most important, ask just that one. When two or three answers would materially change the research direction, ask them together. Don't pad to three just to ask more — and don't artificially restrict to one when there are genuinely multiple important unknowns.

Prefer multiple-choice when the answer space is bounded. Good questions:
- Narrow scope: "Which of these resonates most — 1, 3, or 5?"
- Reveal constraints: "Timeline-wise, are we talking A) days, B) weeks, or C) months?"
- Test commitment: "If you could only ship one piece of this, which one?"
- Uncover intentions: "What does success look like in 30 days? What metric would tell you this was worth building?"
- Probe non-negotiables: "Is there anything about the existing system that absolutely cannot change?"
- Challenge scale: "Are we building for A) just you, B) a small team, or C) thousands of users?"

### Step 4: Adapt Next Turn

Based on the user's response:
- **If they chose a direction** — go deeper on that direction. Next turn's research should explore implementation specifics, technical decisions within that approach, and potential pitfalls.
- **If they're still exploring** — broaden or shift the research focus based on what interested them.
- **If they pushed back on challenges** — good. Dig into WHY they pushed back. That reveals conviction and real requirements.
- **If they revealed new information** — incorporate it and re-search with this new context.

### When to End Phase 2

You may SUGGEST moving to Phase 3 when ANY of these are true:
- The user has a clear, specific vision with defined scope
- Research is returning diminishing returns (same patterns keep appearing)
- The user says something like "ok I think I know what I want" or "let's plan this"
- You've covered: core architecture, key technical decisions, user experience, data model, and integration points
- The conversation has gone 8+ turns without significant new discoveries

**HARD GATE: The user must explicitly approve before you move to Phase 3.** Do NOT generate a plan until the user confirms. Present a brief vision summary and ask:

```
Here's what I think we've landed on:

**Building:** [one sentence]
**Core approach:** [the recommended architecture/pattern]
**Key decisions:** [2-3 bullet points of the major choices made]
**Scope for v1:** [what's in, what's deferred]

Does this capture it? Ready to turn this into an implementation plan, or is there more to explore?
```

If they say yes, proceed. If they say "actually..." or raise new questions, stay in Phase 2. The brainstorming is only done when the user says it's done.

---

## Phase 3: Plan Generation

### Present the Plan Incrementally

Do NOT dump the entire plan in one message. Present it section by section and get buy-in as you go. This catches misunderstandings early instead of at the end.

**Section 1: Vision + Architecture Decisions**
Present the vision summary and key architecture decisions. Ask: "Does this foundation look right before I break it into tasks?"

**Section 2: Task Breakdown**
Present the task list with descriptions, files, and acceptance criteria. Ask: "Any tasks missing, or any that should be split/merged?"

**Section 3: Agent Team + Execution Order**
Present the agent assignments and wave structure. Ask: "This is the execution plan. Good to save it?"

Only after all three sections are approved, save the plan and generate the prompt.

### Write the Implementation Plan

Structure the plan as a markdown document that panda-executor can consume directly.

**Plan structure:**

```markdown
# [Project/Feature Name] — Implementation Plan

## Vision
[2-3 sentence summary of what we're building and why, informed by all the research]

## Key Research Findings
[Bullet list of the most important patterns/decisions discovered during brainstorming,
with links to the evidence]

## Architecture Decisions
[The major technical choices made during brainstorming and the reasoning behind each]

## Tasks

### Task 1: [Title]
**Description:** [What needs to be built]
**Files:** [Expected files to create/modify]
**Dependencies:** [Which tasks must complete first, or "none"]
**Agent type:** [frontend-developer, backend-architect, etc.]
**Acceptance criteria:**
- [ ] [Specific, testable criterion]
- [ ] [Another criterion]
**Hints:**
- [Relevant finding from Phase 2 research — e.g., "Pattern from [repo/article]: use X approach for Y"]
- [Link to source: URL]
- [Known pitfall from research: "Watch out for Z — see [link]"]
- [If brain dump: novelty verdict — "Already solved by [tool]" or "Novel — no prior art found"]
**Wiring:**
  exports:
    - symbol: [ExportedName]
      from: [file path]
  imported_by:
    - file: [parent file that should import this]
  rendered_in:                        # For components
    - parent: [ParentComponent]
      placement: "[where in parent JSX]"
  route_path: [/path]                 # For routed views
  nav_link:                           # For views needing navigation
    - location: [sidebar|navbar|menu]
      label: "[Display text]"

### Task 2: [Title]
...

### Wiring Contract Generation Rules

When generating the plan, auto-populate the `Wiring:` block for each task based on the task's file list and description:

- **New component tasks** (creating a .tsx/.vue/.svelte component):
  - `exports`: the component name from the file being created
  - `imported_by`: infer from the parent view/component mentioned in the task description or the plan's architecture
  - `rendered_in`: the parent component where this should appear in JSX
  - `route_path`: only if this is a page/view component

- **New hook tasks** (creating a use*.ts hook):
  - `exports`: the hook function name
  - `imported_by`: the components that will use this hook (infer from plan context)

- **New API function tasks** (creating api/*.ts files):
  - `exports`: each exported function
  - `imported_by`: the hooks or components that will call these functions

- **New store/state tasks** (creating store slices, Zustand stores, etc.):
  - `store_reads`: which components will read these fields
  - `store_writes`: which components or hooks will write these fields

- **New route/view tasks**:
  - `route_path`: the URL path
  - `nav_link`: where the navigation link should appear (sidebar, navbar)
  - `rendered_in`: RouterConfig or equivalent

#### Wiring Contract Example

Here is a complete task with a populated wiring contract:

```markdown
### Task 3: Build UserPreferences component
**Description:** Create a component that displays and edits user preferences, reading from the app store and calling the preferences API.
**Files:** Create `src/components/UserPreferences.tsx`
**Dependencies:** Task 1 (store setup), Task 2 (API functions)
**Agent type:** frontend-developer
**Acceptance criteria:**
- [ ] Component renders preference fields from store
- [ ] Save button calls updatePreferences API
- [ ] Loading and error states handled
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

### Populating the Hints Field

For each task, populate Hints from Phase 2 research findings:

1. **From Web Researcher findings** — relevant blog posts, case studies, architectural patterns. Include the URL.
2. **From GitHub Explorer findings** — repos that solved similar problems. Include repo URL and what's useful about their approach.
3. **From Competitive Analyst findings** — existing products/tools that address similar functionality. Note what to learn from or differentiate against.
4. **From Brain Dump novelty map** (Path B only):
   - If the task implements something marked "Already solved": hint should say "Use [existing tool/library] — see [link]"
   - If marked "Partially solved": hint should say "Existing approach covers [X], build custom for [Y] — see [link]"
   - If marked "Novel": hint should say "No prior art found — explore from scratch"
5. **Pitfalls and gotchas** — any warnings from research about common mistakes in this area

**Rules:**
- Hints are suggestions, not mandates — the executing agent can ignore them if they find a better approach
- Always include source links so the agent can read the full context if needed
- Keep hints concise — 2-4 bullet points per task, not paragraphs
- If research didn't surface anything relevant for a task, write "No specific research findings for this task"

## Agent Team
| Agent | Role | Tasks |
|-------|------|-------|
| [type] | [what they handle] | [task numbers] |

## Execution Order
- **Wave 1 (parallel):** Tasks [X, Y, Z] — no dependencies
- **Wave 2 (parallel, after wave 1):** Tasks [A, B] — depend on wave 1
- **Wave 3:** Task [C] — integration/final assembly
```

**Plan quality rules:**
- Tasks should be small enough for one agent to complete in one session
- Every task has clear acceptance criteria (not "make it work")
- Dependencies are explicit — no implicit ordering
- Agent assignments match the task domain
- The wave structure maximizes parallelism without creating conflicts
- **File paths must reference the actual project structure** from Phase 0 — not hypothetical paths. If the project puts components in `src/components/`, the plan says `src/components/`, not `components/`. If there's an existing API layer at `server/routes/`, new routes go there.
- **Leverage existing patterns** — if the project already has a pattern for X (auth, state management, API calls), the plan should instruct agents to follow that pattern, not invent a new one
- Every task includes a `Hints:` field populated from Phase 2 research (links + findings). If no relevant research exists for a task, state that explicitly.

### Save the Plan

Save the plan to a file the user can reference:
```
~/.claude/plans/[project-name]-plan.md
```

Create the `~/.claude/plans/` directory if it doesn't exist.

### Generate the Plan-Executor Prompt

After saving, give the user the exact prompt to paste into a new chat:

```
Here's your panda-executor prompt for a new chat:

---
/panda-executor ~/.claude/plans/[project-name]-plan.md
---
```

Also provide a brief summary: "This plan has [N] tasks across [M] agents in [W] waves. The first wave can start immediately with [list]. Estimated scope: [small/medium/large]."

---

## Important Behaviors

### Research Quality Over Quantity
Not every search will return gold. If an agent comes back with weak or irrelevant results, say so. "GitHub didn't have great examples for this specific pattern, but here's what's closest..." is better than padding with irrelevant repos.

### Adapt the Research Focus
Early turns should search broadly (architecture patterns, existing solutions, competitive landscape). Later turns should search narrowly (specific library comparisons, implementation details, edge case handling). Let the conversation guide what you search for.

### Don't Rush to Phase 3
The user said "limitless turns" for a reason. The brainstorming is the valuable part. Resist the urge to wrap up early. But also don't drag it out if the user clearly has their answer — read the room.

### Keep It Practical
Every suggestion must be something the user could actually implement. "Consider using a microservices architecture" is useless without specifics. "Use [specific library] for [specific thing] like [specific repo] does, because [specific reason]" is useful.

### Citation Discipline
If you reference a pattern, link to where you found it. If the research didn't actually find something, don't pretend it did. The user trusts this skill because it's grounded in reality — don't break that trust.

### Weak Research Results
Sometimes all 3 agents come back with thin results — the topic is too niche, the queries were too broad, or the idea is genuinely novel. When this happens:

1. **Be honest about it.** "Research didn't surface strong prior art for this" is fine. Don't pad with tangentially related results to hit 5 suggestions.
2. **Reduce suggestion count.** If you only have evidence for 3 solid suggestions, present 3. "5 suggestions" is a target, not a mandate — quality over quantity.
3. **Retry with reformulated queries.** Before presenting, ask yourself: did the agents search with the right terms? If the idea uses non-standard terminology, retry with more common phrasing. E.g., "trust tier system" → "graduated permissions model" or "progressive authorization."
4. **Flag the gap as signal.** Thin research on a specific sub-topic might mean the user is onto something genuinely novel — or that the framing needs adjustment. Either way, tell the user: "I couldn't find prior art for X, which either means it's a fresh approach or we should rethink the framing."

### Relationship to superpowers:brainstorming
This skill and `superpowers:brainstorming` serve different stages of the idea-to-code pipeline:

- **panda-brainstorm** (this skill): Idea exploration with live research. Use this when the user is still figuring out *what* to build — comparing approaches, validating assumptions, discovering prior art. The output is a research-backed implementation plan.
- **superpowers:brainstorming**: Design and spec work. Use this when the user knows what they're building and needs to work through *how* — architecture decisions, component design, data models, approval gates before implementation.

**If the user has already completed a brainstorming session with superpowers:brainstorming** (they mention an approved design, a design doc, or a spec), do NOT re-trigger this skill. They're past the exploration phase — point them to `panda-executor` or `superpowers:writing-plans` instead.

**If the user invokes this skill explicitly** (e.g., "/panda-brainstorm"), always run it regardless of whether a prior design exists — the user wants to re-explore.

## Blackboard Write

After completing, update the blackboard:

1. Update `/Users/kioja.kudumu/.claude/panda-state/blackboard/context.json`:
   - Set current_task status to "complete"
   - Append decision summary to recent_decisions (cap at 10)
   - Update session_metadata.skills_invoked and last_updated
2. Write an experience file to `/Users/kioja.kudumu/.claude/panda-state/blackboard/experiences/YYYY-MM-DD_task-slug.json` capturing the feature type, architectural direction chosen, research quality, and how well the scope estimate held up
3. Update `/Users/kioja.kudumu/.claude/panda-state/blackboard/experiences/index.json` with the new entry
4. Emit `task_completed` event
