"""Convert Playbook objects into Plan objects for the approval flow."""

import time
import importlib.util
from pathlib import Path

from models import Plan, Phase, PlanStep

# Import Playbook from playbook_engine without shadowing planner's models
_spec = importlib.util.spec_from_file_location(
    "pb_models", Path(__file__).parent.parent / "playbook_engine" / "models.py"
)
_pb_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pb_mod)
PBPlaybook = _pb_mod.Playbook


CONFIDENCE_MAP = {"low": 0.4, "medium": 0.7, "high": 0.95}

# Tools whose primary action is sending/modifying external state
MEDIUM_RISK_PATTERNS = ["send_", "reply", "post_message", "update_", "transition_", "create_issue", "create_ticket"]
HIGH_RISK_PATTERNS = ["delete_", "remove_", "drop_", "reset_"]

# Phase classification heuristics based on tool domains
COMMUNICATE_TOOLS = ["slack", "gmail", "send_", "reply", "post_message", "draft_email", "send_email"]
SETUP_TOOLS = ["get_", "search_", "list_", "filter_", "find_", "read_"]


def _infer_action_type(tool: str) -> str:
    if "playwright" in tool:
        return "playwright"
    return "mcp"


def _infer_risk(tool: str) -> str:
    tool_lower = tool.lower()
    if any(p in tool_lower for p in HIGH_RISK_PATTERNS):
        return "high"
    if any(p in tool_lower for p in MEDIUM_RISK_PATTERNS):
        return "medium"
    return "low"


def _classify_phase(tool: str, step_name: str) -> str:
    combined = (tool + " " + step_name).lower()
    if any(p in combined for p in COMMUNICATE_TOOLS):
        return "Communicate"
    if any(p in combined for p in SETUP_TOOLS):
        return "Setup"
    return "Execute"


def playbook_to_plan(playbook, card_id: int) -> Plan:
    """Convert a matched Playbook into a Plan with phased steps."""
    phase_buckets: dict[str, list[PlanStep]] = {}
    phase_order = ["Setup", "Execute", "Communicate"]

    for i, pb_step in enumerate(playbook.steps, start=1):
        phase_name = _classify_phase(pb_step.action.tool, pb_step.name)
        plan_step = PlanStep(
            index=i,
            summary=pb_step.name,
            detail=f"Playbook step from '{playbook.name}' v{playbook.version}",
            action_type=_infer_action_type(pb_step.action.tool),
            tool=pb_step.action.tool,
            params=dict(pb_step.action.params),
            param_sources={k: v.to_dict() for k, v in pb_step.action.param_sources.items()},
            draft_content=None,
            risk=_infer_risk(pb_step.action.tool),
            status="pending",
            output=None,
        )
        if phase_name not in phase_buckets:
            phase_buckets[phase_name] = []
        phase_buckets[phase_name].append(plan_step)

    # Build phases in canonical order, re-index steps globally
    phases = []
    global_index = 1
    for phase_name in phase_order:
        if phase_name in phase_buckets:
            for step in phase_buckets[phase_name]:
                step.index = global_index
                global_index += 1
            phases.append(Phase(name=phase_name, steps=phase_buckets[phase_name]))

    return Plan(
        id=f"plan-{card_id}-{int(time.time())}",
        card_id=card_id,
        source="playbook",
        playbook_id=playbook.id,
        confidence=CONFIDENCE_MAP.get(playbook.confidence, 0.5),
        phases=phases,
        status="pending",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        executed_at=None,
    )
