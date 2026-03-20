"""
Execution API routes — start, pause, resume, retry, audit log, SSE streaming.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.db.connection import get_connection
from backend.executor.engine import ExecutionEngine

router = APIRouter(prefix="/api", tags=["execution"])

# In-memory registry of active engines (single-process; swap for Redis in production)
_active_engines: dict[int, ExecutionEngine] = {}


@router.post("/tasks/{task_id}/execute")
async def start_execution(task_id: int):
    """Start execution of approved plan steps."""
    conn = get_connection()
    plan_row = conn.execute(
        "SELECT id, status FROM plans WHERE task_id = ? ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()

    if not plan_row:
        raise HTTPException(404, "No plan found for this task")

    plan_id = plan_row["id"]
    engine = ExecutionEngine(task_id, plan_id)
    _active_engines[task_id] = engine

    result = await engine.execute()
    _active_engines.pop(task_id, None)
    return result


@router.get("/tasks/{task_id}/execution-stream")
async def execution_stream(task_id: int):
    """SSE stream of execution output."""
    conn = get_connection()
    plan_row = conn.execute(
        "SELECT id FROM plans WHERE task_id = ? ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()

    if not plan_row:
        raise HTTPException(404, "No plan found for this task")

    plan_id = plan_row["id"]
    engine = ExecutionEngine(task_id, plan_id)
    _active_engines[task_id] = engine

    output_queue: asyncio.Queue[str] = asyncio.Queue()

    def on_output(text: str):
        output_queue.put_nowait(text)

    engine.on_output(on_output)

    async def event_generator():
        # Start execution in background
        task = asyncio.create_task(engine.execute())

        try:
            while not task.done():
                try:
                    text = await asyncio.wait_for(output_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

            # Drain remaining messages
            while not output_queue.empty():
                text = output_queue.get_nowait()
                yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"

            result = task.result()
            yield f"data: {json.dumps({'type': 'done', 'result': result})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            _active_engines.pop(task_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/tasks/{task_id}/pause")
async def pause_execution(task_id: int):
    """Pause execution after the current step completes."""
    engine = _active_engines.get(task_id)
    if not engine:
        raise HTTPException(404, "No active execution for this task")
    engine.pause()
    return {"status": "pausing", "message": "Execution will pause after current step"}


@router.post("/tasks/{task_id}/resume")
async def resume_execution(task_id: int):
    """Resume a paused execution."""
    engine = _active_engines.get(task_id)
    if engine:
        engine.resume()
        result = await engine.execute()
        return result

    # No active engine — restart from where we left off
    conn = get_connection()
    plan_row = conn.execute(
        "SELECT id FROM plans WHERE task_id = ? ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if not plan_row:
        raise HTTPException(404, "No plan found for this task")

    engine = ExecutionEngine(task_id, plan_row["id"])
    _active_engines[task_id] = engine
    result = await engine.execute()
    _active_engines.pop(task_id, None)
    return result


@router.post("/tasks/{task_id}/steps/{step_id}/retry")
async def retry_step(task_id: int, step_id: int):
    """Retry a failed step."""
    conn = get_connection()
    plan_row = conn.execute(
        "SELECT id, yaml_content FROM plans WHERE task_id = ? ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if not plan_row:
        raise HTTPException(404, "No plan found")

    import yaml
    plan_data = yaml.safe_load(plan_row["yaml_content"]) or {}
    for step in plan_data.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = "approved"

    updated = yaml.dump(plan_data, default_flow_style=False)
    conn.execute(
        "UPDATE plans SET yaml_content = ?, updated_at = datetime('now') WHERE id = ?",
        (updated, plan_row["id"]),
    )
    conn.commit()

    return {"status": "reset", "step_id": step_id, "message": "Step reset to approved, ready for re-execution"}


@router.get("/tasks/{task_id}/audit-log")
async def get_audit_log(task_id: int, limit: int = Query(100, ge=1, le=1000)):
    """Get audit log entries for a task's execution."""
    conn = get_connection()

    # Get all plan IDs for this task
    plan_rows = conn.execute(
        "SELECT id FROM plans WHERE task_id = ?", (task_id,)
    ).fetchall()
    if not plan_rows:
        return {"entries": []}

    plan_ids = [r["id"] for r in plan_rows]

    # Get step_ids from the plans to filter audit_log
    rows = conn.execute(
        f"SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    entries = []
    for row in rows:
        entry = dict(row)
        if entry.get("result") and isinstance(entry["result"], str):
            entry["result"] = json.loads(entry["result"])
        entries.append(entry)

    return {"entries": entries}
