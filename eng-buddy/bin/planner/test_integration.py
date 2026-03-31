"""End-to-end integration test for the planning pipeline."""

import pytest
import sqlite3
import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import patch

# Ensure playbook_engine is on path (append so planner dir stays first)
_playbook_engine_dir = str(Path(__file__).parent.parent / "playbook_engine")
if _playbook_engine_dir not in sys.path:
    sys.path.append(_playbook_engine_dir)

from models import Plan
from store import PlanStore

# Load planner.py via importlib — alias "planner_integration" avoids collision with
# "planner_module" used by test_planner.py and "planner_worker_mod" used by worker.py.
_planner_spec = importlib.util.spec_from_file_location(
    "planner_integration", Path(__file__).parent / "planner.py"
)
_planner_mod = importlib.util.module_from_spec(_planner_spec)
sys.modules["planner_integration"] = _planner_mod
_planner_spec.loader.exec_module(_planner_mod)
CardPlanner = _planner_mod.CardPlanner

# Load learner.py — alias "learner_integration" avoids any collision.
_learner_spec = importlib.util.spec_from_file_location(
    "learner_integration", Path(__file__).parent / "learner.py"
)
_learner_mod = importlib.util.module_from_spec(_learner_spec)
sys.modules["learner_integration"] = _learner_mod
_learner_spec.loader.exec_module(_learner_mod)
plan_to_draft_playbook = _learner_mod.plan_to_draft_playbook

# Load PlaybookManager via importlib — reuse the already-loaded pb_engine.manager
# that planner_integration registered, so models are consistent.
PlaybookManager = _planner_mod.PlaybookManager


@pytest.fixture
def env(tmp_path):
    db_path = tmp_path / "inbox.db"
    plans_dir = tmp_path / "plans"
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "_registry.yml").write_text("""tools:
  jira:
    prefix: "mcp__mcp-atlassian__jira_"
    capabilities: [create_issue, update_issue, add_comment]
    domains: [ticket_management]
  freshservice:
    prefix: "mcp__freshservice-mcp__"
    capabilities: [get_ticket_by_id, update_ticket, send_ticket_reply]
    domains: [service_desk]
  slack:
    prefix: "mcp__slack__slack_"
    capabilities: [post_message]
    domains: [communication]
""")

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cards (id INTEGER PRIMARY KEY, source TEXT, status TEXT, "
        "summary TEXT, context_notes TEXT, timestamp TEXT, classification TEXT, section TEXT)"
    )
    conn.execute(
        "INSERT INTO cards VALUES (1, 'freshservice', 'pending', 'SSO setup for Linear', "
        "'Requester: jdoe', '2026-03-10', 'Service Request', '')"
    )
    conn.commit()
    conn.close()

    return {
        "db_path": str(db_path),
        "plans_dir": str(plans_dir),
        "playbooks_dir": str(playbooks_dir),
        "registry_dir": str(registry_dir),
    }


def test_full_pipeline_llm_plan_to_draft_playbook(env):
    """Card -> LLM plan -> approve -> execute -> draft playbook."""
    planner = CardPlanner(**env)
    card = {
        "id": 1,
        "source": "freshservice",
        "summary": "SSO setup for Linear",
        "context_notes": "Requester: jdoe",
        "classification": "Service Request",
    }

    llm_response = json.dumps({
        "confidence": 0.75,
        "phases": [
            {
                "name": "Setup",
                "steps": [
                    {
                        "index": 1,
                        "summary": "Get ticket details",
                        "detail": "Fetch Freshservice ticket",
                        "action_type": "mcp",
                        "tool": "mcp__freshservice-mcp__get_ticket_by_id",
                        "params": {"ticket_id": 1},
                        "risk": "low",
                    },
                ],
            },
            {
                "name": "Execute",
                "steps": [
                    {
                        "index": 2,
                        "summary": "Create Jira ticket",
                        "detail": "Under SSO epic",
                        "action_type": "mcp",
                        "tool": "mcp__mcp-atlassian__jira_create_issue",
                        "params": {"project": "ITWORK2", "summary": "[SSO] Linear"},
                        "draft_content": None,
                        "risk": "low",
                    },
                ],
            },
            {
                "name": "Communicate",
                "steps": [
                    {
                        "index": 3,
                        "summary": "Reply to requester",
                        "detail": "Confirm ticket creation",
                        "action_type": "mcp",
                        "tool": "mcp__freshservice-mcp__send_ticket_reply",
                        "params": {},
                        "draft_content": "Hi jdoe, I've created Jira ticket ITWORK2-XXXX for your SSO request.",
                        "risk": "medium",
                    },
                ],
            },
        ],
    })

    with patch.object(_planner_mod, "_call_claude_cli", return_value=llm_response):
        plan = planner.plan_card(card)

    assert plan is not None
    assert plan.source == "llm"
    assert len(plan.phases) == 3
    assert len(plan.all_steps()) == 3

    # Simulate approval
    for step in plan.all_steps():
        step.status = "approved"

    # Simulate editing the draft content on the communication step
    plan.all_steps()[2].draft_content = (
        "Hi jdoe, I've created Jira ticket ITWORK2-9999 for your Linear SSO request."
    )
    plan.all_steps()[2].status = "edited"

    # Simulate execution completion
    for step in plan.all_steps():
        step.status = "done"
    plan.status = "completed"
    planner.store.save(plan)

    # Verify plan was persisted with correct status
    saved = planner.store.get(1)
    assert saved is not None
    assert saved.status == "completed"

    # Learning loop: convert completed plan into a draft playbook
    pb = plan_to_draft_playbook(plan, card)
    mgr = PlaybookManager(env["playbooks_dir"])
    mgr.save_draft(pb)

    drafts = mgr.list_drafts()
    assert len(drafts) == 1
    assert drafts[0].created_from == "plan-learning"
    assert len(drafts[0].steps) == 3

    # After promotion the playbook should match similar future cards
    mgr.promote_draft(pb.id)
    matches = mgr.match_ticket(
        ticket_type="Service Request",
        text="SSO setup for Okta",
        source="freshservice",
    )
    assert len(matches) >= 1


def test_deduplication_prevents_double_planning(env):
    """Same card should not be planned twice (no second LLM call)."""
    planner = CardPlanner(**env)
    card = {
        "id": 1,
        "source": "freshservice",
        "summary": "SSO setup for Linear",
        "context_notes": "",
    }

    llm_response = json.dumps({
        "confidence": 0.7,
        "phases": [
            {
                "name": "Execute",
                "steps": [
                    {
                        "index": 1,
                        "summary": "Do thing",
                        "detail": "",
                        "action_type": "mcp",
                        "tool": "t1",
                        "params": {},
                        "risk": "low",
                    },
                ],
            }
        ],
    })

    call_count = {"n": 0}

    def counting_cli(prompt):
        call_count["n"] += 1
        return llm_response

    with patch.object(_planner_mod, "_call_claude_cli", side_effect=counting_cli):
        plan1 = planner.plan_card(card)
        plan2 = planner.plan_card(card)

    assert call_count["n"] == 1
    assert plan1 is not None
    assert plan2 is not None
    assert plan1.id == plan2.id
