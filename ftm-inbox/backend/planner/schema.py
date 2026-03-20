"""
Pydantic models for structured execution plans.

A Plan contains an ordered list of PlanSteps. Each step tracks its approval
state independently so the operator can approve individual steps before
the executor runs them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class PlanStep(BaseModel):
    id: int
    title: str
    target_system: str = ""
    method_primary: str = ""
    method_fallback: str = ""
    risk_level: str = "low"       # low | medium | high
    approval_required: bool = False
    rollback: str = ""
    status: str = "pending"       # pending | approved | rejected | running | completed | failed


class Plan(BaseModel):
    id: int | None = None
    task_id: int
    steps: list[PlanStep] = Field(default_factory=list)
    status: str = "draft"         # draft | approved | executing | completed | failed
    yaml_content: str = ""
    created_at: str | None = None
    updated_at: str | None = None
