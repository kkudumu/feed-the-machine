#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "codex-skills"

COMMON_BASELINE = """## Codex Native Baseline

These copies target Codex, not Claude. If any later section uses legacy wording, follow these Codex-native rules first:

- Ask user questions directly in chat while running in Default mode. Only use `request_user_input` if the session is actually in Plan mode.
- Prefer local tool work and `multi_tool_use.parallel` for parallelism. Use `spawn_agent` only when the user explicitly asks for sub-agents, delegation, or parallel agent work.
- Open `references/*.md` files when needed; they are not auto-loaded automatically.
- Do not rely on `TaskCreate`, `TaskList`, Claude command files, or `claude -p`.
- Treat any remaining external-model or external-CLI workflow as legacy reference unless this skill includes a Codex-native override below.
"""

SPECIAL_OVERRIDES = {
    "ftm-brainstorm": """## Codex Native Overrides

- Always read `references/agent-prompts.md` before a research sprint. Treat it as the template library for research lanes.
- Default research execution is three local lanes run in parallel: repo/codebase inspection, web/docs research, and GitHub/example hunting.
- Only use `spawn_agent` for brainstorming or research when the user explicitly asks for sub-agents or parallel agent work.
- Replace every legacy `AskUserQuestion` step with one concise blocking question in chat. In Plan mode, `request_user_input` is acceptable, but Default mode should stay in normal chat.
- After each sprint: synthesize, add 2-3 challenge observations, ask one blocking question, then stop and wait for the user.
""",
    "ftm-researcher": """## Codex Native Overrides

- Treat the seven finder roles as research lenses, not mandatory sub-agents. Cover them with local parallel tool work unless the user explicitly authorizes sub-agents.
- In quick mode, use three local lanes. In standard mode, widen the evidence sources and reconciliation depth. In deep mode, add a second refinement pass and stronger adversarial review.
- `ftm-council` is optional second-pass review, not a required external multi-CLI dependency.
- After each research pass, return a clear synthesis with sources and then wait for the user's next instruction.
""",
    "ftm-council": """## Codex Native Overrides

- This copy does not shell out to Claude or Gemini CLIs. In Codex-native mode, the council is simulated as three independent reasoning lanes: implementation, risk, and operations/product impact.
- Gather those lanes with local parallel tools by default. Only use `spawn_agent` if the user explicitly asks for sub-agents or parallel agent work.
- Treat any remaining external CLI protocol below as legacy reference. The Codex-native behavior is to collect independent evidence, compare positions, and synthesize a majority-style recommendation inside Codex.
""",
    "eng-buddy": """## Codex Native Overrides

- Do not rely on transient in-session task UIs like `TaskCreate` or `TaskList`. Persist tasks in `tasks.db`, load them with `brain.py`, and show numbered task summaries directly in the response.
- If a legacy section mentions recreating tasks in a UI task list, replace that with a concise markdown or prose task snapshot for the user.
- Codex should still use the workspace files, dashboard, hooks, and pollers described below when they exist.
""",
    "my-insights": """## Codex Native Overrides

- The aggregate/report workflow is the native path. If the bundled facet-generation helpers still depend on a legacy CLI adapter, continue with cached facets or aggregate-only reporting instead of blocking the whole skill.
- Keep the skill useful even without LLM facet generation: parse the date range, read sessions, aggregate them, render the report, and tell the user what enrichment was skipped.
""",
    "skill-creator": """## Codex Native Overrides

- Prefer manual Codex-native review loops over any legacy `claude -p` helper scripts.
- When evaluating a skill, inspect the copied skill directly, test it with realistic prompts in normal Codex conversations, and compare outputs or diffs rather than relying on Claude command-file injection.
- Treat the bundled legacy eval scripts as reference material unless they have been explicitly updated for Codex.
""",
}

REPLACEMENTS = {
    "codex-skills/ftm-brainstorm/SKILL.md": [
        ("4. ASK VIA UI       — use AskUserQuestion tool (1-4 questions, clickable options)", "4. ASK ONE QUESTION — ask one concise blocking question in chat (or `request_user_input` only in Plan mode)"),
        ("**Use `AskUserQuestion` for all questions.** This gives the user a clickable selection UI instead of making them type answers. Format every question with 2-4 labeled options, each with a short description of the trade-off. The user clicks their choice (or picks \"Other\" to type a custom answer). This is faster, less friction, and prevents answers from getting lost.", "**Use the Codex-native question flow for all questions.** In Default mode, ask a concise blocking question directly in chat with 2-4 inline options. In Plan mode, you may use `request_user_input` for the same structure."),
        ("**Batching rules:** `AskUserQuestion` supports 1-4 questions per call. Use this intelligently:", "**Batching rules:** in Codex, only batch questions when you are in Plan mode and `request_user_input` is available. In Default mode, ask one blocking question at a time."),
        ("Spawn an **Explore** agent (subagent_type: Explore):", "Run a repo scan first. Prefer local parallel reads; if and only if the user explicitly asked for sub-agents, you may spawn an `explorer` agent:"),
        ("Every turn, read `references/agent-prompts.md` and spawn **3 parallel agents** (subagent_type: general-purpose, model: from ftm-config `planning` profile). Each agent gets:", "Every turn, read `references/agent-prompts.md` and run **3 parallel research lanes**. Use `multi_tool_use.parallel` plus local tools by default; only use `spawn_agent` if the user explicitly asked for sub-agents. Each lane gets:"),
        ("## Step 4: Ask Questions via AskUserQuestion", "## Step 4: Ask One Blocking Question"),
        ("Use the `AskUserQuestion` tool for every question. Never just type a question in chat — always use the tool so the user gets the clickable selection UI.", "In Codex Default mode, ask the next blocking question directly in chat. If the session is in Plan mode, `request_user_input` is the preferred structured UI."),
        ("**Batch independent questions (up to 4 per call).** Review your queue — if the top 2-3 questions don't depend on each other's answers, send them in a single `AskUserQuestion` call. The user clicks through them quickly in the UI. If answers ARE dependent, send only the blocking question and save the rest.", "**Batch independent questions only in Plan mode.** In Default mode, send only the single blocking question and keep the rest in your internal queue."),
        ("**Example AskUserQuestion call:**", "**Example blocking question format:**"),
    ],
    "codex-skills/ftm-researcher/SKILL.md": [
        ("Silent background Explore agent scans the local codebase (same as ftm-brainstorm).", "Run a silent repo scan with local tools first. If the user explicitly asked for sub-agents, an `explorer` agent may assist."),
        ("Dispatch 7 finders in parallel, each with:", "Cover up to 7 finder lenses in parallel. Prefer local tool parallelism; only dispatch sub-agents when explicitly authorized by the user. Each research lane should have:"),
        ("- \"dig deeper on finding #N\" / \"more on #N\" → spawn 3 targeted agents on that specific finding's topic", "- \"dig deeper on finding #N\" / \"more on #N\" → run a targeted follow-up research pass on that finding; use sub-agents only if explicitly authorized"),
        ("- \"I disagree with X\" / \"I think X is wrong because Y\" → spawn counter-evidence agents, update findings", "- \"I disagree with X\" / \"I think X is wrong because Y\" → run a counter-evidence pass and update findings"),
        ("- \"focus on [angle]\" / \"what about the security angle\" → reshape subtopics with new weighting, re-dispatch", "- \"focus on [angle]\" / \"what about the security angle\" → reshape subtopics with new weighting and rerun the research lanes"),
        ("- \"more on [agent]'s findings\" → re-dispatch that agent with broader query", "- \"more on [lane]'s findings\" → rerun that research lane with a broader query"),
        ("- \"compare A vs B\" → spawn comparison agent with both findings as context", "- \"compare A vs B\" → run a comparison pass with both findings as context"),
        ("Deep mode only. Routes top claims through ftm-council (Claude + Codex + Gemini independent review).", "Deep mode only. Routes top claims through `ftm-council` for Codex-native multi-lens adversarial review."),
    ],
    "codex-skills/ftm-council/SKILL.md": [
        ("Three AI peers — Claude, Codex, and Gemini — independently research the codebase and deliberate on a problem through structured rounds of debate.", "Three independent reasoning lanes — implementation, risk, and operations/product impact — independently inspect the problem and deliberate through structured rounds of comparison."),
        ("The user needs both CLI tools installed and authenticated:", "Codex-native mode does not require external model CLIs."),
        ("- **Codex**: `npm install -g @openai/codex` (authenticated via `codex login`)\n- **Gemini**: `npm install -g @google/gemini-cli` (authenticated via Google)\n\nBefore the first round, verify both are available:\n```bash\nwhich codex && which gemini\n```\nIf either is missing, tell the user what to install and stop — don't try to run a 2-model council.", "Use local tools and Codex reasoning lanes by default. External CLIs, if they appear later in this file, are legacy reference only."),
        ("Show the user the framed prompt before proceeding: \"Here's what I'll send to the council — does this capture the problem?\" Wait for confirmation or edits.", "Show the user the framed prompt before proceeding and wait for confirmation or edits."),
        ("Launch all three in parallel:", "Run the three council lanes in parallel. Prefer local tool work; only use `spawn_agent` if the user explicitly asked for sub-agents or parallel agent work."),
    ],
    "codex-skills/eng-buddy/SKILL.md": [
        ("- For each pending/in_progress task: TaskCreate with task details (use legacy_number from metadata if available for #N prefix)", "- For each pending or in-progress task: load it from `tasks.db` and surface it in a numbered task summary in your response"),
        ("1. **Check and restore task list** (CRITICAL - tasks don't persist across conversations):", "1. **Check and restore task state** (CRITICAL - rely on `tasks.db`, not transient UI task lists):"),
        ("   - Run `TaskList` to check current state\n   - IF TaskList is empty:\n     - Run `python3 ~/.codex/skills/eng-buddy/bin/brain.py --tasks --task-json`\n     - Parse JSON output — each task has id, title, status, priority, jira_key, metadata (with legacy_number)\n     - Recreate ALL pending/in_progress tasks using TaskCreate with `#N -` prefix (use legacy_number from metadata for N, or DB id if no legacy_number)\n     - Inform user: \"Loaded X tasks from tasks.db\"\n     - FALLBACK: If brain.py fails, fall back to sync-task-lists.py + active-tasks.md\n   - IF TaskList has tasks:\n     - Continue normally (tasks already loaded)", "   - Run `python3 ~/.codex/skills/eng-buddy/bin/brain.py --tasks --task-json`\n   - Parse JSON output — each task has id, title, status, priority, jira_key, metadata (with legacy_number)\n   - Present the active tasks back to the user as a numbered summary using the `#N -` prefix\n   - Inform user: \"Loaded X tasks from tasks.db\"\n   - FALLBACK: If brain.py fails, fall back to sync-task-lists.py + active-tasks.md"),
        ("**Problem**: TaskList does NOT persist across conversations. All tasks are lost when starting a new conversation.", "**Problem**: transient in-session task UIs do not persist across conversations."),
        ("**On EVERY task change** (TaskCreate, TaskUpdate, task completion):\n1. Make the in-session task system change (TaskCreate/TaskUpdate)\n2. IMMEDIATELY update tasks.db via brain.py CLI:", "**On EVERY task change**:\n1. Update `tasks.db` immediately via `brain.py` CLI:"),
        ("**Recovery on new conversation**:\n- TaskList will be empty\n- Run `brain.py --tasks --task-json` to get all active tasks from DB\n- Recreate using TaskCreate with `#N -` prefix (use legacy_number from metadata)\n- Inform user: \"Loaded X tasks from tasks.db\"", "**Recovery on new conversation**:\n- Run `brain.py --tasks --task-json` to get all active tasks from DB\n- Present a numbered task snapshot using the `#N -` prefix\n- Inform user: \"Loaded X tasks from tasks.db\""),
        ("**When creating new tasks** (TaskCreate):", "**When creating new tasks**:"),
        ("**Example TaskCreate calls**:", "**Example task snapshot format**:"),
    ],
    "codex-skills/my-insights/SKILL.md": [
        ("This is the longest step. For each session without a cached facet, call the Claude API.", "This is the longest step. For each session without a cached facet, run the bundled facet generator if it works in your local Codex setup; otherwise skip enrichment and continue with the cached or aggregate-only path."),
        ("- The facet generator uses the Claude API (ANTHROPIC_API_KEY must be set)", "- The facet generator may still require a local LLM adapter. If it is not configured, skip facet enrichment and continue with aggregate-only reporting."),
    ],
    "codex-skills/skill-creator/SKILL.md": [
        ("Claude sees when deciding whether to use the skill", "Codex sees when deciding whether to use the skill"),
        ("Claude has a tendency to \"undertrigger\" skills", "Codex may still under-trigger skills"),
        ("This section requires the `claude` CLI tool (specifically `claude -p`) which is only available in Codex. Skip it if you're on Claude.ai.", "This section references a legacy CLI-based description optimizer. In Codex-native mode, prefer manual description iteration unless you have updated the helper scripts for Codex."),
        ("Description optimization (`run_loop.py` / `run_eval.py`) should work in Cowork just fine since it uses `claude -p` via subprocess, not a browser, but please save it until you've fully finished making the skill and the user agrees it's in good shape.", "Description optimization helper scripts are legacy reference unless you have explicitly updated them for Codex. Prefer manual review first, then optional script work if you have a Codex-compatible adapter."),
    ],
}


def insert_baseline(text: str, skill_name: str) -> str:
    if "## Codex Native Baseline" in text:
        return text
    marker = "\n\n"
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            insert_at = end + len("\n---\n")
            extra = "\n" + COMMON_BASELINE + "\n"
            if skill_name in SPECIAL_OVERRIDES:
                extra += SPECIAL_OVERRIDES[skill_name] + "\n"
            return text[:insert_at] + extra + text[insert_at:]
    return COMMON_BASELINE + "\n" + text


def main() -> None:
    for skill_md in sorted(ROOT.glob("*/SKILL.md")):
        skill_name = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8")
        text = insert_baseline(text, skill_name)
        key = str(skill_md.relative_to(ROOT.parent))
        for old, new in REPLACEMENTS.get(key, []):
            text = text.replace(old, new)
        skill_md.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
