"""Plan data models — phases, steps, and execution plans for dashboard cards."""

import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

VALID_STEP_STATUSES = {"pending", "approved", "skipped", "edited", "executing", "done", "failed"}
VALID_PLAN_STATUSES = {"pending", "approved", "executing", "completed", "failed"}
VALID_RISKS = {"low", "medium", "high"}


@dataclass
class PlanStep:
    index: int
    summary: str
    detail: str
    action_type: str  # "api", "mcp", "playwright"
    tool: str  # exact MCP tool name or "__MISSING__"
    params: dict = field(default_factory=dict)
    param_sources: dict = field(default_factory=dict)
    draft_content: Optional[str] = None
    risk: str = "low"  # "low", "medium", "high"
    status: str = "pending"  # "pending", "approved", "skipped", "edited", "executing", "done", "failed"
    output: Optional[str] = None
    missing_capability: Optional[dict] = None  # set when tool == "__MISSING__"

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        return cls(
            index=d["index"],
            summary=d["summary"],
            detail=d["detail"],
            action_type=d["action_type"],
            tool=d["tool"],
            params=d.get("params", {}),
            param_sources=d.get("param_sources", {}),
            draft_content=d.get("draft_content"),
            risk=d.get("risk", "low"),
            status=d.get("status", "pending"),
            output=d.get("output"),
            missing_capability=d.get("missing_capability"),
        )

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
        }
        if self.missing_capability:
            d["missing_capability"] = self.missing_capability
        return d


@dataclass
class Phase:
    name: str
    steps: list  # list of PlanStep

    @classmethod
    def from_dict(cls, d: dict) -> "Phase":
        return cls(
            name=d["name"],
            steps=[PlanStep.from_dict(s) for s in d.get("steps", [])],
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class Plan:
    id: str
    card_id: int
    source: str  # "playbook", "llm", "hybrid"
    playbook_id: Optional[str]
    confidence: float
    phases: list  # list of Phase
    status: str  # "pending", "approved", "executing", "completed", "failed"
    created_at: str
    executed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            id=d["id"],
            card_id=d["card_id"],
            source=d["source"],
            playbook_id=d.get("playbook_id"),
            confidence=d["confidence"],
            phases=[Phase.from_dict(p) for p in d.get("phases", [])],
            status=d.get("status", "pending"),
            created_at=d["created_at"],
            executed_at=d.get("executed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "card_id": self.card_id,
            "source": self.source,
            "playbook_id": self.playbook_id,
            "confidence": self.confidence,
            "phases": [p.to_dict() for p in self.phases],
            "status": self.status,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
        }

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "Plan":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def all_steps(self) -> list:
        """Return all steps across all phases, in order."""
        steps = []
        for phase in self.phases:
            steps.extend(phase.steps)
        return steps

    def get_step(self, index: int) -> Optional["PlanStep"]:
        """Find a step by global index."""
        for step in self.all_steps():
            if step.index == index:
                return step
        return None

    def has_missing_tools(self) -> bool:
        """Check if any step has a __MISSING__ tool."""
        return any(s.tool == "__MISSING__" for s in self.all_steps())
