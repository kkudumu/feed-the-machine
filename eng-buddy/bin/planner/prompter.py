"""Build Claude CLI prompts for LLM planning and parse responses."""

import json
import re
import time
from typing import Optional
from models import Plan, Phase, PlanStep

PLAN_SCHEMA = """{
  "confidence": 0.0-1.0,
  "phases": [
    {
      "name": "Setup" | "Execute" | "Communicate" | "Tooling Setup",
      "steps": [
        {
          "index": 1,
          "summary": "Human-readable step name",
          "detail": "Full description of what this step does",
          "action_type": "api" | "mcp" | "playwright",
          "tool": "exact_mcp_tool_name OR __MISSING__",
          "params": {"key": "value"},
          "param_sources": {},
          "draft_content": "editable text content if step produces messages/comments" | null,
          "risk": "low" | "medium" | "high",
          "missing_capability": {"description": "...", "domain": "...", "systems": ["..."]} | null
        }
      ]
    }
  ]
}"""


def build_planning_prompt(
    card: dict,
    tools_summary: list,
    learned_context: str,
    example_plans: list,
    feedback: Optional[str] = None,
) -> str:
    sections = []

    sections.append(
        "You are eng-buddy's planning engine. Given a card from the dashboard, "
        "produce a step-by-step execution plan using the available tools.\n"
    )

    # Card context
    sections.append("## Card\n")
    sections.append(f"- **ID**: {card.get('id')}")
    sections.append(f"- **Source**: {card.get('source')}")
    sections.append(f"- **Summary**: {card.get('summary')}")
    if card.get("context_notes"):
        sections.append(f"- **Context**: {card.get('context_notes')}")
    sections.append("")

    # Available tools
    if tools_summary:
        sections.append("## Available Tools\n")
        for tool in tools_summary:
            caps = ", ".join(tool.get("capabilities", []))
            prefix = tool.get("prefix", "")
            sections.append(f"- **{tool['name']}** (prefix: `{prefix}`): {caps}")
        sections.append("")

    # Learned context
    if learned_context:
        sections.append("## Learned Context\n")
        sections.append(learned_context)
        sections.append("")

    # Example plans
    if example_plans:
        sections.append("## Example Plans\n")
        for ex in example_plans[:3]:
            sections.append(f"```json\n{json.dumps(ex, indent=2)}\n```\n")

    # Feedback from rejected plan
    if feedback:
        sections.append("## Previous Plan Feedback\n")
        sections.append(f"The previous plan was rejected because: {feedback}\n")

    # Instructions
    sections.append("## Instructions\n")
    sections.append("- Group steps into phases: \"Setup\" (data gathering, lookups), \"Execute\" (main actions, ticket creation, admin changes), \"Communicate\" (notifications, replies, status updates)")
    sections.append("- Each step MUST use an exact tool name from the Available Tools list (use the prefix + capability name)")
    sections.append("- If a step requires a tool not in the Available Tools list, set tool to \"__MISSING__\" and include a \"missing_capability\" object with description, domain, and systems fields")
    sections.append("- Mark steps with draft_content when they produce user-visible text (email bodies, Slack messages, Jira comments)")
    sections.append("- Assess risk per step: \"low\" (read/create), \"medium\" (send/update), \"high\" (delete/access changes/admin)")
    sections.append("- Self-assess confidence 0.0-1.0 based on how well you understand the card's intent")
    sections.append("")

    # Output format
    sections.append("## Output Format\n")
    sections.append("Respond with ONLY valid JSON matching this schema:\n")
    sections.append(f"```json\n{PLAN_SCHEMA}\n```")

    return "\n".join(sections)


def parse_plan_response(response: str, card_id: int) -> Optional[Plan]:
    """Parse LLM response into a Plan object. Handles raw JSON or markdown-wrapped JSON."""
    json_str = None

    # Try extracting from markdown code block first
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Try parsing the whole response as JSON
        json_str = response.strip()

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    # Ensure all steps have required defaults
    for phase in data.get("phases", []):
        for step in phase.get("steps", []):
            step.setdefault("status", "pending")
            step.setdefault("output", None)
            step.setdefault("param_sources", {})
            step.setdefault("params", {})

    return Plan(
        id=f"plan-{card_id}-{int(time.time())}",
        card_id=card_id,
        source="llm",
        playbook_id=None,
        confidence=data.get("confidence", 0.5),
        phases=[Phase.from_dict(p) for p in data.get("phases", [])],
        status="pending",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        executed_at=None,
    )
