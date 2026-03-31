"""Capability expansion agent — discovers and proposes new tools for missing capabilities."""

import json
import re
from typing import Optional
from models import Plan, Phase, PlanStep


def build_expansion_prompt(plan: Plan) -> str:
    missing = []
    for step in plan.all_steps():
        if step.tool == "__MISSING__" and step.missing_capability:
            missing.append({
                "step_index": step.index,
                "summary": step.summary,
                "capability": step.missing_capability,
            })

    sections = [
        "You are eng-buddy's capability expansion agent. The planner needs tools that don't exist in our registry yet.\n",
        "## Missing Capabilities\n",
    ]
    for m in missing:
        cap = m["capability"]
        sections.append(f"- **Step {m['step_index']}**: {m['summary']} (tool: __MISSING__)")
        sections.append(f"  Description: {cap.get('description', 'Unknown')}")
        sections.append(f"  Domain: {cap.get('domain', 'Unknown')}")
        sections.append(f"  Systems: {', '.join(cap.get('systems', []))}")
        sections.append("")

    sections.append("## Instructions\n")
    sections.append("For each missing capability, research and propose ONE of these solutions:")
    sections.append("1. **mcp_server**: An existing MCP server package (npm).")
    sections.append("2. **api**: A public REST API.")
    sections.append("3. **playwright**: Browser automation.")
    sections.append("4. **custom_script**: A Python script.\n")
    sections.append("## Output Format\n")
    sections.append("Respond with ONLY valid JSON:")
    sections.append(
        '```json\n'
        '{"expansions": [{"for_step_index": 1, "solution_type": "mcp_server"|"api"|"playwright"|"custom_script", '
        '"package": "npm pkg", "config": {}, "registry_entry": {"name": "...", "prefix": "...", '
        '"capabilities": [], "domains": []}, "new_tool_name": "exact tool name", '
        '"url": "for playwright", "script_code": "for custom_script"}]}\n```'
    )

    return "\n".join(sections)


def parse_expansion_response(response: str) -> list:
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
    json_str = match.group(1) if match else response.strip()
    try:
        data = json.loads(json_str)
        return data.get("expansions", [])
    except (json.JSONDecodeError, TypeError):
        return []


def inject_tooling_phase(plan: Plan, expansions: list) -> Plan:
    """Add Phase 0: Tooling Setup and fix __MISSING__ steps.

    WARNING: Mutates plan in place (steps, phases, indices). Returns same object."""
    tooling_steps = []
    step_index = 1

    # Build map of original step index to expansion
    expansion_map = {e["for_step_index"]: e for e in expansions}

    # Fix __MISSING__ steps BEFORE re-indexing — use original indices which still match
    for phase in plan.phases:
        for step in phase.steps:
            if step.tool == "__MISSING__" and step.index in expansion_map:
                exp = expansion_map[step.index]
                step.tool = exp.get("new_tool_name", step.tool)
                step.missing_capability = None

    # Build tooling steps
    for exp in expansions:
        solution = exp["solution_type"]
        if solution == "mcp_server":
            tooling_steps.append(PlanStep(
                index=step_index,
                summary=f"Install {exp.get('package', 'MCP server')}",
                detail=f"npm install -g {exp.get('package', '')}. Add to Claude MCP config.",
                action_type="api",
                tool="local_scripts",
                params={"package": exp.get("package"), "config": exp.get("config", {})},
                risk="high",
                status="pending",
            ))
            step_index += 1
            if exp.get("registry_entry"):
                tooling_steps.append(PlanStep(
                    index=step_index,
                    summary=f"Register {exp['registry_entry'].get('name', 'tool')} in tool registry",
                    detail="Add entry to _registry.yml and create defaults file.",
                    action_type="api",
                    tool="local_scripts",
                    params={"registry_entry": exp["registry_entry"]},
                    risk="high",
                    status="pending",
                ))
                step_index += 1
        elif solution == "custom_script":
            tooling_steps.append(PlanStep(
                index=step_index,
                summary=f"Create custom script for step {exp.get('for_step_index', '?')}",
                detail=exp.get("script_code", "Script code not provided"),
                action_type="api",
                tool="local_scripts",
                params={"script_code": exp.get("script_code", "")},
                risk="high",
                status="pending",
            ))
            step_index += 1

    # Re-index existing steps after tooling steps
    for phase in plan.phases:
        for step in phase.steps:
            step.index = step_index
            step_index += 1

    # Insert tooling phase at beginning
    if tooling_steps:
        tooling_phase = Phase(name="Tooling Setup", steps=tooling_steps)
        plan.phases.insert(0, tooling_phase)

    return plan
