"""Self-healing system — typed failures, recovery policies, and failure memory.

Suggestion 8 from the brain dump:
"1. Every step has typed failure classes
 2. Each class has a recovery policy
 3. The system reflects after failure
 4. Failure patterns become searchable memory"
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Typed failure classes
# ---------------------------------------------------------------------------

class FailureClass(str, Enum):
    """Typed failure categories for every step."""
    AUTH_FAILURE = "auth_failure"             # authentication/authorization failed
    TIMEOUT = "timeout"                       # step timed out
    RATE_LIMIT = "rate_limit"               # API rate limit hit
    NOT_FOUND = "not_found"                 # resource not found
    PERMISSION_DENIED = "permission_denied"  # insufficient permissions
    VALIDATION_ERROR = "validation_error"    # input validation failed
    TOOL_ERROR = "tool_error"               # MCP tool returned error
    NETWORK_ERROR = "network_error"         # network connectivity issue
    STATE_CONFLICT = "state_conflict"       # resource in unexpected state
    DEPENDENCY_MISSING = "dependency_missing"  # required prior step not done
    HUMAN_INTERVENTION = "human_intervention"  # needs human to proceed
    DATA_INTEGRITY = "data_integrity"       # data corruption or inconsistency
    UNKNOWN = "unknown"                     # unclassified failure


class RecoveryAction(str, Enum):
    """What to do when a failure occurs."""
    RETRY = "retry"                          # retry the same step
    RETRY_WITH_BACKOFF = "retry_with_backoff"  # retry with exponential backoff
    SKIP = "skip"                            # skip this step and continue
    FALLBACK = "fallback"                    # use an alternative approach
    ROLLBACK = "rollback"                    # undo completed steps
    ESCALATE = "escalate"                    # escalate to human
    PAUSE = "pause"                          # pause execution, wait for input
    ABORT = "abort"                          # stop execution entirely


# ---------------------------------------------------------------------------
# Recovery policies
# ---------------------------------------------------------------------------

@dataclass
class RecoveryPolicy:
    """A policy for recovering from a specific failure class."""
    failure_class: str
    primary_action: str = RecoveryAction.ESCALATE.value
    max_retries: int = 0
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    fallback_tool: str = ""        # alternative tool to try
    fallback_params: dict = field(default_factory=dict)
    escalation_message: str = ""
    auto_rollback: bool = False

    def to_dict(self) -> dict:
        return {
            "failure_class": self.failure_class,
            "primary_action": self.primary_action,
            "max_retries": self.max_retries,
            "backoff_seconds": self.backoff_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "fallback_tool": self.fallback_tool,
            "fallback_params": self.fallback_params,
            "escalation_message": self.escalation_message,
            "auto_rollback": self.auto_rollback,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RecoveryPolicy":
        return cls(
            failure_class=d["failure_class"],
            primary_action=d.get("primary_action", RecoveryAction.ESCALATE.value),
            max_retries=d.get("max_retries", 0),
            backoff_seconds=d.get("backoff_seconds", 1.0),
            backoff_multiplier=d.get("backoff_multiplier", 2.0),
            fallback_tool=d.get("fallback_tool", ""),
            fallback_params=d.get("fallback_params", {}),
            escalation_message=d.get("escalation_message", ""),
            auto_rollback=d.get("auto_rollback", False),
        )


# Default recovery policies
DEFAULT_RECOVERY_POLICIES: Dict[str, RecoveryPolicy] = {
    FailureClass.AUTH_FAILURE.value: RecoveryPolicy(
        failure_class=FailureClass.AUTH_FAILURE.value,
        primary_action=RecoveryAction.ESCALATE.value,
        escalation_message="Authentication failed. Check credentials or session.",
    ),
    FailureClass.TIMEOUT.value: RecoveryPolicy(
        failure_class=FailureClass.TIMEOUT.value,
        primary_action=RecoveryAction.RETRY_WITH_BACKOFF.value,
        max_retries=3,
        backoff_seconds=5.0,
        backoff_multiplier=2.0,
    ),
    FailureClass.RATE_LIMIT.value: RecoveryPolicy(
        failure_class=FailureClass.RATE_LIMIT.value,
        primary_action=RecoveryAction.RETRY_WITH_BACKOFF.value,
        max_retries=5,
        backoff_seconds=10.0,
        backoff_multiplier=2.0,
    ),
    FailureClass.NOT_FOUND.value: RecoveryPolicy(
        failure_class=FailureClass.NOT_FOUND.value,
        primary_action=RecoveryAction.ESCALATE.value,
        escalation_message="Resource not found. Verify the ID or URL.",
    ),
    FailureClass.PERMISSION_DENIED.value: RecoveryPolicy(
        failure_class=FailureClass.PERMISSION_DENIED.value,
        primary_action=RecoveryAction.ESCALATE.value,
        escalation_message="Insufficient permissions. Admin access may be needed.",
    ),
    FailureClass.VALIDATION_ERROR.value: RecoveryPolicy(
        failure_class=FailureClass.VALIDATION_ERROR.value,
        primary_action=RecoveryAction.ESCALATE.value,
        escalation_message="Input validation failed. Check parameters.",
    ),
    FailureClass.TOOL_ERROR.value: RecoveryPolicy(
        failure_class=FailureClass.TOOL_ERROR.value,
        primary_action=RecoveryAction.RETRY.value,
        max_retries=2,
    ),
    FailureClass.NETWORK_ERROR.value: RecoveryPolicy(
        failure_class=FailureClass.NETWORK_ERROR.value,
        primary_action=RecoveryAction.RETRY_WITH_BACKOFF.value,
        max_retries=3,
        backoff_seconds=5.0,
    ),
    FailureClass.STATE_CONFLICT.value: RecoveryPolicy(
        failure_class=FailureClass.STATE_CONFLICT.value,
        primary_action=RecoveryAction.PAUSE.value,
        escalation_message="Resource is in an unexpected state.",
    ),
    FailureClass.DEPENDENCY_MISSING.value: RecoveryPolicy(
        failure_class=FailureClass.DEPENDENCY_MISSING.value,
        primary_action=RecoveryAction.ABORT.value,
        escalation_message="Required prior step was not completed.",
    ),
    FailureClass.HUMAN_INTERVENTION.value: RecoveryPolicy(
        failure_class=FailureClass.HUMAN_INTERVENTION.value,
        primary_action=RecoveryAction.PAUSE.value,
        escalation_message="Human intervention required to proceed.",
    ),
    FailureClass.DATA_INTEGRITY.value: RecoveryPolicy(
        failure_class=FailureClass.DATA_INTEGRITY.value,
        primary_action=RecoveryAction.ABORT.value,
        auto_rollback=True,
        escalation_message="Data integrity issue detected. Rolling back.",
    ),
    FailureClass.UNKNOWN.value: RecoveryPolicy(
        failure_class=FailureClass.UNKNOWN.value,
        primary_action=RecoveryAction.ESCALATE.value,
        escalation_message="Unknown error occurred.",
    ),
}


# ---------------------------------------------------------------------------
# Failure record
# ---------------------------------------------------------------------------

@dataclass
class FailureRecord:
    """A recorded failure event for searchable memory."""
    id: str = ""
    step_index: int = 0
    step_summary: str = ""
    tool: str = ""
    failure_class: str = FailureClass.UNKNOWN.value
    error_message: str = ""
    error_details: dict = field(default_factory=dict)
    recovery_action_taken: str = ""
    recovery_successful: bool = False
    card_id: Optional[int] = None
    plan_id: Optional[str] = None
    playbook_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "step_index": self.step_index,
            "step_summary": self.step_summary,
            "tool": self.tool,
            "failure_class": self.failure_class,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "recovery_action_taken": self.recovery_action_taken,
            "recovery_successful": self.recovery_successful,
            "card_id": self.card_id,
            "plan_id": self.plan_id,
            "playbook_id": self.playbook_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FailureRecord":
        return cls(
            id=d.get("id", ""),
            step_index=d.get("step_index", 0),
            step_summary=d.get("step_summary", ""),
            tool=d.get("tool", ""),
            failure_class=d.get("failure_class", FailureClass.UNKNOWN.value),
            error_message=d.get("error_message", ""),
            error_details=d.get("error_details", {}),
            recovery_action_taken=d.get("recovery_action_taken", ""),
            recovery_successful=d.get("recovery_successful", False),
            card_id=d.get("card_id"),
            plan_id=d.get("plan_id"),
            playbook_id=d.get("playbook_id"),
            timestamp=d.get("timestamp", ""),
        )


# ---------------------------------------------------------------------------
# Failure classifier
# ---------------------------------------------------------------------------

class FailureClassifier:
    """Classifies errors into typed failure classes."""

    # Error message patterns -> failure class
    PATTERNS = {
        FailureClass.AUTH_FAILURE.value: [
            "401", "unauthorized", "authentication", "auth failed",
            "invalid token", "expired token", "session expired",
        ],
        FailureClass.TIMEOUT.value: [
            "timeout", "timed out", "deadline exceeded",
        ],
        FailureClass.RATE_LIMIT.value: [
            "429", "rate limit", "too many requests", "throttle",
        ],
        FailureClass.NOT_FOUND.value: [
            "404", "not found", "does not exist", "no such",
        ],
        FailureClass.PERMISSION_DENIED.value: [
            "403", "forbidden", "permission denied", "access denied",
            "insufficient permissions",
        ],
        FailureClass.VALIDATION_ERROR.value: [
            "400", "bad request", "validation", "invalid",
            "missing required", "schema",
        ],
        FailureClass.NETWORK_ERROR.value: [
            "connection refused", "dns", "network", "econnreset",
            "econnrefused", "socket", "unreachable",
        ],
        FailureClass.STATE_CONFLICT.value: [
            "409", "conflict", "already exists", "duplicate",
            "state mismatch",
        ],
    }

    @classmethod
    def classify(cls, error_message: str, error_code: Optional[int] = None) -> str:
        """Classify an error message into a failure class."""
        lower = error_message.lower()

        for failure_class, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if pattern in lower:
                    return failure_class

        return FailureClass.UNKNOWN.value


# ---------------------------------------------------------------------------
# Self-healing engine
# ---------------------------------------------------------------------------

class SelfHealingEngine:
    """Orchestrates failure detection, classification, recovery, and learning."""

    def __init__(
        self,
        recovery_policies: Optional[Dict[str, RecoveryPolicy]] = None,
        memory_store=None,
    ):
        self.policies = recovery_policies or dict(DEFAULT_RECOVERY_POLICIES)
        self.memory_store = memory_store
        self.failure_history: List[FailureRecord] = []

    def handle_failure(
        self,
        step: dict,
        error_message: str,
        error_code: Optional[int] = None,
        card_id: Optional[int] = None,
        plan_id: Optional[str] = None,
    ) -> dict:
        """Handle a step failure: classify, recover, record.

        Returns a dict with:
          - failure_class: the classified failure type
          - recovery_action: what recovery action to take
          - recovery_policy: the full policy applied
          - record: the failure record
        """
        # 1. Classify the failure
        failure_class = FailureClassifier.classify(error_message, error_code)

        # 2. Look up recovery policy
        policy = self.policies.get(failure_class, self.policies[FailureClass.UNKNOWN.value])

        # 3. Record the failure
        record = FailureRecord(
            id=f"fail-{len(self.failure_history)}",
            step_index=step.get("index", 0),
            step_summary=step.get("summary", ""),
            tool=step.get("tool", ""),
            failure_class=failure_class,
            error_message=error_message,
            recovery_action_taken=policy.primary_action,
            card_id=card_id,
            plan_id=plan_id,
        )
        self.failure_history.append(record)

        # 4. Store in memory for searchability
        if self.memory_store:
            self.memory_store.append(
                "episodic",
                f"failure-{record.id}",
                record.to_dict(),
            )

        return {
            "failure_class": failure_class,
            "recovery_action": policy.primary_action,
            "recovery_policy": policy.to_dict(),
            "record": record.to_dict(),
        }

    def get_similar_failures(self, tool: str, limit: int = 5) -> List[FailureRecord]:
        """Find similar past failures for a given tool."""
        matches = [f for f in self.failure_history if f.tool == tool]
        return matches[-limit:]

    def get_failure_stats(self) -> dict:
        """Get failure statistics by class and tool."""
        by_class: Dict[str, int] = {}
        by_tool: Dict[str, int] = {}
        for f in self.failure_history:
            by_class[f.failure_class] = by_class.get(f.failure_class, 0) + 1
            by_tool[f.tool] = by_tool.get(f.tool, 0) + 1
        return {
            "total": len(self.failure_history),
            "by_class": by_class,
            "by_tool": by_tool,
        }

    def add_recovery_policy(self, policy: RecoveryPolicy):
        """Add or override a recovery policy."""
        self.policies[policy.failure_class] = policy
