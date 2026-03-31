import pytest
import sys
import importlib.util
from pathlib import Path

from models import Plan, Phase, PlanStep
from converter import playbook_to_plan

# Import Playbook from playbook_engine via direct file load to avoid name collision
_spec = importlib.util.spec_from_file_location(
    "pb_models", Path(__file__).parent.parent / "playbook_engine" / "models.py"
)
_pb_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pb_mod)
PBPlaybook = _pb_mod.Playbook


def _make_playbook_dict():
    return {
        "id": "sso-onboarding",
        "name": "SSO Onboarding",
        "version": 1,
        "confidence": "high",
        "trigger_patterns": [{"ticket_type": "Service Request", "keywords": ["SSO"], "source": ["freshservice"]}],
        "created_from": "session",
        "executions": 5,
        "steps": [
            {
                "id": 1,
                "name": "Create Jira ticket",
                "action": {"tool": "mcp__mcp-atlassian__jira_create_issue", "params": {"project": "ITWORK2"}},
                "auth_required": False,
                "human_required": False,
            },
            {
                "id": 2,
                "name": "Update Freshservice status",
                "action": {"tool": "mcp__freshservice-mcp__update_ticket", "params": {"status": 3}},
                "auth_required": False,
                "human_required": False,
            },
            {
                "id": 3,
                "name": "Notify requester",
                "action": {"tool": "mcp__freshservice-mcp__send_ticket_reply", "params": {}},
                "auth_required": False,
                "human_required": False,
            },
        ],
    }


def test_converts_playbook_to_plan():
    pb = PBPlaybook.from_dict(_make_playbook_dict())
    plan = playbook_to_plan(pb, card_id=42)
    assert plan.card_id == 42
    assert plan.source == "playbook"
    assert plan.playbook_id == "sso-onboarding"
    assert plan.status == "pending"


def test_groups_steps_into_phases():
    pb = PBPlaybook.from_dict(_make_playbook_dict())
    plan = playbook_to_plan(pb, card_id=42)
    assert len(plan.phases) >= 1
    total_steps = sum(len(p.steps) for p in plan.phases)
    assert total_steps == 3


def test_maps_confidence():
    pb = PBPlaybook.from_dict(_make_playbook_dict())
    plan = playbook_to_plan(pb, card_id=42)
    assert plan.confidence >= 0.8


def test_infers_action_type():
    pb = PBPlaybook.from_dict(_make_playbook_dict())
    plan = playbook_to_plan(pb, card_id=42)
    steps = plan.all_steps()
    assert all(s.action_type == "mcp" for s in steps)


def test_infers_risk():
    pb = PBPlaybook.from_dict(_make_playbook_dict())
    plan = playbook_to_plan(pb, card_id=42)
    steps = plan.all_steps()
    reply_step = [s for s in steps if "reply" in s.tool][0]
    assert reply_step.risk in ("medium", "low")
