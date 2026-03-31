import pytest
import sys
from pathlib import Path

# Insert planner dir so "from models import Plan" resolves to planner/models.py
sys.path.insert(0, str(Path(__file__).parent))

from models import Plan, Phase, PlanStep
from learner import plan_to_draft_playbook


def _make_completed_plan() -> Plan:
    return Plan.from_dict({
        "id": "plan-42-0",
        "card_id": 42,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.8,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "Look up requester", "detail": "Find in Freshservice",
                 "action_type": "mcp", "tool": "mcp__freshservice-mcp__get_requester_id",
                 "params": {"email": "jdoe@company.com"}, "param_sources": {},
                 "draft_content": None, "risk": "low", "status": "done", "output": "Found: req-123"},
            ]},
            {"name": "Execute", "steps": [
                {"index": 2, "summary": "Create Jira ticket", "detail": "Under SSO epic",
                 "action_type": "mcp", "tool": "mcp__mcp-atlassian__jira_create_issue",
                 "params": {"project": "ITWORK2", "summary": "[SSO] Okta"},
                 "param_sources": {}, "draft_content": None, "risk": "low",
                 "status": "done", "output": "Created ITWORK2-9999"},
            ]},
            {"name": "Communicate", "steps": [
                {"index": 3, "summary": "Notify requester", "detail": "Send reply",
                 "action_type": "mcp", "tool": "mcp__freshservice-mcp__send_ticket_reply",
                 "params": {}, "param_sources": {},
                 "draft_content": "Hi, I've created ticket ITWORK2-9999 for your SSO request.",
                 "risk": "medium", "status": "done", "output": "Sent"},
            ]},
        ],
        "status": "completed",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": "2026-03-10T09:05:00Z",
    })


def test_converts_plan_to_draft_playbook():
    plan = _make_completed_plan()
    card = {"id": 42, "source": "freshservice", "summary": "SSO setup for Okta", "classification": "Service Request"}
    pb = plan_to_draft_playbook(plan, card)
    assert pb.id.startswith("auto-")
    assert pb.confidence == "low"
    assert pb.created_from == "plan-learning"
    assert len(pb.steps) == 3


def test_preserves_tool_bindings():
    plan = _make_completed_plan()
    card = {"id": 42, "source": "freshservice", "summary": "SSO setup for Okta", "classification": "Service Request"}
    pb = plan_to_draft_playbook(plan, card)
    assert pb.steps[0].action.tool == "mcp__freshservice-mcp__get_requester_id"
    assert pb.steps[1].action.tool == "mcp__mcp-atlassian__jira_create_issue"
    assert pb.steps[1].action.params.get("project") == "ITWORK2"


def test_extracts_trigger_patterns():
    plan = _make_completed_plan()
    card = {"id": 42, "source": "freshservice", "summary": "SSO setup for Okta", "classification": "Service Request"}
    pb = plan_to_draft_playbook(plan, card)
    assert len(pb.trigger_patterns) >= 1
    tp = pb.trigger_patterns[0]
    assert "freshservice" in tp.source
    assert any("sso" in kw.lower() for kw in tp.keywords)


def test_skips_skipped_steps():
    plan = _make_completed_plan()
    plan.phases[0].steps[0].status = "skipped"
    card = {"id": 42, "source": "freshservice", "summary": "SSO for Okta", "classification": ""}
    pb = plan_to_draft_playbook(plan, card)
    assert len(pb.steps) == 2
