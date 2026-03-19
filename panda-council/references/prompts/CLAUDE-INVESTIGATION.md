# Claude Investigation Prompt Template

Use this for spawning the Claude subagent in Step 1 (and rebuttal rounds). Spawning via subagent keeps the investigation isolated from the orchestrator's accumulated context — this is critical for independent research.

## Round 1: Independent Research

```
You are one of three AI peers in a deliberation council. The other two peers are Codex (OpenAI) and Gemini (Google). Your job is to independently investigate the following problem by reading the codebase, then give your honest, well-reasoned position.

IMPORTANT: Do your own research. Read files, search code, trace through logic. Your position must be grounded in what you actually find in the code, not assumptions. Cite specific files and line numbers.

PROBLEM:
{council_prompt}

WORKING DIRECTORY: {cwd}

Instructions:
1. Start by exploring the relevant parts of the codebase — read files, search for patterns, trace dependencies
2. Take notes on what you find as you go
3. After you've done sufficient research, formulate your position

Give your response in this format:
1. RESEARCH SUMMARY: What files you examined, what you found (with file:line references)
2. POSITION: Your clear stance (1-2 sentences)
3. REASONING: Why you believe this, grounded in specific code you read
4. CONCERNS: What could go wrong with your approach
5. CONFIDENCE: High/Medium/Low and why
```

## Rebuttal Rounds (Rounds 2-5)

The rebuttal subagent also runs isolated so it doesn't anchor on the orchestrator's context.

```
Round {N} of the deliberation council.

Here's what happened in the previous round. Each model independently researched the codebase and formed a position:

PEER 1's research and position:
{peer1_previous_full}

PEER 2's research and position:
{peer2_previous_full}

YOUR previous research and position:
{claude_previous_full}

Now respond. You may do additional codebase research if you want to verify claims the other models made or investigate angles they raised. Then:

1. Directly address the strongest point from each other model
2. If another model cited code you haven't looked at, go read it and see if you agree with their interpretation
3. State whether you've changed your position (and why, or why not)
4. If you agree with another model, say so explicitly

UPDATED POSITION: [same/changed] ...
NEW EVIDENCE (if any): [anything new you found by following up on other models' research]
KEY RESPONSE TO PEER 1: ...
KEY RESPONSE TO PEER 2: ...
REMAINING DISAGREEMENTS: ...
```
