# Rebuttal Round Prompt Template

Use this to construct the prompt sent to each model in rebuttal rounds (Steps 3-4). The prompt must be fully self-contained — Codex and Gemini are stateless between rounds, so every round's prompt must include the full history.

## Template

```
Round {N} of the deliberation council.

Here's what happened in the previous round. Each model independently researched the codebase and formed a position:

MODEL A's research and position:
{model_a_previous_full}

MODEL B's research and position:
{model_b_previous_full}

MODEL C's research and position:
{model_c_previous_full}

Now respond. You may do additional codebase research if you want to verify claims the other models made or investigate angles they raised. Then:

1. Directly address the strongest point from each other model
2. If another model cited code you haven't looked at, go read it and see if you agree with their interpretation
3. State whether you've changed your position (and why, or why not)
4. If you agree with another model, say so explicitly

UPDATED POSITION: [same/changed] ...
NEW EVIDENCE (if any): [anything new you found by following up on other models' research]
KEY RESPONSE TO MODEL A: ...
KEY RESPONSE TO MODEL B: ...
REMAINING DISAGREEMENTS: ...
```

## Construction Rules

- Replace `{model_a/b/c_previous_full}` with each model's complete response from the prior round — research summary, position, reasoning, concerns, and confidence
- Do NOT summarize or truncate prior responses — the full research context is what allows models to verify each other's findings
- Include ALL prior rounds' positions if building a multi-round history, not just the most recent
- Use the same CLI flags as Round 1 (`--full-auto` for Codex, `--yolo` for Gemini) so models can do follow-up research

## Orchestrator State

Between rounds, the orchestrator holds all state. Keep a running record of:
- Each model's research findings per round (files examined, what was found)
- Each model's position per round
- Whether any model changed position and why

This record feeds the next round's rebuttal prompt. Without it, models cannot engage meaningfully with each other's evidence.

## What to Watch For

When presenting round results to the user, highlight:
- **Position changes**: which model moved and what evidence caused the shift
- **New research**: if a model read files others hadn't looked at
- **Convergence signal**: models independently finding the same evidence
- **Persistent divergence**: models who've both read the same code and still disagree — this is a genuine hard problem
