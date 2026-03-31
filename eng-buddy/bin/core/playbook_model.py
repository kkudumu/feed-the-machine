"""First-class executable playbook model.

Suggestion 3 from the brain dump:
"Every playbook should have: trigger conditions, input schema, output schema,
steps with typed tool calls, required approvals, side effects, known failure
modes, test fixtures, example successful runs, rollback instructions,
owner/version history."

This replaces the simpler playbook_engine/models.py with a fully-typed,
executable-first playbook definition.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class TriggerCondition:
    """When should this playbook activate."""
    ticket_type: str = ""                   # "sso-setup", "access-request", etc.
    keywords: List[str] = field(default_factory=list)
    source: List[str] = field(default_factory=list)  # ["freshservice", "slack"]
    work_type: str = ""                     # matches ActionObject.work_type
    min_confidence: float = 0.5             # minimum confidence to trigger

    def to_dict(self) -> dict:
        return {
            "ticket_type": self.ticket_type,
            "keywords": self.keywords,
            "source": self.source,
            "work_type": self.work_type,
            "min_confidence": self.min_confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TriggerCondition":
        return cls(
            ticket_type=d.get("ticket_type", ""),
            keywords=d.get("keywords", []),
            source=d.get("source", []),
            work_type=d.get("work_type", ""),
            min_confidence=d.get("min_confidence", 0.5),
        )


@dataclass
class ParamSpec:
    """Schema definition for a single input/output parameter."""
    name: str
    type: str = "string"          # "string", "number", "boolean", "array", "object"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            d["default"] = self.default
        if self.enum:
            d["enum"] = self.enum
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ParamSpec":
        return cls(
            name=d["name"],
            type=d.get("type", "string"),
            description=d.get("description", ""),
            required=d.get("required", False),
            default=d.get("default"),
            enum=d.get("enum", []),
        )


@dataclass
class SideEffect:
    """A documented side effect of running this playbook."""
    system: str            # "jira", "freshservice", "okta"
    description: str
    reversible: bool = True

    def to_dict(self) -> dict:
        return {
            "system": self.system,
            "description": self.description,
            "reversible": self.reversible,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SideEffect":
        return cls(
            system=d["system"],
            description=d["description"],
            reversible=d.get("reversible", True),
        )


@dataclass
class FailureMode:
    """A known way this playbook can fail."""
    id: str
    description: str
    detection: str = ""      # how to detect this failure
    recovery: str = ""       # what to do when it happens
    frequency: str = "rare"  # "common", "occasional", "rare"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "detection": self.detection,
            "recovery": self.recovery,
            "frequency": self.frequency,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FailureMode":
        return cls(
            id=d["id"],
            description=d["description"],
            detection=d.get("detection", ""),
            recovery=d.get("recovery", ""),
            frequency=d.get("frequency", "rare"),
        )


@dataclass
class TestFixture:
    """A test case for validating the playbook."""
    name: str
    input_params: dict = field(default_factory=dict)
    expected_outcome: str = ""
    mock_responses: dict = field(default_factory=dict)  # step_index -> mock response

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "input_params": self.input_params,
            "expected_outcome": self.expected_outcome,
            "mock_responses": self.mock_responses,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TestFixture":
        return cls(
            name=d["name"],
            input_params=d.get("input_params", {}),
            expected_outcome=d.get("expected_outcome", ""),
            mock_responses=d.get("mock_responses", {}),
        )


@dataclass
class ExampleRun:
    """A recorded successful execution of this playbook."""
    run_id: str
    timestamp: str
    input_params: dict = field(default_factory=dict)
    outcome: str = ""
    duration_seconds: float = 0.0
    card_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "input_params": self.input_params,
            "outcome": self.outcome,
            "duration_seconds": self.duration_seconds,
            "card_id": self.card_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExampleRun":
        return cls(
            run_id=d["run_id"],
            timestamp=d["timestamp"],
            input_params=d.get("input_params", {}),
            outcome=d.get("outcome", ""),
            duration_seconds=d.get("duration_seconds", 0.0),
            card_id=d.get("card_id"),
        )


@dataclass
class VersionEntry:
    """One version in the playbook's history."""
    version: int
    changed_at: str
    changed_by: str = "system"
    changelog: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "changed_at": self.changed_at,
            "changed_by": self.changed_by,
            "changelog": self.changelog,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VersionEntry":
        return cls(
            version=d["version"],
            changed_at=d["changed_at"],
            changed_by=d.get("changed_by", "system"),
            changelog=d.get("changelog", ""),
        )


@dataclass
class TypedToolCall:
    """A fully-typed tool call within a playbook step."""
    tool: str                              # exact MCP tool name
    params: dict = field(default_factory=dict)
    param_sources: dict = field(default_factory=dict)  # param -> where to get it
    timeout_seconds: int = 120

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "params": self.params,
            "param_sources": self.param_sources,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TypedToolCall":
        return cls(
            tool=d["tool"],
            params=d.get("params", {}),
            param_sources=d.get("param_sources", {}),
            timeout_seconds=d.get("timeout_seconds", 120),
        )


@dataclass
class PlaybookStep:
    """A single step in a first-class playbook."""
    id: int
    name: str
    description: str = ""
    action: Optional[TypedToolCall] = None
    requires_approval: bool = False
    human_required: bool = False
    optional: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "action": self.action.to_dict() if self.action else None,
            "requires_approval": self.requires_approval,
            "human_required": self.human_required,
            "optional": self.optional,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlaybookStep":
        action_data = d.get("action")
        action = TypedToolCall.from_dict(action_data) if action_data else None
        return cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            action=action,
            requires_approval=d.get("requires_approval", False),
            human_required=d.get("human_required", False),
            optional=d.get("optional", False),
            notes=d.get("notes", ""),
        )


@dataclass
class RollbackInstructions:
    """How to undo an entire playbook execution."""
    description: str
    steps: List[str] = field(default_factory=list)
    automated_tool: str = ""  # MCP tool for automated rollback
    automated_params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "steps": self.steps,
            "automated_tool": self.automated_tool,
            "automated_params": self.automated_params,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RollbackInstructions":
        return cls(
            description=d["description"],
            steps=d.get("steps", []),
            automated_tool=d.get("automated_tool", ""),
            automated_params=d.get("automated_params", {}),
        )


@dataclass
class ExecutablePlaybook:
    """A first-class executable playbook — the full specification.

    This is the target model that playbooks should evolve toward.
    Backward-compatible with the legacy Playbook model via from_legacy().
    """
    # Identity
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    owner: str = "system"

    # Trigger
    trigger_conditions: List[TriggerCondition] = field(default_factory=list)

    # Schema
    input_schema: List[ParamSpec] = field(default_factory=list)
    output_schema: List[ParamSpec] = field(default_factory=list)

    # Steps
    steps: List[PlaybookStep] = field(default_factory=list)

    # Approvals
    required_approvals: List[str] = field(default_factory=list)  # who must approve

    # Side effects & failures
    side_effects: List[SideEffect] = field(default_factory=list)
    known_failure_modes: List[FailureMode] = field(default_factory=list)

    # Testing
    test_fixtures: List[TestFixture] = field(default_factory=list)
    example_runs: List[ExampleRun] = field(default_factory=list)

    # Rollback
    rollback: Optional[RollbackInstructions] = None

    # Versioning
    version: int = 1
    version_history: List[VersionEntry] = field(default_factory=list)
    created_from: str = "manual"  # "manual", "extracted", "observed", "plan-learning"

    # Metrics
    confidence: float = 1.0
    executions: int = 0
    last_executed: Optional[str] = None
    avg_duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "trigger_conditions": [t.to_dict() for t in self.trigger_conditions],
            "input_schema": [p.to_dict() for p in self.input_schema],
            "output_schema": [p.to_dict() for p in self.output_schema],
            "steps": [s.to_dict() for s in self.steps],
            "required_approvals": self.required_approvals,
            "side_effects": [s.to_dict() for s in self.side_effects],
            "known_failure_modes": [f.to_dict() for f in self.known_failure_modes],
            "test_fixtures": [t.to_dict() for t in self.test_fixtures],
            "example_runs": [e.to_dict() for e in self.example_runs],
            "rollback": self.rollback.to_dict() if self.rollback else None,
            "version": self.version,
            "version_history": [v.to_dict() for v in self.version_history],
            "created_from": self.created_from,
            "confidence": self.confidence,
            "executions": self.executions,
            "last_executed": self.last_executed,
            "avg_duration_seconds": self.avg_duration_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutablePlaybook":
        triggers = [TriggerCondition.from_dict(t) for t in d.get("trigger_conditions", [])]
        inputs = [ParamSpec.from_dict(p) for p in d.get("input_schema", [])]
        outputs = [ParamSpec.from_dict(p) for p in d.get("output_schema", [])]
        steps = [PlaybookStep.from_dict(s) for s in d.get("steps", [])]
        side_effects = [SideEffect.from_dict(s) for s in d.get("side_effects", [])]
        failures = [FailureMode.from_dict(f) for f in d.get("known_failure_modes", [])]
        fixtures = [TestFixture.from_dict(t) for t in d.get("test_fixtures", [])]
        examples = [ExampleRun.from_dict(e) for e in d.get("example_runs", [])]
        rollback_data = d.get("rollback")
        rollback = RollbackInstructions.from_dict(rollback_data) if rollback_data else None
        history = [VersionEntry.from_dict(v) for v in d.get("version_history", [])]

        return cls(
            id=d.get("id", uuid.uuid4().hex[:12]),
            name=d.get("name", ""),
            description=d.get("description", ""),
            owner=d.get("owner", "system"),
            trigger_conditions=triggers,
            input_schema=inputs,
            output_schema=outputs,
            steps=steps,
            required_approvals=d.get("required_approvals", []),
            side_effects=side_effects,
            known_failure_modes=failures,
            test_fixtures=fixtures,
            example_runs=examples,
            rollback=rollback,
            version=d.get("version", 1),
            version_history=history,
            created_from=d.get("created_from", "manual"),
            confidence=d.get("confidence", 1.0),
            executions=d.get("executions", 0),
            last_executed=d.get("last_executed"),
            avg_duration_seconds=d.get("avg_duration_seconds", 0.0),
        )

    @classmethod
    def from_legacy(cls, legacy: dict) -> "ExecutablePlaybook":
        """Convert a legacy Playbook dict (playbook_engine/models.py) to ExecutablePlaybook."""
        # Map trigger_keywords to TriggerCondition
        triggers = []
        if legacy.get("trigger_keywords"):
            triggers.append(TriggerCondition(
                keywords=legacy["trigger_keywords"],
            ))

        # Map input_params to input_schema
        inputs = []
        for name, spec in (legacy.get("input_params") or {}).items():
            inputs.append(ParamSpec(
                name=name,
                type=spec.get("type", "string"),
                description=spec.get("description", ""),
                required=spec.get("required", False),
                default=spec.get("default"),
            ))

        # Map legacy steps
        steps = []
        for s in legacy.get("steps", []):
            action = None
            if s.get("tool"):
                action = TypedToolCall(
                    tool=s["tool"],
                    params=s.get("tool_params", {}),
                )
            steps.append(PlaybookStep(
                id=s.get("number", 0),
                name=s.get("description", ""),
                action=action,
                human_required=s.get("requires_human", False),
                notes=s.get("notes", ""),
            ))

        # Map rollback
        rollback = None
        if legacy.get("rollback"):
            rb = legacy["rollback"]
            rollback = RollbackInstructions(
                description=rb.get("description", ""),
                steps=rb.get("steps", []),
            )

        # Map known_issues to failure_modes
        failures = []
        for i, issue in enumerate(legacy.get("known_issues", [])):
            failures.append(FailureMode(
                id=f"legacy-{i}",
                description=issue.get("issue", ""),
                detection=issue.get("description", ""),
                recovery=issue.get("fix", ""),
            ))

        return cls(
            id=legacy.get("id", uuid.uuid4().hex[:12]),
            name=legacy.get("name", ""),
            description=legacy.get("description", ""),
            trigger_conditions=triggers,
            input_schema=inputs,
            steps=steps,
            rollback=rollback,
            known_failure_modes=failures,
            version=legacy.get("version", 1),
            created_from=legacy.get("source", "manual"),
            confidence=legacy.get("confidence", 1.0),
            executions=legacy.get("executions", 0),
        )
