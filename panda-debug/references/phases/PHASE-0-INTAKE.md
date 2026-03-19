# Phase 0: Problem Intake

Before launching agents, understand what you're debugging. This happens in the main conversation thread — no agents yet.

## Step 1: Gather the Problem Statement

If the user hasn't already described the bug in detail, ask targeted questions (one at a time, skip what you already know from conversation history):

1. **What's happening?** — The symptom. What does the user see/experience?
2. **What should be happening?** — The expected behavior.
3. **What have you already tried?** — Critical context. Don't duplicate wasted work.
4. **When did it start?** — A recent change? Always been broken? Intermittent?
5. **Can you trigger it reliably?** — Reproduction steps if they exist.

## Step 2: Codebase Reconnaissance

Spawn an **Explore agent** to scan the relevant area of the codebase:

```
Analyze the codebase around the reported problem area:

1. **Entry points**: What are the main files involved in this feature/behavior?
2. **Call graph**: Trace the execution path from trigger to symptom
3. **State flow**: What state (variables, stores, databases, caches) does this code touch?
4. **Dependencies**: What external libs, APIs, or services are in the path?
5. **Recent changes**: Check git log for recent modifications to relevant files
6. **Test coverage**: Are there existing tests for this code path? Do they pass?
7. **Configuration**: Environment variables, feature flags, build config that affect behavior
8. **Error handling**: Where does error handling exist? Where is it missing?

Focus on the area described by the user. Map the territory before anyone tries to change it.
```

Store the result as **codebase context**. Every subsequent agent receives this.

## Step 3: Formulate the Investigation Plan

Based on the problem statement and codebase context, decide:

1. **Which debug vectors are relevant?** Not every bug needs all 7 agents. A pure logic bug doesn't need instrumentation. A well-documented API issue might not need research. Pick what helps.
2. **What specific questions should each agent answer?** Generic "go investigate" prompts produce generic results. Targeted questions produce answers.
3. **What's the most likely root cause category?** (Race condition? State corruption? API contract mismatch? Build/config issue? Logic error? Missing error handling?) This focuses the investigation.

Present the investigation plan to the user:

```
Investigation Plan:
  Problem: [one-line summary]
  Likely category: [race condition / state bug / API mismatch / etc.]
  Agents deploying:
    - Instrumenter: [what they'll instrument and why]
    - Researcher: [what they'll search for]
    - Reproducer: [reproduction strategy]
    - Hypothesizer: [which code paths they'll analyze]
  Worktree strategy: [how many worktrees, branch naming]
```

Then proceed immediately unless the user objects.
