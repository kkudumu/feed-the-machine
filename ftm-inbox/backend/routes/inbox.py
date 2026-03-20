"""
Inbox API routes — paginated task listing with source/status filtering.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from backend.db.connection import get_connection

router = APIRouter(prefix="/api", tags=["inbox"])

_JSON_FIELDS = ("tags", "custom_fields", "raw_payload")


@router.get("/inbox")
async def list_inbox(
    source: str | None = Query(None, description="Filter by source"),
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Return paginated inbox tasks with optional filters."""
    conn = get_connection()
    conditions: list[str] = []
    params: list[str] = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"SELECT * FROM inbox{where} ORDER BY ingested_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    tasks = []
    for row in rows:
        task = dict(row)
        for field in _JSON_FIELDS:
            val = task.get(field)
            if val and isinstance(val, str):
                task[field] = json.loads(val)
        tasks.append(task)

    total = conn.execute(
        f"SELECT COUNT(*) as total FROM inbox{where}", params
    ).fetchone()["total"]

    return {"tasks": tasks, "total": total, "page": page, "per_page": per_page}


@router.get("/inbox/sources")
async def list_sources():
    """Return distinct source names with task counts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, COUNT(*) as count FROM inbox GROUP BY source ORDER BY count DESC"
    ).fetchall()
    return {"sources": [{"name": r["source"], "count": r["count"]} for r in rows]}
