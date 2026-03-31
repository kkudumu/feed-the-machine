"""Enterprise-grade features — audit, policy, evaluation, and shadow mode.

Suggestion 9 from the brain dump:
"Execution ledger for auditability, policy and permissions as real
architecture, evaluation harnesses, simulation/shadow mode."
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Execution Ledger
# ---------------------------------------------------------------------------

@dataclass
class LedgerEntry:
    """An immutable audit record of an execution event."""
    id: int = 0
    event_type: str = ""       # "step_start", "step_complete", "step_fail", "plan_start", etc.
    card_id: Optional[int] = None
    plan_id: Optional[str] = None
    step_index: Optional[int] = None
    agent: str = ""            # which agent performed this
    tool: str = ""             # which tool was used
    input_summary: str = ""    # sanitized summary of input (no secrets)
    output_summary: str = ""   # sanitized summary of output
    status: str = ""           # "success", "failure", "skipped"
    error_message: str = ""
    duration_ms: int = 0
    mode: str = "live"         # "live", "shadow", "dry_run", "replay"
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "card_id": self.card_id,
            "plan_id": self.plan_id,
            "step_index": self.step_index,
            "agent": self.agent,
            "tool": self.tool,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "mode": self.mode,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class ExecutionLedger:
    """Append-only execution ledger for full auditability.

    Every action the system takes is recorded here. This is the
    source of truth for "what did eng-buddy do and when."
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    card_id INTEGER,
                    plan_id TEXT,
                    step_index INTEGER,
                    agent TEXT,
                    tool TEXT,
                    input_summary TEXT,
                    output_summary TEXT,
                    status TEXT,
                    error_message TEXT,
                    duration_ms INTEGER DEFAULT 0,
                    mode TEXT DEFAULT 'live',
                    metadata TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_card ON execution_ledger(card_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_plan ON execution_ledger(plan_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_mode ON execution_ledger(mode)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_time ON execution_ledger(timestamp)"
            )
            conn.commit()
        finally:
            conn.close()

    def record(self, entry: LedgerEntry) -> int:
        """Record an execution event. Returns the entry ID."""
        conn = self._conn()
        try:
            cursor = conn.execute("""
                INSERT INTO execution_ledger
                    (event_type, card_id, plan_id, step_index, agent, tool,
                     input_summary, output_summary, status, error_message,
                     duration_ms, mode, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.event_type, entry.card_id, entry.plan_id, entry.step_index,
                entry.agent, entry.tool, entry.input_summary, entry.output_summary,
                entry.status, entry.error_message, entry.duration_ms, entry.mode,
                json.dumps(entry.metadata), entry.timestamp,
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_for_card(self, card_id: int) -> List[dict]:
        """Get all ledger entries for a card."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM execution_ledger WHERE card_id = ? ORDER BY timestamp",
                (card_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_for_plan(self, plan_id: str) -> List[dict]:
        """Get all ledger entries for a plan."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM execution_ledger WHERE plan_id = ? ORDER BY timestamp",
                (plan_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_recent(self, limit: int = 50, mode: Optional[str] = None) -> List[dict]:
        """Get recent ledger entries, optionally filtered by mode."""
        conn = self._conn()
        try:
            if mode:
                rows = conn.execute(
                    "SELECT * FROM execution_ledger WHERE mode = ? ORDER BY timestamp DESC LIMIT ?",
                    (mode, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM execution_ledger ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self, since: Optional[str] = None) -> dict:
        """Get execution statistics."""
        conn = self._conn()
        try:
            where = ""
            params = []
            if since:
                where = "WHERE timestamp >= ?"
                params = [since]

            total = conn.execute(
                f"SELECT COUNT(*) FROM execution_ledger {where}", params
            ).fetchone()[0]
            successes = conn.execute(
                f"SELECT COUNT(*) FROM execution_ledger {where} {'AND' if where else 'WHERE'} status = 'success'",
                params,
            ).fetchone()[0]
            failures = conn.execute(
                f"SELECT COUNT(*) FROM execution_ledger {where} {'AND' if where else 'WHERE'} status = 'failure'",
                params,
            ).fetchone()[0]

            return {
                "total": total,
                "successes": successes,
                "failures": failures,
                "success_rate": successes / total if total > 0 else 0.0,
            }
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Shadow Mode
# ---------------------------------------------------------------------------

class ExecutionMode(str, Enum):
    LIVE = "live"           # real execution
    SHADOW = "shadow"       # simulate and log, but don't actually execute
    DRY_RUN = "dry_run"    # show what would happen
    REPLAY = "replay"       # re-run a previous execution


@dataclass
class ShadowResult:
    """The result of a shadow-mode execution."""
    step_index: int
    tool: str
    would_execute: bool
    simulated_output: str = ""
    trust_decision: Optional[dict] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "step_index": self.step_index,
            "tool": self.tool,
            "would_execute": self.would_execute,
            "simulated_output": self.simulated_output,
            "trust_decision": self.trust_decision,
            "notes": self.notes,
        }


class ShadowExecutor:
    """Shadow mode executor — simulates execution without side effects.

    Logs what would happen if the plan were executed for real.
    Useful for validating plans, training the system, and building confidence.
    """

    def __init__(self, ledger: ExecutionLedger):
        self.ledger = ledger

    def simulate_plan(self, plan: dict, action_object: dict) -> List[ShadowResult]:
        """Simulate executing a plan in shadow mode.

        Returns a list of ShadowResults showing what each step would do.
        """
        from core.trust import TrustEvaluator, READ_ONLY_TOOLS

        evaluator = TrustEvaluator()
        results = []

        for phase in plan.get("phases", []):
            for step in phase.get("steps", []):
                tool = step.get("tool", "")
                trust = evaluator.evaluate_step(step)

                result = ShadowResult(
                    step_index=step.get("index", 0),
                    tool=tool,
                    would_execute=trust.can_auto_execute,
                    trust_decision=trust.to_dict(),
                    notes=f"Tool: {tool}, Risk: {step.get('risk', 'low')}",
                )

                if tool in READ_ONLY_TOOLS:
                    result.simulated_output = "[READ-ONLY: Would fetch data]"
                else:
                    result.simulated_output = f"[SHADOW: Would call {tool}]"

                results.append(result)

                # Record in ledger as shadow mode
                self.ledger.record(LedgerEntry(
                    event_type="shadow_step",
                    card_id=action_object.get("id"),
                    plan_id=plan.get("id"),
                    step_index=step.get("index"),
                    tool=tool,
                    input_summary=str(step.get("params", {}))[:200],
                    output_summary=result.simulated_output,
                    status="simulated",
                    mode=ExecutionMode.SHADOW.value,
                ))

        return results


# ---------------------------------------------------------------------------
# Evaluation Harness
# ---------------------------------------------------------------------------

@dataclass
class EvalCase:
    """A test case for evaluating system behavior."""
    id: str
    name: str
    description: str = ""
    input_event: dict = field(default_factory=dict)
    expected_work_type: str = ""
    expected_risk: str = ""
    expected_approval_policy: str = ""
    expected_playbook_match: str = ""
    expected_step_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "input_event": self.input_event,
            "expected_work_type": self.expected_work_type,
            "expected_risk": self.expected_risk,
            "expected_approval_policy": self.expected_approval_policy,
            "expected_playbook_match": self.expected_playbook_match,
            "expected_step_count": self.expected_step_count,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvalCase":
        return cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            input_event=d.get("input_event", {}),
            expected_work_type=d.get("expected_work_type", ""),
            expected_risk=d.get("expected_risk", ""),
            expected_approval_policy=d.get("expected_approval_policy", ""),
            expected_playbook_match=d.get("expected_playbook_match", ""),
            expected_step_count=d.get("expected_step_count", 0),
            tags=d.get("tags", []),
        )


@dataclass
class EvalResult:
    """The result of running an eval case."""
    case_id: str
    passed: bool
    checks: List[dict] = field(default_factory=list)
    actual_output: dict = field(default_factory=dict)
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "checks": self.checks,
            "actual_output": self.actual_output,
            "duration_ms": self.duration_ms,
        }


class EvalHarness:
    """Evaluation harness for testing system behavior.

    Runs eval cases through the agent pipeline and compares
    actual vs expected behavior.
    """

    def __init__(self):
        self.cases: List[EvalCase] = []
        self.results: List[EvalResult] = []

    def add_case(self, case: EvalCase):
        self.cases.append(case)

    def load_cases(self, path: str):
        """Load eval cases from a JSON file."""
        data = json.loads(Path(path).read_text())
        for d in data.get("cases", []):
            self.cases.append(EvalCase.from_dict(d))

    def run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case through the intake agent.

        Returns an EvalResult with pass/fail checks.
        """
        import time
        from core.agents import IntakeAgent

        start = time.monotonic()
        agent = IntakeAgent()
        result = agent.process(
            {"raw_event": case.input_event, "source": case.input_event.get("source", "")},
            context={},
        )
        duration = int((time.monotonic() - start) * 1000)

        action = result.output.get("action_object", {})
        checks = []

        if case.expected_work_type:
            match = action.get("work_type") == case.expected_work_type
            checks.append({
                "field": "work_type",
                "expected": case.expected_work_type,
                "actual": action.get("work_type"),
                "passed": match,
            })

        if case.expected_risk:
            match = action.get("risk_level") == case.expected_risk
            checks.append({
                "field": "risk_level",
                "expected": case.expected_risk,
                "actual": action.get("risk_level"),
                "passed": match,
            })

        if case.expected_approval_policy:
            match = action.get("approval_policy") == case.expected_approval_policy
            checks.append({
                "field": "approval_policy",
                "expected": case.expected_approval_policy,
                "actual": action.get("approval_policy"),
                "passed": match,
            })

        passed = all(c["passed"] for c in checks) if checks else True

        eval_result = EvalResult(
            case_id=case.id,
            passed=passed,
            checks=checks,
            actual_output=action,
            duration_ms=duration,
        )
        self.results.append(eval_result)
        return eval_result

    def run_all(self) -> dict:
        """Run all eval cases. Returns summary."""
        for case in self.cases:
            self.run_case(case)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "results": [r.to_dict() for r in self.results],
        }

    def save_results(self, path: str):
        """Save eval results to a JSON file."""
        data = {
            "run_at": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
            },
            "results": [r.to_dict() for r in self.results],
        }
        Path(path).write_text(json.dumps(data, indent=2))
