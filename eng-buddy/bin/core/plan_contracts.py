"""Contract-driven plan step model — every step declares its contract.

Suggestion 2 from the brain dump:
"Every plan step should declare: preconditions, required permissions,
expected output, rollback strategy, observability hook, whether it can
auto-run or requires human approval, whether it is deterministic,
probabilistic, or interactive."
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Determinism(str, Enum):
    """How predictable is the step's outcome."""
    DETERMINISTIC = "deterministic"       # same input always = same output
    PROBABILISTIC = "probabilistic"       # LLM-generated, may vary
    INTERACTIVE = "interactive"           # requires human interaction mid-step


class StepRunMode(str, Enum):
    """Whether the step can auto-execute."""
    AUTO = "auto"                          # no human needed
    AUTO_IF_VERIFIED = "auto_if_verified"  # auto only if playbook-verified
    DRY_RUN = "dry_run"                    # simulate first, then confirm
    HUMAN_REQUIRED = "human_required"      # always needs approval


@dataclass
class Precondition:
    """A condition that must be true before the step can run."""
    description: str
    check_type: str = "manual"  # "manual", "api_check", "step_output", "env_var"
    check_value: str = ""       # the thing to check: step index, env var name, API call
    met: bool = False

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "check_type": self.check_type,
            "check_value": self.check_value,
            "met": self.met,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Precondition":
        return cls(
            description=d["description"],
            check_type=d.get("check_type", "manual"),
            check_value=d.get("check_value", ""),
            met=d.get("met", False),
        )


@dataclass
class RollbackStrategy:
    """How to undo this step if it fails or needs reverting."""
    description: str
    tool: str = ""             # MCP tool to call for rollback
    params: dict = field(default_factory=dict)
    manual_steps: List[str] = field(default_factory=list)
    tested: bool = False       # has this rollback been verified?

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "manual_steps": self.manual_steps,
            "tested": self.tested,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RollbackStrategy":
        return cls(
            description=d["description"],
            tool=d.get("tool", ""),
            params=d.get("params", {}),
            manual_steps=d.get("manual_steps", []),
            tested=d.get("tested", False),
        )


@dataclass
class ObservabilityHook:
    """How to monitor/verify this step ran correctly."""
    description: str
    hook_type: str = "log"     # "log", "metric", "assertion", "screenshot", "api_check"
    target: str = ""           # what to check
    expected_value: str = ""   # what we expect to see

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "hook_type": self.hook_type,
            "target": self.target,
            "expected_value": self.expected_value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ObservabilityHook":
        return cls(
            description=d["description"],
            hook_type=d.get("hook_type", "log"),
            target=d.get("target", ""),
            expected_value=d.get("expected_value", ""),
        )


@dataclass
class ContractStep:
    """A plan step with full contract declaration.

    Extends the existing PlanStep concept with contract fields.
    This can wrap or replace the existing PlanStep dataclass.
    """
    # Core identity (matches existing PlanStep)
    index: int = 0
    summary: str = ""
    detail: str = ""
    action_type: str = "mcp"   # "api", "mcp", "playwright", "manual", "llm"
    tool: str = ""
    params: dict = field(default_factory=dict)
    param_sources: dict = field(default_factory=dict)
    draft_content: Optional[str] = None
    risk: str = "low"
    status: str = "pending"
    output: Optional[str] = None

    # Contract fields (NEW)
    preconditions: List[Precondition] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)  # ["freshservice:write", "jira:create"]
    expected_output: str = ""  # description of what a successful run looks like
    expected_output_schema: Optional[dict] = None  # JSON schema of expected output
    rollback: Optional[RollbackStrategy] = None
    observability: List[ObservabilityHook] = field(default_factory=list)
    run_mode: str = StepRunMode.HUMAN_REQUIRED.value
    determinism: str = Determinism.DETERMINISTIC.value
    timeout_seconds: int = 120
    retry_count: int = 0
    max_retries: int = 1

    def to_dict(self) -> dict:
        d = {
            "index": self.index,
            "summary": self.summary,
            "detail": self.detail,
            "action_type": self.action_type,
            "tool": self.tool,
            "params": self.params,
            "param_sources": self.param_sources,
            "draft_content": self.draft_content,
            "risk": self.risk,
            "status": self.status,
            "output": self.output,
            "preconditions": [p.to_dict() for p in self.preconditions],
            "required_permissions": self.required_permissions,
            "expected_output": self.expected_output,
            "expected_output_schema": self.expected_output_schema,
            "rollback": self.rollback.to_dict() if self.rollback else None,
            "observability": [o.to_dict() for o in self.observability],
            "run_mode": self.run_mode,
            "determinism": self.determinism,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ContractStep":
        preconditions = [Precondition.from_dict(p) for p in d.get("preconditions", [])]
        rollback_data = d.get("rollback")
        rollback = RollbackStrategy.from_dict(rollback_data) if rollback_data else None
        observability = [ObservabilityHook.from_dict(o) for o in d.get("observability", [])]
        return cls(
            index=d.get("index", 0),
            summary=d.get("summary", ""),
            detail=d.get("detail", ""),
            action_type=d.get("action_type", "mcp"),
            tool=d.get("tool", ""),
            params=d.get("params", {}),
            param_sources=d.get("param_sources", {}),
            draft_content=d.get("draft_content"),
            risk=d.get("risk", "low"),
            status=d.get("status", "pending"),
            output=d.get("output"),
            preconditions=preconditions,
            required_permissions=d.get("required_permissions", []),
            expected_output=d.get("expected_output", ""),
            expected_output_schema=d.get("expected_output_schema"),
            rollback=rollback,
            observability=observability,
            run_mode=d.get("run_mode", StepRunMode.HUMAN_REQUIRED.value),
            determinism=d.get("determinism", Determinism.DETERMINISTIC.value),
            timeout_seconds=d.get("timeout_seconds", 120),
            retry_count=d.get("retry_count", 0),
            max_retries=d.get("max_retries", 1),
        )

    @classmethod
    def from_legacy_step(cls, step_dict: dict) -> "ContractStep":
        """Convert a legacy PlanStep dict into a ContractStep."""
        return cls.from_dict(step_dict)

    def preconditions_met(self) -> bool:
        """Check if all preconditions are satisfied."""
        return all(p.met for p in self.preconditions)

    def can_auto_run(self) -> bool:
        """Check if this step can auto-execute."""
        return self.run_mode in (StepRunMode.AUTO.value, StepRunMode.AUTO_IF_VERIFIED.value)

    def needs_rollback(self) -> bool:
        """Check if this step has a rollback strategy defined."""
        return self.rollback is not None
