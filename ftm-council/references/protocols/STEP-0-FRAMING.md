# Step 0: Frame the Problem

> **Note:** This step is skipped in auto-invocation mode. If a structured conflict payload was provided, proceed directly to Step 1 using the payload as the council prompt.

Take the user's request and distill it into a clear **council prompt** — a self-contained problem statement that makes sense without conversation history. The prompt should describe the problem and what a good answer looks like, but it should NOT include pre-read code. The models will read the code themselves.

## What to Include

- The specific question or decision to be made
- File paths or areas of the codebase to start investigating (as pointers, not content)
- Error messages or symptoms if it's a debugging problem
- Decision criteria — what a good answer looks like
- Any constraints the user has mentioned

## What to Exclude

- Pre-read file contents (each model reads files itself)
- Your own analysis or opinion about the problem
- Summaries of what the code does (let each model discover that)

## Confirmation Gate

Show the user the framed prompt before proceeding: "Here's what I'll send to the council — does this capture the problem?" Wait for confirmation or edits.

## Structured Payload Format

When creating the council prompt, use this structure:

```
PROBLEM:
[Clear statement of the question or decision]

CODEBASE ENTRY POINTS:
[File paths or directories to investigate — no content, just paths]

SYMPTOMS / ERROR MESSAGES:
[If debugging: exact error text, stack traces, reproduction steps]

DECISION CRITERIA:
[What a good answer looks like — what tradeoffs matter here]

CONSTRAINTS:
[Any hard requirements, technology restrictions, or non-negotiables]
```

The prompt must be fully self-contained. A model dropped into a fresh session with only this prompt should know exactly what to investigate and what success looks like.
