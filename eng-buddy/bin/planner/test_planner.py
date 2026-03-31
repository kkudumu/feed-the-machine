import pytest
import sys
import json
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure playbook_engine is on path (append so planner dir stays first)
_playbook_engine_dir = str(Path(__file__).parent.parent / "playbook_engine")
if _playbook_engine_dir not in sys.path:
    sys.path.append(_playbook_engine_dir)

from models import Plan
from store import PlanStore

# Load planner.py via importlib to avoid collision with the 'planner' package dir,
# then register it in sys.modules so patch() can find it by name.
_planner_spec = importlib.util.spec_from_file_location(
    "planner_module", Path(__file__).parent / "planner.py"
)
_planner_mod = importlib.util.module_from_spec(_planner_spec)
sys.modules["planner_module"] = _planner_mod
_planner_spec.loader.exec_module(_planner_mod)
CardPlanner = _planner_mod.CardPlanner

# Load playbook_engine models via importlib to get Playbook without shadowing Plan
_pb_models_spec = importlib.util.spec_from_file_location(
    "pb_models", Path(__file__).parent.parent / "playbook_engine" / "models.py"
)
_pb_models_mod = importlib.util.module_from_spec(_pb_models_spec)
_pb_models_spec.loader.exec_module(_pb_models_mod)
PBPlaybook = _pb_models_mod.Playbook


@pytest.fixture
def planner(tmp_path):
    plans_dir = tmp_path / "plans"
    db_path = tmp_path / "inbox.db"
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "_registry.yml").write_text("tools: {}")
    return CardPlanner(
        plans_dir=str(plans_dir),
        db_path=str(db_path),
        playbooks_dir=str(playbooks_dir),
        registry_dir=str(registry_dir),
    )


def test_plan_card_with_no_playbook_match(planner):
    card = {"id": 1, "source": "freshservice", "summary": "New SSO request", "context_notes": ""}
    mock_response = json.dumps({
        "confidence": 0.7,
        "phases": [{"name": "Setup", "steps": [
            {"index": 1, "summary": "Look up ticket", "detail": "Get ticket details", "action_type": "mcp",
             "tool": "mcp__freshservice-mcp__get_ticket_by_id", "params": {}, "risk": "low"},
        ]}],
    })
    with patch("planner_module._call_claude_cli", return_value=mock_response):
        plan = planner.plan_card(card)
    assert plan is not None
    assert plan.source == "llm"
    assert plan.card_id == 1
    assert len(plan.all_steps()) == 1
    assert planner.store.has_plan(1)


def test_plan_card_with_playbook_match(planner):
    pb = PBPlaybook.from_dict({
        "id": "test-pb", "name": "Test", "version": 1, "confidence": "high",
        "trigger_patterns": [{"keywords": ["SSO"], "source": ["freshservice"]}],
        "created_from": "session", "executions": 5,
        "steps": [{"id": 1, "name": "Do thing", "action": {"tool": "mcp__jira__create_issue", "params": {}},
                   "auth_required": False, "human_required": False}],
    })
    # Use PlaybookManager from planner_module (loaded safely via importlib)
    PlaybookManager = _planner_mod.PlaybookManager
    mgr = PlaybookManager(planner.playbooks_dir)
    mgr.save(pb)

    planner2 = CardPlanner(
        plans_dir=planner.store.plans_dir,
        db_path=str(planner.store.db_path),
        playbooks_dir=planner.playbooks_dir,
        registry_dir=planner.registry_dir,
    )
    card = {"id": 2, "source": "freshservice", "summary": "SSO setup for Linear", "context_notes": ""}
    plan = planner2.plan_card(card)
    assert plan is not None
    assert plan.source == "playbook"
    assert plan.playbook_id == "test-pb"


def test_plan_card_deduplication(planner):
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    mock_response = json.dumps({
        "confidence": 0.7,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "risk": "low"},
        ]}],
    })
    with patch("planner_module._call_claude_cli", return_value=mock_response):
        plan1 = planner.plan_card(card)
        plan2 = planner.plan_card(card)
    assert plan2.id == plan1.id


def test_plan_card_detects_missing_tools(planner):
    card = {"id": 3, "source": "freshservice", "summary": "Okta admin task", "context_notes": ""}
    mock_response = json.dumps({
        "confidence": 0.5,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Access Okta", "detail": "Need Okta admin", "action_type": "mcp",
             "tool": "__MISSING__", "params": {}, "risk": "high",
             "missing_capability": {"description": "Okta admin API", "domain": "identity", "systems": ["Okta"]}},
        ]}],
    })
    with patch("planner_module._call_claude_cli", return_value=mock_response):
        plan = planner.plan_card(card)
    assert plan is not None
    assert plan.has_missing_tools()


def test_plan_card_triggers_expansion_for_missing_tools(planner):
    card = {"id": 5, "source": "freshservice", "summary": "Okta SSO setup", "context_notes": ""}

    missing_response = json.dumps({
        "confidence": 0.5,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Access Okta", "detail": "", "action_type": "mcp",
             "tool": "__MISSING__", "params": {}, "risk": "high",
             "missing_capability": {"description": "Okta admin", "domain": "identity", "systems": ["Okta"]}},
        ]}],
    })

    expansion_response = json.dumps({
        "expansions": [{
            "for_step_index": 1,
            "solution_type": "playwright",
            "url": "https://admin.okta.com",
            "new_tool_name": "playwright_cli",
        }]
    })

    call_count = {"n": 0}
    def mock_cli(prompt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return missing_response
        return expansion_response

    with patch("planner_module._call_claude_cli", side_effect=mock_cli):
        plan = planner.plan_card(card)

    assert plan is not None
    has_tooling = any(p.name == "Tooling Setup" for p in plan.phases)
    has_missing = plan.has_missing_tools()
    assert has_tooling or not has_missing
