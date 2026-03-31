import pytest
from models import Plan, Phase, PlanStep


def test_plan_step_from_dict():
    raw = {
        "index": 1,
        "summary": "Create Jira ticket",
        "detail": "Create ITWORK2 ticket under SSO epic",
        "action_type": "mcp",
        "tool": "mcp__mcp-atlassian__jira_create_issue",
        "params": {"project": "ITWORK2"},
        "param_sources": {},
        "draft_content": None,
        "risk": "low",
        "status": "pending",
        "output": None,
    }
    step = PlanStep.from_dict(raw)
    assert step.index == 1
    assert step.tool == "mcp__mcp-atlassian__jira_create_issue"
    assert step.risk == "low"
    assert step.status == "pending"


def test_plan_step_round_trip():
    raw = {
        "index": 2,
        "summary": "Send Slack notification",
        "detail": "Notify #it-ops channel",
        "action_type": "mcp",
        "tool": "mcp__slack__slack_post_message",
        "params": {"channel": "it-ops"},
        "param_sources": {},
        "draft_content": "SSO ticket created for {{app_name}}",
        "risk": "medium",
        "status": "pending",
        "output": None,
    }
    step = PlanStep.from_dict(raw)
    assert step.to_dict() == raw


def test_phase_from_dict():
    raw = {
        "name": "Setup",
        "steps": [
            {
                "index": 1,
                "summary": "Look up requester",
                "detail": "Find requester info",
                "action_type": "mcp",
                "tool": "mcp__freshservice-mcp__get_requester_id",
                "params": {},
                "param_sources": {},
                "draft_content": None,
                "risk": "low",
                "status": "pending",
                "output": None,
            }
        ],
    }
    phase = Phase.from_dict(raw)
    assert phase.name == "Setup"
    assert len(phase.steps) == 1
    assert phase.steps[0].summary == "Look up requester"


def test_plan_from_dict():
    raw = {
        "id": "plan-42-1710000000",
        "card_id": 42,
        "source": "playbook",
        "playbook_id": "sso-onboarding",
        "confidence": 0.85,
        "phases": [
            {
                "name": "Setup",
                "steps": [
                    {
                        "index": 1,
                        "summary": "Create Jira ticket",
                        "detail": "Create under SSO epic",
                        "action_type": "mcp",
                        "tool": "mcp__mcp-atlassian__jira_create_issue",
                        "params": {"project": "ITWORK2"},
                        "param_sources": {},
                        "draft_content": None,
                        "risk": "low",
                        "status": "pending",
                        "output": None,
                    }
                ],
            }
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    }
    plan = Plan.from_dict(raw)
    assert plan.id == "plan-42-1710000000"
    assert plan.card_id == 42
    assert plan.source == "playbook"
    assert plan.confidence == 0.85
    assert len(plan.phases) == 1
    assert plan.phases[0].steps[0].tool == "mcp__mcp-atlassian__jira_create_issue"


def test_plan_round_trip_json(tmp_path):
    raw = {
        "id": "plan-99-1710000000",
        "card_id": 99,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.7,
        "phases": [],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    }
    plan = Plan.from_dict(raw)
    path = tmp_path / "test-plan.json"
    plan.save(str(path))
    loaded = Plan.load(str(path))
    assert loaded.id == plan.id
    assert loaded.card_id == plan.card_id
    assert loaded.source == plan.source


def test_plan_all_steps():
    plan = Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
            ]},
            {"name": "Execute", "steps": [
                {"index": 2, "summary": "s2", "detail": "", "action_type": "mcp", "tool": "t2", "params": {}, "param_sources": {}, "draft_content": None, "risk": "medium", "status": "pending", "output": None},
                {"index": 3, "summary": "s3", "detail": "", "action_type": "playwright", "tool": "t3", "params": {}, "param_sources": {}, "draft_content": None, "risk": "high", "status": "pending", "output": None},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })
    all_steps = plan.all_steps()
    assert len(all_steps) == 3
    assert [s.index for s in all_steps] == [1, 2, 3]


def test_plan_get_step():
    plan = Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
                {"index": 2, "summary": "s2", "detail": "", "action_type": "mcp", "tool": "t2", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })
    step = plan.get_step(2)
    assert step is not None
    assert step.summary == "s2"
    assert plan.get_step(99) is None


def test_plan_has_missing_tools():
    plan = Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [
            {"name": "Execute", "steps": [
                {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "__MISSING__", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None, "missing_capability": {"description": "Okta admin", "domain": "identity", "systems": ["Okta"]}},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })
    assert plan.has_missing_tools() is True
