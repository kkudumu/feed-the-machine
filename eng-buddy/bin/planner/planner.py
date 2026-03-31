"""Core planner — orchestrates playbook matching, LLM planning, and storage."""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("planner")

_PB_ENGINE_DIR = Path(__file__).parent.parent / "playbook_engine"


def _load_pb_engine_module(stem: str, alias: str):
    """Load a playbook_engine module under a unique alias, temporarily injecting
    playbook_engine's models into sys.modules['models'] so that bare
    `from models import Playbook` within those modules resolves correctly."""
    # Load pb_models first (no external deps)
    pb_models_alias = f"{alias}._pb_models"
    if pb_models_alias not in sys.modules:
        spec = importlib.util.spec_from_file_location(pb_models_alias, _PB_ENGINE_DIR / "models.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pb_models_alias] = mod
        spec.loader.exec_module(mod)

    pb_models_mod = sys.modules[pb_models_alias]

    # Temporarily swap sys.modules["models"] so bare imports in target module work
    _saved_models = sys.modules.get("models")
    sys.modules["models"] = pb_models_mod
    try:
        spec = importlib.util.spec_from_file_location(alias, _PB_ENGINE_DIR / f"{stem}.py")
        target_mod = importlib.util.module_from_spec(spec)
        sys.modules[alias] = target_mod
        spec.loader.exec_module(target_mod)
    finally:
        if _saved_models is not None:
            sys.modules["models"] = _saved_models
        elif "models" in sys.modules and sys.modules["models"] is pb_models_mod:
            del sys.modules["models"]

    return target_mod


_pb_manager_mod = _load_pb_engine_module("manager", "pb_engine.manager")
_pb_registry_mod = _load_pb_engine_module("registry", "pb_engine.registry")

PlaybookManager = _pb_manager_mod.PlaybookManager
ToolRegistry = _pb_registry_mod.ToolRegistry

from models import Plan
from store import PlanStore
from converter import playbook_to_plan
from prompter import build_planning_prompt, parse_plan_response
from expander import build_expansion_prompt, parse_expansion_response, inject_tooling_phase


def _call_claude_cli(prompt: str) -> str:
    """Shell out to Claude CLI for LLM planning. Passes prompt via stdin."""
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", "-"],
            input=prompt,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.warning("Claude CLI returned %d: %s", result.returncode, result.stderr[:500])
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out after 120s")
        return ""
    except FileNotFoundError:
        logger.error("Claude CLI not found in PATH")
        return ""


def _get_tools_summary(registry) -> list:
    summary = []
    for name, info in registry.tools.items():
        summary.append({
            "name": name,
            "prefix": info.get("prefix", ""),
            "capabilities": info.get("capabilities", []),
            "domains": info.get("domains", []),
        })
    return summary


def _get_learned_context() -> str:
    brain_path = Path(__file__).parent.parent / "brain.py"
    if not brain_path.exists():
        return ""
    try:
        result = subprocess.run(
            [sys.executable, str(brain_path), "--build-context"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_example_plans(pb_manager) -> list:
    playbooks = pb_manager.list_playbooks()
    playbooks.sort(key=lambda p: p.executions, reverse=True)
    examples = []
    for pb in playbooks[:3]:
        plan = playbook_to_plan(pb, card_id=0)
        examples.append(plan.to_dict())
    return examples


class CardPlanner:
    def __init__(self, plans_dir: str, db_path: str, playbooks_dir: str, registry_dir: str):
        self.store = PlanStore(plans_dir, db_path)
        self.playbooks_dir = playbooks_dir
        self.registry_dir = registry_dir

    def _get_pb_manager(self):
        return PlaybookManager(self.playbooks_dir)

    def _get_registry(self):
        return ToolRegistry(self.registry_dir)

    def plan_card(self, card: dict, feedback: Optional[str] = None) -> Optional[Plan]:
        card_id = card["id"]
        if not feedback and self.store.has_plan(card_id):
            return self.store.get(card_id)

        pb_manager = self._get_pb_manager()
        matches = pb_manager.match_ticket(
            ticket_type=card.get("classification", ""),
            text=card.get("summary", ""),
            source=card.get("source", ""),
        )
        if matches:
            plan = playbook_to_plan(matches[0], card_id=card_id)
            self.store.save(plan)
            return plan

        registry = self._get_registry()
        tools_summary = _get_tools_summary(registry)
        learned_context = _get_learned_context()
        example_plans = _get_example_plans(pb_manager)

        prompt = build_planning_prompt(
            card=card, tools_summary=tools_summary,
            learned_context=learned_context, example_plans=example_plans,
            feedback=feedback,
        )
        response = _call_claude_cli(prompt)
        if not response:
            return None

        plan = parse_plan_response(response, card_id=card_id)
        if plan and plan.has_missing_tools():
            expansion_prompt = build_expansion_prompt(plan)
            expansion_response = _call_claude_cli(expansion_prompt)
            if expansion_response:
                expansions = parse_expansion_response(expansion_response)
                if expansions:
                    plan = inject_tooling_phase(plan, expansions)
        if plan:
            self.store.save(plan)
        return plan

    def regenerate(self, card_id: int, feedback: Optional[str] = None) -> Optional[Plan]:
        self.store.delete(card_id)
        card = self.store.get_card(card_id)
        if not card:
            return None
        return self.plan_card(card, feedback=feedback)
