"""
ExecutionEngine — orchestrates sequential execution of approved plan steps.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from backend.db.connection import get_connection
from backend.executor.step_runner import StepRunner

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Executes approved plan steps in sequence with pause/resume support."""

    def __init__(self, task_id: int, plan_id: int) -> None:
        self.task_id = task_id
        self.plan_id = plan_id
        self._paused = False
        self._callbacks: list[Callable[[str], None]] = []
        self._invocation_count = 0

    def on_output(self, callback: Callable[[str], None]) -> None:
        """Register a callback for streaming output."""
        self._callbacks.append(callback)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def _emit(self, text: str) -> None:
        for cb in self._callbacks:
            try:
                cb(text)
            except Exception:
                pass

    async def execute(self) -> dict[str, Any]:
        """Execute all approved steps in sequence."""
        conn = get_connection()
        steps = self._load_approved_steps(conn)
        task_context = self._load_task_context(conn)

        if not steps:
            return {"status": "no_steps", "message": "No approved steps to execute"}

        self._update_plan_status(conn, "executing")
        results: list[dict] = []

        for step in steps:
            if self._paused:
                self._emit("Execution paused. Use resume to continue.")
                return {"status": "paused", "last_step_id": step["id"], "results": results}

            step_id = step["id"]
            self._update_step_status(conn, step_id, "running")
            self._emit(f"Step {step_id}: {step.get('title', '...')}")

            result = await StepRunner.run(step, task_context)
            self._invocation_count += 1
            results.append({"step_id": step_id, **result})

            if result["status"] == "completed":
                self._update_step_status(conn, step_id, "completed")
                self._log_audit(conn, step, result)
                self._emit(f"Step {step_id} completed ({result['duration_ms']}ms)")
            else:
                self._update_step_status(conn, step_id, "failed")
                self._mark_dependents_blocked(conn, step_id, steps)
                self._log_audit(conn, step, result)
                self._emit(f"Step {step_id} failed: {result.get('error', 'unknown')}")
                self._update_plan_status(conn, "failed")
                return {"status": "failed", "failed_step": step_id, "results": results}

        self._update_plan_status(conn, "completed")
        self._emit(f"Execution complete. {len(steps)} steps, {self._invocation_count} CLI invocations.")
        return {"status": "completed", "results": results, "invocations": self._invocation_count}

    def _load_approved_steps(self, conn) -> list[dict]:
        row = conn.execute(
            "SELECT yaml_content FROM plans WHERE id = ?", (self.plan_id,)
        ).fetchone()
        if not row:
            return []
        import yaml
        plan_data = yaml.safe_load(row["yaml_content"]) or {}
        steps = plan_data.get("steps", [])
        return [s for s in steps if s.get("status") in ("approved", "pending")]

    def _load_task_context(self, conn) -> dict:
        row = conn.execute(
            "SELECT * FROM inbox WHERE id = ?", (self.task_id,)
        ).fetchone()
        return dict(row) if row else {}

    def _update_step_status(self, conn, step_id: int, status: str) -> None:
        row = conn.execute(
            "SELECT yaml_content FROM plans WHERE id = ?", (self.plan_id,)
        ).fetchone()
        if not row:
            return
        import yaml
        plan_data = yaml.safe_load(row["yaml_content"]) or {}
        for step in plan_data.get("steps", []):
            if step.get("id") == step_id:
                step["status"] = status
        updated = yaml.dump(plan_data, default_flow_style=False)
        conn.execute(
            "UPDATE plans SET yaml_content = ?, updated_at = datetime('now') WHERE id = ?",
            (updated, self.plan_id),
        )
        conn.commit()

    def _update_plan_status(self, conn, status: str) -> None:
        conn.execute(
            "UPDATE plans SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, self.plan_id),
        )
        conn.commit()

    def _mark_dependents_blocked(self, conn, failed_step_id: int, all_steps: list[dict]) -> None:
        for step in all_steps:
            if step.get("id", 0) > failed_step_id and step.get("status") != "completed":
                self._update_step_status(conn, step["id"], "blocked")

    def _log_audit(self, conn, step: dict, result: dict) -> None:
        conn.execute(
            """INSERT INTO audit_log
               (step_id, action_type, target_system, target_object,
                mutation_performed, result, rollback_available)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(step.get("id", "")),
                "execute_step",
                step.get("target_system", ""),
                step.get("title", ""),
                result.get("output", "")[:500],
                json.dumps({"status": result["status"], "duration_ms": result.get("duration_ms", 0)}),
                1 if step.get("rollback") else 0,
            ),
        )
        conn.commit()
