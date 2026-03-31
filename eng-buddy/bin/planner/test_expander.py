import pytest
import json
from models import Plan, Phase, PlanStep
from expander import build_expansion_prompt, parse_expansion_response, inject_tooling_phase


def _make_plan_with_missing() -> Plan:
    return Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Access Okta admin", "detail": "Need Okta admin console",
             "action_type": "mcp", "tool": "__MISSING__", "params": {}, "param_sources": {},
             "draft_content": None, "risk": "high", "status": "pending", "output": None,
             "missing_capability": {"description": "Okta admin API", "domain": "identity", "systems": ["Okta"]}},
            {"index": 2, "summary": "Update ticket", "detail": "", "action_type": "mcp",
             "tool": "mcp__freshservice-mcp__update_ticket", "params": {}, "param_sources": {},
             "draft_content": None, "risk": "low", "status": "pending", "output": None},
        ]}],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })


def test_build_expansion_prompt():
    plan = _make_plan_with_missing()
    prompt = build_expansion_prompt(plan)
    assert "Okta" in prompt
    assert "identity" in prompt
    assert "__MISSING__" in prompt


def test_parse_expansion_mcp_install():
    response = json.dumps({
        "expansions": [{
            "for_step_index": 1,
            "solution_type": "mcp_server",
            "package": "@okta/mcp-server",
            "config": {"api_key": "env:OKTA_API_KEY"},
            "registry_entry": {
                "name": "okta",
                "prefix": "mcp__okta__",
                "capabilities": ["list_users", "get_user", "assign_app"],
                "domains": ["identity_management"],
            },
            "new_tool_name": "mcp__okta__assign_app",
        }]
    })
    expansions = parse_expansion_response(response)
    assert len(expansions) == 1
    assert expansions[0]["solution_type"] == "mcp_server"
    assert expansions[0]["package"] == "@okta/mcp-server"


def test_parse_expansion_playwright():
    response = json.dumps({
        "expansions": [{
            "for_step_index": 1,
            "solution_type": "playwright",
            "url": "https://admin.okta.com/admin/apps",
            "new_tool_name": "playwright_cli",
        }]
    })
    expansions = parse_expansion_response(response)
    assert expansions[0]["solution_type"] == "playwright"


def test_parse_expansion_returns_empty_on_garbage():
    expansions = parse_expansion_response("not json")
    assert expansions == []


def test_inject_tooling_phase():
    plan = _make_plan_with_missing()
    expansions = [{
        "for_step_index": 1,
        "solution_type": "mcp_server",
        "package": "@okta/mcp-server",
        "config": {"api_key": "env:OKTA_API_KEY"},
        "registry_entry": {"name": "okta", "prefix": "mcp__okta__"},
        "new_tool_name": "mcp__okta__assign_app",
    }]

    updated = inject_tooling_phase(plan, expansions)
    assert updated.phases[0].name == "Tooling Setup"
    for step in updated.phases[0].steps:
        assert step.risk == "high"
    execute_phase = [p for p in updated.phases if p.name == "Execute"][0]
    assert execute_phase.steps[0].tool == "mcp__okta__assign_app"
