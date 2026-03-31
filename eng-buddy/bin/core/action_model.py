"""Canonical Action Model — the normalized representation of every card/task.

Every intake event (Slack message, email, Jira ticket, Freshservice request,
calendar event, manual entry) gets normalized into an ActionObject before
any planning or execution happens.

This is Suggestion 1 from the brain dump:
"Create a canonical action model under every card."
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkType(str, Enum):
    """What kind of work this represents."""
    INCIDENT = "incident"
    REQUEST = "request"
    MESSAGE = "message"
    APPROVAL = "approval"
    INVESTIGATION = "investigation"
    RUNBOOK = "runbook"
    MEETING = "meeting"
    AUTOMATION = "automation"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """How risky is this action."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Reversibility(str, Enum):
    """Can this action be undone."""
    FULLY_REVERSIBLE = "fully_reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


class ApprovalPolicy(str, Enum):
    """What approval is needed before execution."""
    AUTO_RUN = "auto_run"
    AUTO_IF_PLAYBOOK_MATCH = "auto_if_playbook_match"
    AUTO_IF_HIGH_CONFIDENCE = "auto_if_high_confidence"
    DRY_RUN_FIRST = "dry_run_first"
    HUMAN_APPROVAL = "human_approval"
    HUMAN_APPROVAL_IF_EXTERNAL = "human_approval_if_external"
    NEVER_AUTO = "never_auto"


@dataclass
class MissingContext:
    """Tracks what information is missing to proceed."""
    field_name: str
    description: str
    source_hint: str = ""  # where to find it: "ask user", "check Jira", etc.
    blocking: bool = False  # does this block execution?

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "description": self.description,
            "source_hint": self.source_hint,
            "blocking": self.blocking,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MissingContext":
        return cls(
            field_name=d["field_name"],
            description=d["description"],
            source_hint=d.get("source_hint", ""),
            blocking=d.get("blocking", False),
        )


@dataclass
class ActionObject:
    """The canonical normalized representation of any intake event.

    Every card in the dashboard maps to one ActionObject. This is the
    single source of truth for what the system knows about a piece of work.
    """
    # Identity
    id: int = 0
    source: str = ""  # "slack", "gmail", "jira", "freshservice", "calendar", "manual"
    source_id: str = ""  # original ID in source system
    source_url: str = ""

    # Classification
    work_type: str = WorkType.UNKNOWN.value
    classification: str = ""  # finer-grained: "sso-setup", "access-request", etc.
    urgency: str = "normal"  # "low", "normal", "high", "critical"

    # Content
    title: str = ""
    summary: str = ""
    raw_body: str = ""

    # Outcome
    required_outcome: str = ""  # "SSO configured and tested for AppName"
    success_criteria: List[str] = field(default_factory=list)

    # Systems & People
    systems_touched: List[str] = field(default_factory=list)  # ["okta", "freshservice", "jira"]
    stakeholders: List[str] = field(default_factory=list)  # ["sender@company.com", "manager"]

    # Risk Assessment
    risk_level: str = RiskLevel.LOW.value
    reversibility: str = Reversibility.UNKNOWN.value

    # Confidence & Gaps
    confidence: float = 0.0  # 0.0–1.0 how confident is the classification
    missing_context: List[MissingContext] = field(default_factory=list)

    # Execution Policy
    allowed_actions: List[str] = field(default_factory=list)  # ["read", "draft", "create_ticket"]
    approval_policy: str = ApprovalPolicy.HUMAN_APPROVAL.value

    # Metadata
    sender: str = ""
    sender_email: str = ""
    received_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)

    # Plan linkage
    plan_id: Optional[str] = None
    playbook_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "source": self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "work_type": self.work_type,
            "classification": self.classification,
            "urgency": self.urgency,
            "title": self.title,
            "summary": self.summary,
            "raw_body": self.raw_body,
            "required_outcome": self.required_outcome,
            "success_criteria": self.success_criteria,
            "systems_touched": self.systems_touched,
            "stakeholders": self.stakeholders,
            "risk_level": self.risk_level,
            "reversibility": self.reversibility,
            "confidence": self.confidence,
            "missing_context": [m.to_dict() for m in self.missing_context],
            "allowed_actions": self.allowed_actions,
            "approval_policy": self.approval_policy,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "received_at": self.received_at,
            "created_at": self.created_at,
            "tags": self.tags,
            "plan_id": self.plan_id,
            "playbook_id": self.playbook_id,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ActionObject":
        missing = [MissingContext.from_dict(m) for m in d.get("missing_context", [])]
        return cls(
            id=d.get("id", 0),
            source=d.get("source", ""),
            source_id=d.get("source_id", ""),
            source_url=d.get("source_url", ""),
            work_type=d.get("work_type", WorkType.UNKNOWN.value),
            classification=d.get("classification", ""),
            urgency=d.get("urgency", "normal"),
            title=d.get("title", ""),
            summary=d.get("summary", ""),
            raw_body=d.get("raw_body", ""),
            required_outcome=d.get("required_outcome", ""),
            success_criteria=d.get("success_criteria", []),
            systems_touched=d.get("systems_touched", []),
            stakeholders=d.get("stakeholders", []),
            risk_level=d.get("risk_level", RiskLevel.LOW.value),
            reversibility=d.get("reversibility", Reversibility.UNKNOWN.value),
            confidence=d.get("confidence", 0.0),
            missing_context=missing,
            allowed_actions=d.get("allowed_actions", []),
            approval_policy=d.get("approval_policy", ApprovalPolicy.HUMAN_APPROVAL.value),
            sender=d.get("sender", ""),
            sender_email=d.get("sender_email", ""),
            received_at=d.get("received_at", ""),
            created_at=d.get("created_at", ""),
            tags=d.get("tags", []),
            plan_id=d.get("plan_id"),
            playbook_id=d.get("playbook_id"),
        )

    @classmethod
    def from_card_row(cls, row: dict) -> "ActionObject":
        """Convert a legacy inbox.db card row into an ActionObject."""
        return cls(
            id=row.get("id", 0),
            source=row.get("source", ""),
            source_id=row.get("source_id", ""),
            source_url=row.get("source_url", ""),
            work_type=row.get("work_type", WorkType.UNKNOWN.value),
            classification=row.get("classification", ""),
            urgency=row.get("urgency", "normal"),
            title=row.get("subject", row.get("title", "")),
            summary=row.get("summary", ""),
            raw_body=row.get("body", ""),
            sender=row.get("sender", ""),
            sender_email=row.get("sender_email", row.get("from", "")),
            received_at=row.get("received_at", row.get("created_at", "")),
            tags=[t for t in (row.get("tags", "") or "").split(",") if t],
        )

    def has_blocking_gaps(self) -> bool:
        """Check if there are any blocking missing context items."""
        return any(m.blocking for m in self.missing_context)

    def is_high_risk(self) -> bool:
        return self.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)

    def can_auto_run(self) -> bool:
        """Check if this action's approval policy allows auto-execution."""
        return self.approval_policy in (
            ApprovalPolicy.AUTO_RUN.value,
            ApprovalPolicy.AUTO_IF_PLAYBOOK_MATCH.value,
            ApprovalPolicy.AUTO_IF_HIGH_CONFIDENCE.value,
        )
