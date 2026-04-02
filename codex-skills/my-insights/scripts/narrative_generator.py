"""
narrative_generator.py

Generates narrative HTML content for all 8 report sections via a single
Claude API call. Consumes the dict returned by aggregator.aggregate() and
returns a dict that report_renderer.py can consume directly.
"""

from __future__ import annotations

import json
import re
from typing import Any


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _trim_aggregated(aggregated: dict) -> dict:
    """
    Return a lean copy of `aggregated` suitable for prompt injection.

    For large datasets we cap list distributions to top-10 entries, cap
    project_areas to 5, and drop raw per-session detail (which does not
    exist in the aggregated dict anyway — it only contains summaries).
    """
    TOP_N = 10

    def top(items: list, n: int = TOP_N) -> list:
        return items[:n] if isinstance(items, list) else items

    return {
        "total_sessions":        aggregated.get("total_sessions", 0),
        "total_messages":        aggregated.get("total_messages", 0),
        "total_lines_added":     aggregated.get("total_lines_added", 0),
        "total_lines_removed":   aggregated.get("total_lines_removed", 0),
        "total_files_modified":  aggregated.get("total_files_modified", 0),
        "active_days":           aggregated.get("active_days", 0),
        "msgs_per_day":          aggregated.get("msgs_per_day", 0.0),
        "total_commits":         aggregated.get("total_commits", 0),
        "response_time_median":  aggregated.get("response_time_median", 0.0),
        "response_time_avg":     aggregated.get("response_time_avg", 0.0),
        "multi_clauding":        aggregated.get("multi_clauding", {}),
        "project_areas":         top(aggregated.get("project_areas", []), 5),
        "goal_categories":       top(aggregated.get("goal_categories", [])),
        "top_tools":             top(aggregated.get("top_tools", [])),
        "languages":             top(aggregated.get("languages", [])),
        "session_types":         top(aggregated.get("session_types", [])),
        "friction_types":        top(aggregated.get("friction_types", [])),
        "satisfaction":          top(aggregated.get("satisfaction", [])),
        "outcomes":              top(aggregated.get("outcomes", [])),
        "primary_success":       top(aggregated.get("primary_success", [])),
        "helpfulness":           top(aggregated.get("helpfulness", [])),
        "response_times":        top(aggregated.get("response_times", [])),
        "tool_errors":           top(aggregated.get("tool_errors", [])),
        "hour_counts":           aggregated.get("hour_counts", {}),
    }


def _build_prompt(aggregated: dict) -> str:
    slim = _trim_aggregated(aggregated)
    data_json = json.dumps(slim, indent=2)

    return f"""You are writing a personalized "Codex Insights" report for a developer.

Below is their aggregated usage data from Codex sessions. Use EVERY relevant data point — cite specific numbers, tool names, project names, friction types, and session patterns. Do NOT write generic filler. Every sentence should be grounded in the actual data.

TONE: Professional but personal — like a smart colleague who reviewed your work and has real observations. Concise, specific, actionable. No fluff.

HTML RULES: Use only basic inline HTML: <strong>, <em>, <p>, <br>. Do NOT use headings, divs, classes, or block-level tags inside string values.

---

AGGREGATED DATA:
{data_json}

---

TONE EXAMPLES (match this voice):

At a Glance - Working:
"You've built a genuinely effective PR review-fix-merge pipeline using Claude and gh CLI — it's one of your most reliable workflows. The data shows {slim['total_commits']} commits across {slim['active_days']} active days, which is a strong shipping cadence."

Usage narrative paragraph:
"You are a high-velocity engineering operator who uses Codex as a persistent co-pilot across an extraordinary volume of work. At {slim['msgs_per_day']:.1f} messages per day across {slim['active_days']} active days, you're not dabbling — this is your primary development environment."

Wins:
"You've developed a highly effective code review workflow where you use Claude to review PRs, identify blocking issues, and immediately implement fixes — all in the same session."

Friction:
"Claude frequently starts down the wrong path — investigating local files when the app is deployed, misreporting git state, or losing context mid-session on longer tasks."

---

OUTPUT: Return ONLY a valid JSON object matching the exact schema below. No markdown fences, no commentary, no extra keys.

{{
  "at_a_glance": {{
    "working": "<HTML string — 1-2 sentences about what's working well, grounded in top wins/success patterns from the data>",
    "hindering": "<HTML string — 1-2 sentences about the biggest friction, grounded in friction_types and tool_errors>",
    "quick_wins": "<HTML string — 1-2 sentences about 1-2 specific quick improvements they can try this week>",
    "ambitious": "<HTML string — 1-2 sentences about 1 ambitious workflow possibility that the data hints at>"
  }},
  "usage": {{
    "paragraphs": [
      "<HTML paragraph 1 — overall developer profile and how they use Codex, cite session/message/day counts>",
      "<HTML paragraph 2 — dominant workflows visible in goal_categories, top_tools, languages>",
      "<HTML paragraph 3 — patterns in timing (hour_counts peaks), multi-clauding, response time habits>"
    ],
    "key_insight": "<One sentence — the single most interesting pattern in the data>"
  }},
  "wins": {{
    "intro": "<One sentence intro about the strongest patterns of successful usage>",
    "items": [
      {{"title": "<Win title>", "description": "<1-2 sentence description grounded in data>"}},
      {{"title": "<Win title>", "description": "<1-2 sentence description grounded in data>"}},
      {{"title": "<Win title>", "description": "<1-2 sentence description grounded in data>"}}
    ]
  }},
  "friction": {{
    "intro": "<One sentence intro about the dominant friction patterns>",
    "categories": [
      {{
        "title": "<Category title>",
        "description": "<1-2 sentence description of the friction pattern>",
        "examples": ["<Specific example from the data>", "<Another example>"]
      }},
      {{
        "title": "<Category title>",
        "description": "<1-2 sentence description>",
        "examples": ["<Example>"]
      }}
    ]
  }},
  "claude_md_suggestions": [
    {{
      "text": "<Actual text to add to CLAUDE.md — a concise directive like 'Always check git status before making file changes'>",
      "why": "<One sentence explaining why this would help, citing a specific friction pattern from the data>"
    }},
    {{
      "text": "<Another CLAUDE.md directive>",
      "why": "<Why it helps>"
    }},
    {{
      "text": "<Another CLAUDE.md directive>",
      "why": "<Why it helps>"
    }},
    {{
      "text": "<Another CLAUDE.md directive>",
      "why": "<Why it helps>"
    }},
    {{
      "text": "<Another CLAUDE.md directive>",
      "why": "<Why it helps>"
    }}
  ],
  "features": [
    {{
      "title": "<Feature title>",
      "oneliner": "<One sentence — what this feature would do>",
      "why": "<One sentence — why their data suggests they'd benefit from it>",
      "examples": [{{"code": "<A real command or prompt they can copy and use right now>"}}]
    }},
    {{
      "title": "<Feature title>",
      "oneliner": "<One sentence>",
      "why": "<One sentence>",
      "examples": [{{"code": "<Command or prompt>"}}]
    }},
    {{
      "title": "<Feature title>",
      "oneliner": "<One sentence>",
      "why": "<One sentence>",
      "examples": [{{"code": "<Command or prompt>"}}]
    }}
  ],
  "patterns": [
    {{
      "title": "<Pattern name>",
      "summary": "<One sentence — what the pattern is>",
      "detail": "<1-2 sentences — how to use it effectively, citing their usage>",
      "prompt": "<Actual prompt the user can paste into Codex to try this pattern>"
    }},
    {{
      "title": "<Pattern name>",
      "summary": "<One sentence>",
      "detail": "<1-2 sentences>",
      "prompt": "<Actual prompt>"
    }},
    {{
      "title": "<Pattern name>",
      "summary": "<One sentence>",
      "detail": "<1-2 sentences>",
      "prompt": "<Actual prompt>"
    }}
  ],
  "horizon": {{
    "intro": "<One sentence — forward-looking intro about workflow possibilities this data unlocks>",
    "items": [
      {{
        "title": "<Possibility title>",
        "possible": "<1-2 sentences — what becomes possible and why>",
        "tip": "<One sentence — concrete first step>",
        "prompt": "<Actual prompt to try this>"
      }},
      {{
        "title": "<Possibility title>",
        "possible": "<1-2 sentences>",
        "tip": "<One sentence>",
        "prompt": "<Actual prompt>"
      }},
      {{
        "title": "<Possibility title>",
        "possible": "<1-2 sentences>",
        "tip": "<One sentence>",
        "prompt": "<Actual prompt>"
      }}
    ]
  }},
  "fun_ending": {{
    "headline": "<A memorable quote or stat from the data — something that captures their Codex personality in a fun way>",
    "detail": "<One sentence of context for the quote/stat>"
  }}
}}"""


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    """
    Try to parse `raw` as JSON. If that fails, attempt to extract JSON from
    markdown code fences. Raises ValueError if nothing parseable is found.
    """
    # Direct parse
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Last resort: find first '{' ... last '}'
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not extract valid JSON from model response")


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_narratives() -> dict:
    """
    Minimal placeholder dict when the API call or JSON parsing fails.
    All string values are plain text — report_renderer will still render them.
    """
    return {
        "at_a_glance": {
            "working": "Your Codex sessions show consistent productivity across multiple projects.",
            "hindering": "Some friction patterns were detected — check the friction section for details.",
            "quick_wins": "Review your most-used tools and consider adding CLAUDE.md directives for your top workflows.",
            "ambitious": "Your multi-session patterns suggest potential for automated review pipelines.",
        },
        "usage": {
            "paragraphs": [
                "You use Codex regularly across a range of engineering tasks.",
                "Your session data shows a mix of feature development, debugging, and code review workflows.",
                "Usage is distributed across multiple projects and time windows.",
            ],
            "key_insight": "High message volume suggests deep, collaborative sessions rather than quick lookups.",
        },
        "wins": {
            "intro": "Several strong workflow patterns emerge from the session data.",
            "items": [
                {"title": "Consistent Shipping Cadence", "description": "Your commit and session data shows a reliable delivery rhythm."},
                {"title": "Broad Tool Utilization", "description": "You leverage a wide range of Codex tools effectively."},
                {"title": "Multi-Project Coverage", "description": "Sessions span multiple codebases, showing broad engineering coverage."},
            ],
        },
        "friction": {
            "intro": "A few recurring friction patterns appear across sessions.",
            "categories": [
                {
                    "title": "Context Loss in Long Sessions",
                    "description": "Extended sessions sometimes lose earlier context, requiring re-explanation.",
                    "examples": ["Re-stating project structure mid-session", "Repeating earlier decisions"],
                },
                {
                    "title": "Tool Error Recovery",
                    "description": "Some tool errors require manual correction before continuing.",
                    "examples": ["File path issues", "Git state mismatches"],
                },
            ],
        },
        "claude_md_suggestions": [
            {"text": "Always verify git status before making file changes.", "why": "Prevents git state confusion that appears in tool error data."},
            {"text": "State the target file path explicitly in every edit request.", "why": "Reduces file path errors seen in session friction data."},
            {"text": "Summarize project context at the start of each new session.", "why": "Helps maintain continuity across long-running work streams."},
            {"text": "Prefer atomic commits with descriptive messages after each logical change.", "why": "Aligns with your high commit cadence and makes history reviewable."},
            {"text": "Use /clear between unrelated tasks in the same session.", "why": "Reduces context bleed between separate workstreams."},
        ],
        "features": [
            {
                "title": "Session Continuity Prompts",
                "oneliner": "Start each session with a structured context handoff from the previous one.",
                "why": "Your multi-session work patterns would benefit from explicit state transfer.",
                "examples": [{"code": "Summarize what we accomplished last session and what's next."}],
            },
            {
                "title": "Automated PR Review Pipeline",
                "oneliner": "Chain PR review, fix, and merge into a single Codex workflow.",
                "why": "Your git commit data suggests frequent PR cycles that could be streamlined.",
                "examples": [{"code": "gh pr view --json body | claude review and fix blocking issues"}],
            },
            {
                "title": "Tool Error Auto-Recovery",
                "oneliner": "Add CLAUDE.md rules that pre-empt your most common tool errors.",
                "why": "Recurring tool errors in the data suggest preventable failure modes.",
                "examples": [{"code": "Add to CLAUDE.md: 'Check file exists before editing. Use absolute paths.'"}],
            },
        ],
        "patterns": [
            {
                "title": "Spec-First Development",
                "summary": "Write a brief spec before asking Claude to implement.",
                "detail": "Starting with a written spec reduces back-and-forth and produces better first drafts.",
                "prompt": "Here's the spec for what I want to build: [paste spec]. Implement this step by step.",
            },
            {
                "title": "Review-Then-Fix",
                "summary": "Ask Claude to review before it edits.",
                "detail": "A review pass catches issues before code changes, reducing re-work in long sessions.",
                "prompt": "Review this code for issues before making any changes. List what you find, then fix each one.",
            },
            {
                "title": "Checkpoint Summaries",
                "summary": "Ask for a summary at natural stopping points.",
                "detail": "Periodic summaries help Claude maintain accurate context in long sessions.",
                "prompt": "Summarize what we've done so far, what's working, and what's still to do.",
            },
        ],
        "horizon": {
            "intro": "Your usage patterns point toward several high-leverage workflow upgrades.",
            "items": [
                {
                    "title": "Automated Daily Standup",
                    "possible": "Your git commit and session data could auto-generate a daily standup summary.",
                    "tip": "Start by asking Claude to summarize yesterday's commits each morning.",
                    "prompt": "Summarize my git commits from yesterday into a standup-style update.",
                },
                {
                    "title": "Cross-Project Knowledge Base",
                    "possible": "Your multi-project sessions contain reusable patterns that could be captured in CLAUDE.md.",
                    "tip": "After each project, extract the top 3 learnings into project-level CLAUDE.md.",
                    "prompt": "What patterns from this project should I capture in CLAUDE.md for next time?",
                },
                {
                    "title": "Friction Reduction Sprint",
                    "possible": "A focused session on your top friction types could eliminate hours of future re-work.",
                    "tip": "Pick the top friction type from the report and spend 30 minutes addressing it in CLAUDE.md.",
                    "prompt": "Help me write CLAUDE.md rules to prevent [top friction type] from happening again.",
                },
            ],
        },
        "fun_ending": {
            "headline": "You're building a lot — keep the momentum going.",
            "detail": "The data shows consistent, high-velocity usage. That's how compounding productivity works.",
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_narratives(aggregated: dict) -> dict:
    """
    Generate narrative HTML content for all report sections.

    Uses `codex exec`.

    Args:
        aggregated: The output dict from aggregator.aggregate()

    Returns:
        dict matching the narratives schema expected by report_renderer
    """
    import subprocess

    prompt = _build_prompt(aggregated)

    def _call_cli() -> str:
        result = subprocess.run(
            ["codex", "exec", prompt],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        raise RuntimeError(result.stderr.strip() or f"exit code {result.returncode}")

    # First attempt
    try:
        raw = _call_cli()
        return _extract_json(raw)
    except Exception:
        pass

    # Single retry
    try:
        raw = _call_cli()
        return _extract_json(raw)
    except Exception:
        return _fallback_narratives()
