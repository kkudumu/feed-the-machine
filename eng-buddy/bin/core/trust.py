"""Trust layer — determines what can auto-execute vs what needs approval.

Suggestion 5 from the brain dump:
"You need a trust layer, not just an approval button."

Trust tiers:
- auto_run: fully trusted, no human needed
- auto_if_playbook: auto only if plan matches a verified playbook
- auto_if_confident: auto only if confidence > threshold and no destructive actions
- dry_run_first: simulate execution, show results, then ask
- approval_required: always ask for human approval
- approval_if_external: ask only if contacting humans or changing prod state
- never_auto: read-only or investigation only
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TrustTier(str, Enum):
    """Ordered trust levels from most to least autonomous."""
    AUTO_RUN = "auto_run"
    AUTO_IF_PLAYBOOK = "auto_if_playbook"
    AUTO_IF_CONFIDENT = "auto_if_confident"
    DRY_RUN_FIRST = "dry_run_first"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_IF_EXTERNAL = "approval_if_external"
    NEVER_AUTO = "never_auto"


# Trust tier ordering (lower = more autonomous)
TRUST_TIER_ORDER = {
    TrustTier.AUTO_RUN: 0,
    TrustTier.AUTO_IF_PLAYBOOK: 1,
    TrustTier.AUTO_IF_CONFIDENT: 2,
    TrustTier.DRY_RUN_FIRST: 3,
    TrustTier.APPROVAL_REQUIRED: 4,
    TrustTier.APPROVAL_IF_EXTERNAL: 5,
    TrustTier.NEVER_AUTO: 6,
}


@dataclass
class TrustDecision:
    """The outcome of a trust evaluation."""
    can_auto_execute: bool
    tier: str
    reason: str
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)
    override_required: bool = False

    def to_dict(self) -> dict:
        return {
            "can_auto_execute": self.can_auto_execute,
            "tier": self.tier,
            "reason": self.reason,
            "conditions_met": self.conditions_met,
            "conditions_failed": self.conditions_failed,
            "override_required": self.override_required,
        }


# Destructive action indicators
DESTRUCTIVE_TOOLS = {
    "mcp__mcp-atlassian__jira_delete_issue",
    "mcp__mcp-atlassian__jira_transition_issue",
    "mcp__freshservice-mcp__delete_ticket",
    "mcp__gmail__delete_email",
    "mcp__gmail__batch_delete_emails",
    "mcp__gmail__send_email",
    "mcp__slack__slack_post_message",
    "mcp__slack__slack_reply_to_thread",
}

# Tools that contact external humans
EXTERNAL_CONTACT_TOOLS = {
    "mcp__gmail__send_email",
    "mcp__gmail__draft_email",
    "mcp__slack__slack_post_message",
    "mcp__slack__slack_reply_to_thread",
    "mcp__freshservice-mcp__send_ticket_reply",
    "mcp__freshservice-mcp__create_ticket_note",
}

# Tools that modify production state
PROD_STATE_TOOLS = {
    "mcp__mcp-atlassian__jira_create_issue",
    "mcp__mcp-atlassian__jira_update_issue",
    "mcp__mcp-atlassian__jira_transition_issue",
    "mcp__mcp-atlassian__jira_delete_issue",
    "mcp__freshservice-mcp__create_ticket",
    "mcp__freshservice-mcp__update_ticket",
    "mcp__freshservice-mcp__delete_ticket",
    "mcp__freshservice-mcp__create_service_request",
    "playwright_cli",
    "python_browser",
}

# Read-only tools (always safe)
READ_ONLY_TOOLS = {
    "mcp__mcp-atlassian__jira_get_issue",
    "mcp__mcp-atlassian__jira_search",
    "mcp__freshservice-mcp__get_ticket_by_id",
    "mcp__freshservice-mcp__get_tickets",
    "mcp__freshservice-mcp__filter_tickets",
    "mcp__gmail__search_emails",
    "mcp__gmail__read_email",
    "mcp__slack__slack_get_channel_history",
    "mcp__slack__slack_get_thread_replies",
    "mcp__context7__resolve-library-id",
    "mcp__context7__query-docs",
}


class TrustEvaluator:
    """Evaluates whether an action can auto-execute based on trust rules."""

    def __init__(
        self,
        default_tier: str = TrustTier.APPROVAL_REQUIRED.value,
        confidence_threshold: float = 0.8,
        verified_playbook_ids: Optional[List[str]] = None,
    ):
        self.default_tier = default_tier
        self.confidence_threshold = confidence_threshold
        self.verified_playbook_ids = set(verified_playbook_ids or [])

    def evaluate(
        self,
        action_object: dict,
        plan: Optional[dict] = None,
        step: Optional[dict] = None,
    ) -> TrustDecision:
        """Evaluate trust for an action, plan, or individual step.

        Args:
            action_object: The canonical ActionObject dict.
            plan: Optional plan dict (if evaluating a plan).
            step: Optional step dict (if evaluating a single step).

        Returns:
            TrustDecision with the evaluation result.
        """
        approval_policy = action_object.get("approval_policy", self.default_tier)
        conditions_met = []
        conditions_failed = []

        # Check tier-specific conditions
        if approval_policy == TrustTier.AUTO_RUN.value:
            return TrustDecision(
                can_auto_execute=True,
                tier=approval_policy,
                reason="Action is in auto-run tier",
                conditions_met=["auto_run_tier"],
            )

        if approval_policy == TrustTier.NEVER_AUTO.value:
            return TrustDecision(
                can_auto_execute=False,
                tier=approval_policy,
                reason="Action is in never-auto tier",
                conditions_failed=["never_auto_tier"],
            )

        # Check playbook match
        if approval_policy == TrustTier.AUTO_IF_PLAYBOOK.value:
            playbook_id = action_object.get("playbook_id") or (plan or {}).get("playbook_id")
            if playbook_id and playbook_id in self.verified_playbook_ids:
                conditions_met.append("verified_playbook_match")
                return TrustDecision(
                    can_auto_execute=True,
                    tier=approval_policy,
                    reason=f"Matches verified playbook: {playbook_id}",
                    conditions_met=conditions_met,
                )
            conditions_failed.append("no_verified_playbook_match")

        # Check confidence
        if approval_policy == TrustTier.AUTO_IF_CONFIDENT.value:
            confidence = action_object.get("confidence", 0.0)
            if confidence >= self.confidence_threshold:
                conditions_met.append(f"confidence={confidence:.2f} >= {self.confidence_threshold}")
            else:
                conditions_failed.append(f"confidence={confidence:.2f} < {self.confidence_threshold}")

            # Check for destructive tools
            if step:
                tool = step.get("tool", "")
                if tool in DESTRUCTIVE_TOOLS:
                    conditions_failed.append(f"destructive_tool: {tool}")
                else:
                    conditions_met.append("no_destructive_tools")
            elif plan:
                destructive = self._find_destructive_tools(plan)
                if destructive:
                    conditions_failed.append(f"destructive_tools: {', '.join(destructive)}")
                else:
                    conditions_met.append("no_destructive_tools")

            if not conditions_failed:
                return TrustDecision(
                    can_auto_execute=True,
                    tier=approval_policy,
                    reason="High confidence, no destructive actions",
                    conditions_met=conditions_met,
                )

        # Check external contact
        if approval_policy == TrustTier.APPROVAL_IF_EXTERNAL.value:
            external = False
            if step:
                if step.get("tool", "") in EXTERNAL_CONTACT_TOOLS:
                    external = True
                    conditions_failed.append(f"external_contact: {step['tool']}")
            elif plan:
                ext_tools = self._find_external_tools(plan)
                if ext_tools:
                    external = True
                    conditions_failed.append(f"external_contact: {', '.join(ext_tools)}")

            if not external:
                conditions_met.append("no_external_contact")
                return TrustDecision(
                    can_auto_execute=True,
                    tier=approval_policy,
                    reason="No external human contact in plan",
                    conditions_met=conditions_met,
                )

        # Check dry-run
        if approval_policy == TrustTier.DRY_RUN_FIRST.value:
            return TrustDecision(
                can_auto_execute=False,
                tier=approval_policy,
                reason="Dry-run required before execution",
                conditions_failed=["dry_run_not_completed"],
                override_required=False,
            )

        # Default: approval required
        return TrustDecision(
            can_auto_execute=False,
            tier=approval_policy,
            reason="Human approval required",
            conditions_met=conditions_met,
            conditions_failed=conditions_failed or ["approval_required"],
        )

    def evaluate_step(self, step: dict) -> TrustDecision:
        """Quick evaluation of a single step's trust level."""
        tool = step.get("tool", "")
        risk = step.get("risk", "low")

        # Browser tools: check sub-action before applying blanket destructive classification
        if tool == "playwright_cli":
            cmd = (step.get("command") or "").strip().lower()
            if cmd.startswith(("snapshot", "screenshot")):
                return TrustDecision(
                    can_auto_execute=True,
                    tier=TrustTier.AUTO_RUN.value,
                    reason="playwright_cli read-only action: snapshot/screenshot",
                    conditions_met=["read_only_tool"],
                )
        if tool == "python_browser":
            action = (step.get("action") or "").lower()
            if action in ("snapshot", "screenshot", "status"):
                return TrustDecision(
                    can_auto_execute=True,
                    tier=TrustTier.AUTO_RUN.value,
                    reason=f"python_browser read-only action: {action}",
                    conditions_met=["read_only_tool"],
                )

        if tool in READ_ONLY_TOOLS:
            return TrustDecision(
                can_auto_execute=True,
                tier=TrustTier.AUTO_RUN.value,
                reason=f"Read-only tool: {tool}",
                conditions_met=["read_only_tool"],
            )

        if tool in DESTRUCTIVE_TOOLS:
            return TrustDecision(
                can_auto_execute=False,
                tier=TrustTier.APPROVAL_REQUIRED.value,
                reason=f"Destructive tool requires approval: {tool}",
                conditions_failed=["destructive_tool"],
            )

        if tool in EXTERNAL_CONTACT_TOOLS:
            return TrustDecision(
                can_auto_execute=False,
                tier=TrustTier.APPROVAL_IF_EXTERNAL.value,
                reason=f"External contact requires approval: {tool}",
                conditions_failed=["external_contact"],
            )

        if risk in ("high", "critical"):
            return TrustDecision(
                can_auto_execute=False,
                tier=TrustTier.APPROVAL_REQUIRED.value,
                reason=f"High risk step (risk={risk})",
                conditions_failed=[f"high_risk_{risk}"],
            )

        return TrustDecision(
            can_auto_execute=True,
            tier=TrustTier.AUTO_IF_CONFIDENT.value,
            reason="Low-risk, non-destructive step",
            conditions_met=["low_risk", "non_destructive"],
        )

    def _find_destructive_tools(self, plan: dict) -> List[str]:
        """Find destructive tools in a plan."""
        found = []
        for phase in plan.get("phases", []):
            for step in phase.get("steps", []):
                if step.get("tool", "") in DESTRUCTIVE_TOOLS:
                    found.append(step["tool"])
        return found

    def _find_external_tools(self, plan: dict) -> List[str]:
        """Find external contact tools in a plan."""
        found = []
        for phase in plan.get("phases", []):
            for step in phase.get("steps", []):
                if step.get("tool", "") in EXTERNAL_CONTACT_TOOLS:
                    found.append(step["tool"])
        return found
