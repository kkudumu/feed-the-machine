"""
Plan API routes.

Endpoints:
  POST /api/tasks/{task_id}/generate-plan  — generate a plan via Claude CLI
  GET  /api/tasks/{task_id}/plan           — fetch the current plan
  POST /api/tasks/{task_id}/plan/steps/{step_id}/approve  — approve one step
  POST /api/tasks/{task_id}/plan/approve-all              — approve all low-risk steps
  GET  /api/tasks/{task_id}/plan-stream    — SSE stream for live generation output
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.db.connection import get_connection
from backend.planner.generator import generate_plan
from backend.planner.schema import Plan, PlanStep

router = APIRouter(prefix="/api", tags=["plans"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CAPABILITIES_PATH = Path(__file__).resolve().parent.parent.parent / "config.yml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_capabilities() -> dict:
    """Try to load the capabilities section from config.yml.  Non-fatal."""
    try:
        import yaml
        with open(_CAPABILITIES_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("capabilities", {})
    except Exception:
        return {}


def _fetch_task(conn: sqlite3.Connection, task_id: int) -> dict:
    row = conn.execute("SELECT * FROM inbox WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return dict(row)


def _fetch_plan_row(conn: sqlite3.Connection, task_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM plans WHERE task_id = ? ORDER BY id DESC LIMIT 1", (task_id,)
    ).fetchone()
    return dict(row) if row else None


def _row_to_plan(row: dict) -> Plan:
    """Deserialise a plans table row into a Plan model."""
    steps_raw = []
    try:
        yaml_content = row.get("yaml_content", "")
        if yaml_content:
            import yaml as _yaml
            parsed = _yaml.safe_load(yaml_content) or {}
            steps_raw = parsed.get("steps", [])
    except Exception:
        pass

    steps = [PlanStep(**s) if isinstance(s, dict) else s for s in steps_raw]
    return Plan(
        id=row["id"],
        task_id=row["task_id"],
        steps=steps,
        status=row.get("status", "draft"),
        yaml_content=row.get("yaml_content", ""),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _upsert_plan(conn: sqlite3.Connection, task_id: int, yaml_content: str, steps: list[dict]) -> int:
    """Insert a new plan row (one plan per task, replaced on re-generation)."""
    # Delete previous plan for this task so we always have a single current plan
    conn.execute("DELETE FROM plans WHERE task_id = ?", (task_id,))
    now = _now()
    cursor = conn.execute(
        """
        INSERT INTO plans (task_id, yaml_content, status, created_at, updated_at)
        VALUES (?, ?, 'draft', ?, ?)
        """,
        (task_id, yaml_content, now, now),
    )
    conn.commit()
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/tasks/{task_id}/generate-plan")
async def generate_plan_for_task(task_id: int):
    """Generate a plan for a task using Claude CLI and persist it."""
    conn = get_connection()
    task = _fetch_task(conn, task_id)
    capabilities = _load_capabilities()

    # Run in a thread pool so we don't block the event loop during the
    # potentially long Claude CLI subprocess call.
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: generate_plan(dict(task), capabilities)
    )

    if result.get("error") and not result.get("steps"):
        raise HTTPException(status_code=502, detail=result["error"])

    plan_id = _upsert_plan(conn, task_id, result.get("yaml_content", ""), result.get("steps", []))
    plan_row = _fetch_plan_row(conn, task_id)
    plan = _row_to_plan(plan_row)

    return plan.model_dump()


@router.get("/tasks/{task_id}/plan")
async def get_plan(task_id: int):
    """Fetch the current plan for a task."""
    conn = get_connection()
    _fetch_task(conn, task_id)  # 404 if task missing
    plan_row = _fetch_plan_row(conn, task_id)
    if plan_row is None:
        return {"plan": None}
    return _row_to_plan(plan_row).model_dump()


@router.post("/tasks/{task_id}/plan/steps/{step_id}/approve")
async def approve_step(task_id: int, step_id: int):
    """Approve a specific plan step."""
    conn = get_connection()
    _fetch_task(conn, task_id)
    plan_row = _fetch_plan_row(conn, task_id)
    if plan_row is None:
        raise HTTPException(status_code=404, detail="No plan found for this task")

    import yaml as _yaml
    yaml_content = plan_row.get("yaml_content", "")
    plan_data = _yaml.safe_load(yaml_content) or {}
    steps: list[dict] = plan_data.get("steps", [])

    updated = False
    for step in steps:
        if step.get("id") == step_id:
            step["status"] = "approved"
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in plan")

    plan_data["steps"] = steps
    new_yaml = _yaml.dump(plan_data, default_flow_style=False)

    # Check if all steps are now approved → mark plan approved
    all_approved = all(s.get("status") == "approved" for s in steps)
    new_status = "approved" if all_approved else plan_row.get("status", "draft")

    conn.execute(
        "UPDATE plans SET yaml_content = ?, status = ?, updated_at = ? WHERE id = ?",
        (new_yaml, new_status, _now(), plan_row["id"]),
    )
    conn.commit()

    updated_row = _fetch_plan_row(conn, task_id)
    return _row_to_plan(updated_row).model_dump()


@router.post("/tasks/{task_id}/plan/approve-all")
async def approve_all_steps(task_id: int):
    """Approve all low-risk steps at once."""
    conn = get_connection()
    _fetch_task(conn, task_id)
    plan_row = _fetch_plan_row(conn, task_id)
    if plan_row is None:
        raise HTTPException(status_code=404, detail="No plan found for this task")

    import yaml as _yaml
    yaml_content = plan_row.get("yaml_content", "")
    plan_data = _yaml.safe_load(yaml_content) or {}
    steps: list[dict] = plan_data.get("steps", [])

    for step in steps:
        if step.get("risk_level", "low") == "low":
            step["status"] = "approved"

    plan_data["steps"] = steps
    new_yaml = _yaml.dump(plan_data, default_flow_style=False)

    all_approved = all(s.get("status") == "approved" for s in steps)
    new_status = "approved" if all_approved else plan_row.get("status", "draft")

    conn.execute(
        "UPDATE plans SET yaml_content = ?, status = ?, updated_at = ? WHERE id = ?",
        (new_yaml, new_status, _now(), plan_row["id"]),
    )
    conn.commit()

    updated_row = _fetch_plan_row(conn, task_id)
    return _row_to_plan(updated_row).model_dump()


@router.get("/tasks/{task_id}/plan-stream")
async def plan_stream(task_id: int):
    """
    SSE endpoint that streams plan generation output in real time.

    Emits:
      - data: {"type": "chunk", "text": "..."}   — incremental output
      - data: {"type": "done", "plan": {...}}     — final plan after storage
      - data: {"type": "error", "message": "..."}
    """
    conn = get_connection()
    task = _fetch_task(conn, task_id)
    capabilities = _load_capabilities()

    async def event_generator():
        try:
            yield _sse({"type": "chunk", "text": "Starting plan generation...\n"})
            yield _sse({"type": "chunk", "text": f"Task: {task['title']}\n"})
            yield _sse({"type": "chunk", "text": "Invoking Claude CLI...\n"})

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: generate_plan(dict(task), capabilities)
            )

            if result.get("error") and not result.get("steps"):
                yield _sse({"type": "error", "message": result["error"]})
                return

            yield _sse({"type": "chunk", "text": f"Plan generated with {len(result.get('steps', []))} steps.\n"})

            plan_id = _upsert_plan(conn, task_id, result.get("yaml_content", ""), result.get("steps", []))
            plan_row = _fetch_plan_row(conn, task_id)
            plan = _row_to_plan(plan_row)

            yield _sse({"type": "done", "plan": plan.model_dump()})

        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event frame."""
    return f"data: {json.dumps(data)}\n\n"
