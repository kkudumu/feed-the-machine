"""PlanStore — filesystem + SQLite index for execution plans.

Each plan is stored as a JSON file at {plans_dir}/{card_id}.json.
A lightweight SQLite index tracks metadata for quick listing.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlanStep:
    index: int
    summary: str
    detail: str
    action_type: str  # 'mcp' | 'manual' | 'browser'
    tool: str
    params: dict
    param_sources: dict
    draft_content: Optional[str]
    risk: str  # 'low' | 'medium' | 'high'
    status: str  # 'pending' | 'approved' | 'edited' | 'skipped' | 'completed' | 'failed'
    output: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        return cls(
            index=d["index"],
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
        )


@dataclass
class PlanPhase:
    name: str
    steps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, d: dict) -> "PlanPhase":
        steps = [PlanStep.from_dict(s) for s in d.get("steps", [])]
        return cls(name=d["name"], steps=steps)


@dataclass
class Plan:
    id: str
    card_id: int
    source: str
    playbook_id: str
    confidence: float
    status: str  # 'pending' | 'executing' | 'completed'
    created_at: str
    executed_at: Optional[str]
    phases: list = field(default_factory=list)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def all_steps(self) -> list:
        return [step for phase in self.phases for step in phase.steps]

    def get_step(self, index: int) -> Optional[PlanStep]:
        for step in self.all_steps():
            if step.index == index:
                return step
        return None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "card_id": self.card_id,
            "source": self.source,
            "playbook_id": self.playbook_id,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "phases": [p.to_dict() for p in self.phases],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        phases = [PlanPhase.from_dict(p) for p in d.get("phases", [])]
        return cls(
            id=d["id"],
            card_id=d["card_id"],
            source=d.get("source", ""),
            playbook_id=d.get("playbook_id", ""),
            confidence=d.get("confidence", 0.0),
            status=d.get("status", "pending"),
            created_at=d.get("created_at", ""),
            executed_at=d.get("executed_at"),
            phases=phases,
        )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class PlanStore:
    """Stores plans as JSON files; SQLite index for metadata queries."""

    def __init__(self, plans_dir: str, db_path: str) -> None:
        self.plans_dir = Path(plans_dir)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    card_id INTEGER PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get(self, card_id: int) -> Optional[Plan]:
        """Load plan from disk if the JSON file exists."""
        plan_file = self.plans_dir / f"{card_id}.json"
        if not plan_file.exists():
            return None
        try:
            data = json.loads(plan_file.read_text(encoding="utf-8"))
            return Plan.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, plan: Plan) -> None:
        """Persist plan JSON to disk and update the SQLite index."""
        plan_file = self.plans_dir / f"{plan.card_id}.json"
        plan_file.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO plans (card_id, plan_id, source, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (plan.card_id, plan.id, plan.source, plan.status, plan.created_at))
            conn.commit()
        finally:
            conn.close()

    def delete(self, card_id: int) -> None:
        """Remove plan JSON from disk and delete SQLite index row."""
        plan_file = self.plans_dir / f"{card_id}.json"
        if plan_file.exists():
            plan_file.unlink()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM plans WHERE card_id = ?", (card_id,))
            conn.commit()
        finally:
            conn.close()

    def list_all(self) -> list:
        """Return all plans from the SQLite index (metadata only)."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT card_id, plan_id, source, status, created_at FROM plans ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        return [
            {"card_id": r[0], "plan_id": r[1], "source": r[2], "status": r[3], "created_at": r[4]}
            for r in rows
        ]
