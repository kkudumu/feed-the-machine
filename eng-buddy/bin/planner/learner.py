"""Learning loop — convert completed LLM plans into draft playbooks."""

import importlib.util
import re
from pathlib import Path

_here = Path(__file__).parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load both models modules by absolute path — avoids any sys.path ordering collision.
_planner_models = _load_module("planner_models", _here / "models.py")
_pb_models = _load_module(
    "playbook_engine_models",
    _here.parent / "playbook_engine" / "models.py",
)

Plan = _planner_models.Plan
Playbook = _pb_models.Playbook
PlaybookStep = _pb_models.PlaybookStep
ActionBinding = _pb_models.ActionBinding
TriggerPattern = _pb_models.TriggerPattern
ParamSource = _pb_models.ParamSource

KNOWN_KEYWORDS = [
    "sso", "saml", "scim", "oidc", "onboarding", "offboarding",
    "certificate", "renewal", "provisioning", "deprovisioning",
    "access", "permissions", "mfa", "2fa", "password", "reset",
    "account", "license", "audit", "compliance", "okta", "azure",
    "google", "slack", "jira", "freshservice",
]


def _extract_keywords(text: str) -> list:
    text_lower = text.lower()
    return [kw for kw in KNOWN_KEYWORDS if kw in text_lower]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    slug = slug.strip("-")[:50]
    return f"auto-{slug}" if slug else "auto-unnamed"


def plan_to_draft_playbook(plan, card: dict):
    """Convert a completed Plan into a draft Playbook for the learning loop.

    Args:
        plan: A completed Plan instance (planner_models.Plan).
        card: Dict with keys ``id``, ``source``, ``summary``, ``classification``.

    Returns:
        A Playbook instance with confidence="low" and created_from="plan-learning".
        Skipped and failed steps are excluded.
    """
    keywords = _extract_keywords(card.get("summary", ""))
    source_list = [card.get("source", "")] if card.get("source") else []
    trigger = TriggerPattern(
        ticket_type=card.get("classification", ""),
        keywords=keywords,
        source=source_list,
    )

    pb_steps = []
    step_id = 1
    for phase in plan.phases:
        for step in phase.steps:
            if step.status in ("skipped", "failed"):
                continue
            action = ActionBinding(
                tool=step.tool,
                params=dict(step.params),
                param_sources={
                    k: ParamSource.from_dict(v)
                    for k, v in step.param_sources.items()
                },
            )
            pb_step = PlaybookStep(
                id=step_id,
                name=step.summary,
                action=action,
                auth_required=step.action_type == "playwright",
                auth_method="stored_session" if step.action_type == "playwright" else None,
                human_required=False,
                optional=False,
            )
            pb_steps.append(pb_step)
            step_id += 1

    playbook_id = _slugify(card.get("summary", "unnamed"))

    return Playbook(
        id=playbook_id,
        name=card.get("summary", "Auto-generated playbook"),
        version=1,
        confidence="low",
        trigger_patterns=[trigger],
        created_from="plan-learning",
        executions=0,
        steps=pb_steps,
    )
