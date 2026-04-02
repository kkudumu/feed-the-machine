# Gemini Investigation Prompt Template

Use this for spawning Gemini via CLI. The `--yolo` flag lets Gemini auto-approve file reads so it can explore without getting stuck on permission prompts.

## Round 1: Independent Research

```bash
cd {cwd} && gemini -p "You are one of three AI peers in a deliberation council. The other two peers are a subagent investigator and Codex (OpenAI). Your job is to independently investigate the following problem by reading the codebase, then give your honest, well-reasoned position.

IMPORTANT: Do your own research. Read files, search code, trace through logic. Your position must be grounded in what you actually find in the code, not assumptions. Cite specific files and line numbers.

PROBLEM:
{council_prompt}

Instructions:
1. Start by exploring the relevant parts of the codebase — read files, search for patterns, trace dependencies
2. Take notes on what you find as you go
3. After you have done sufficient research, formulate your position

Give your response in this format:
1. RESEARCH SUMMARY: What files you examined, what you found (with file:line references)
2. POSITION: Your clear stance (1-2 sentences)
3. REASONING: Why you believe this, grounded in specific code you read
4. CONCERNS: What could go wrong with your approach
5. CONFIDENCE: High/Medium/Low and why" --yolo
```

## Rebuttal Rounds (Rounds 2-5)

Use `--yolo` in rebuttal rounds as well — Gemini may want to verify another model's claims by reading files it hadn't looked at before.

```bash
cd {cwd} && gemini -p "Round {N} of the deliberation council.

Here's what happened in the previous round. Each model independently researched the codebase and formed a position:

PEER 1's research and position:
{peer1_previous_full}

PEER 2's research and position:
{peer2_previous_full}

YOUR previous research and position:
{gemini_previous_full}

Now respond. You may do additional codebase research if you want to verify claims the other models made or investigate angles they raised. Then:

1. Directly address the strongest point from each other model
2. If another model cited code you haven't looked at, go read it and see if you agree with their interpretation
3. State whether you've changed your position (and why, or why not)
4. If you agree with another model, say so explicitly

UPDATED POSITION: [same/changed] ...
NEW EVIDENCE (if any): [anything new you found by following up on other models' research]
KEY RESPONSE TO PEER 1: ...
KEY RESPONSE TO PEER 2: ...
REMAINING DISAGREEMENTS: ..." --yolo
```
