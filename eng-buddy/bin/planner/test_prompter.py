import pytest
import json
from prompter import build_planning_prompt, parse_plan_response


def test_build_prompt_includes_card_context():
    card = {"id": 1, "source": "freshservice", "summary": "SSO setup for Okta", "context_notes": "Requester: jdoe"}
    tools_summary = [{"name": "jira", "capabilities": ["create_issue"]}]
    learned_context = "Always assign to kioja.kudumu"
    example_plans = []

    prompt = build_planning_prompt(card, tools_summary, learned_context, example_plans)
    assert "SSO setup for Okta" in prompt
    assert "freshservice" in prompt
    assert "Requester: jdoe" in prompt


def test_build_prompt_includes_tools():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    tools_summary = [
        {"name": "jira", "prefix": "mcp__mcp-atlassian__jira_", "capabilities": ["create_issue", "update_issue"]},
        {"name": "slack", "prefix": "mcp__slack__slack_", "capabilities": ["post_message"]},
    ]
    prompt = build_planning_prompt(card, tools_summary, "", [])
    assert "jira" in prompt
    assert "create_issue" in prompt
    assert "slack" in prompt


def test_build_prompt_includes_learned_context():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    prompt = build_planning_prompt(card, [], "Always use board 70 for Jira", [])
    assert "board 70" in prompt


def test_build_prompt_includes_examples():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    example = {"id": "plan-example", "card_id": 0, "source": "playbook", "phases": [{"name": "Setup", "steps": []}]}
    prompt = build_planning_prompt(card, [], "", [example])
    assert "plan-example" in prompt


def test_build_prompt_includes_feedback():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    prompt = build_planning_prompt(card, [], "", [], feedback="Step 3 should use Slack not email")
    assert "Step 3 should use Slack not email" in prompt


def test_build_prompt_includes_missing_tool_instruction():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    prompt = build_planning_prompt(card, [], "", [])
    assert "__MISSING__" in prompt


def test_parse_plan_response_valid():
    response = json.dumps({
        "confidence": 0.8,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "Look up user", "detail": "Find user in system", "action_type": "mcp", "tool": "mcp__freshservice-mcp__get_requester_id", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low"},
            ]},
        ],
    })
    plan = parse_plan_response(response, card_id=42)
    assert plan is not None
    assert plan.card_id == 42
    assert plan.source == "llm"
    assert len(plan.phases) == 1
    assert plan.phases[0].steps[0].status == "pending"


def test_parse_plan_response_extracts_json_from_markdown():
    response = """Here's my analysis:

```json
{
    "confidence": 0.7,
    "phases": [
        {"name": "Execute", "steps": [
            {"index": 1, "summary": "Do thing", "detail": "Details", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": null, "risk": "low"}
        ]}
    ]
}
```

That should work!"""
    plan = parse_plan_response(response, card_id=99)
    assert plan is not None
    assert plan.confidence == 0.7


def test_parse_plan_response_returns_none_on_garbage():
    plan = parse_plan_response("this is not json at all", card_id=1)
    assert plan is None
