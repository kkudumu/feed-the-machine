#!/usr/bin/env python3
"""Migrate tasks from active-tasks.md to tasks.db (idempotent)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tasks_db

ENG_BUDDY_ROOT = Path.home() / ".claude" / "eng-buddy"
ACTIVE_TASKS_PATH = ENG_BUDDY_ROOT / "tasks" / "active-tasks.md"

# Regex patterns
TASK_HEADER_RE = re.compile(r"^###\s+#(\d+)\s*-\s*(.+)$")
STATUS_RE = re.compile(r"^\*\*Status\*\*:\s*(.+)$")
PRIORITY_RE = re.compile(r"^\*\*Priority\*\*:\s*(.+)$")
JIRA_KEY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")
FRESHSERVICE_URL_RE = re.compile(r"https://klaviyo\.freshservice\.com/\S+")


def parse_tasks(content: str) -> list[dict]:
    """Parse task blocks from active-tasks.md, extracting all fields."""
    lines = content.splitlines()
    tasks: list[dict] = []
    current: dict | None = None

    def flush(end_idx: int) -> None:
        nonlocal current
        if current is None:
            return
        # Collect description lines (everything between header and next section/task)
        desc_lines = []
        for i in range(current["_body_start"], end_idx):
            desc_lines.append(lines[i])
        current["description"] = "\n".join(desc_lines).strip()
        del current["_body_start"]
        tasks.append(current)
        current = None

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()

        # Section headers end current block
        if line.startswith("## "):
            flush(idx)
            continue

        # Task header
        m = TASK_HEADER_RE.match(line)
        if m:
            flush(idx)
            current = {
                "number": int(m.group(1)),
                "title": m.group(2).strip(),
                "status": "unknown",
                "priority": "medium",
                "_body_start": idx + 1,
            }
            continue

        if current is None:
            continue

        # Status line
        sm = STATUS_RE.match(line)
        if sm:
            current["status"] = sm.group(1).strip()
            continue

        # Priority line
        pm = PRIORITY_RE.match(line)
        if pm:
            current["priority"] = pm.group(1).strip()
            continue

    flush(len(lines))
    return tasks


def map_status(raw: str) -> str:
    """Map raw status string to DB enum."""
    norm = raw.strip().lower()
    if norm.startswith(("completed", "closed", "done")):
        return "completed"
    if norm.startswith(("in_progress", "in progress")):
        return "in_progress"
    if norm.startswith("deferred"):
        return "deferred"
    return "pending"


def map_priority(raw: str) -> str:
    """Normalize priority to high/medium/low."""
    norm = raw.strip().lower()
    if norm in ("high", "critical", "highest"):
        return "high"
    if norm in ("low", "lower", "lowest"):
        return "low"
    return "medium"


def extract_jira_key(title: str, description: str) -> str | None:
    """Extract first Jira key from title or description."""
    for text in (title, description):
        m = JIRA_KEY_RE.search(text)
        if m:
            return m.group(0)
    return None


def extract_freshservice_url(description: str) -> str | None:
    """Extract Freshservice URL from description."""
    m = FRESHSERVICE_URL_RE.search(description)
    return m.group(0) if m else None


def find_existing_by_legacy_number(legacy_number: int) -> bool:
    """Check if a task with given legacy_number exists in metadata."""
    all_tasks = tasks_db.list_tasks(limit=500)
    for t in all_tasks:
        meta = t.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        if meta.get("legacy_number") == legacy_number:
            return True
    return False


def deduplicate(task: dict) -> bool:
    """Return True if this task already exists (should be skipped)."""
    jira_key = task.get("jira_key")
    if jira_key:
        existing = tasks_db.get_task_by_jira_key(jira_key)
        if existing:
            return True
    return find_existing_by_legacy_number(task["number"])


def main() -> None:
    if not ACTIVE_TASKS_PATH.exists():
        print(f"ERROR: {ACTIVE_TASKS_PATH} not found", file=sys.stderr)
        sys.exit(1)

    content = ACTIVE_TASKS_PATH.read_text(encoding="utf-8")
    raw_tasks = parse_tasks(content)

    # Deduplicate by task number (keep last occurrence, same as sync-task-lists)
    seen: dict[int, dict] = {}
    for t in raw_tasks:
        seen[t["number"]] = t
    unique_tasks = list(seen.values())

    new_count = 0
    skip_count = 0

    for task in unique_tasks:
        number = task["number"]
        title = task["title"]
        description = task["description"]
        status = map_status(task["status"])
        priority = map_priority(task["priority"])
        jira_key = extract_jira_key(title, description)
        freshservice_url = extract_freshservice_url(description)
        metadata = {"legacy_number": number}

        # Enrich task dict for dedup check
        task["jira_key"] = jira_key

        if deduplicate(task):
            skip_count += 1
            continue

        task_id = tasks_db.add_task(
            title=title,
            description=description,
            priority=priority,
            jira_key=jira_key,
            freshservice_url=freshservice_url,
            metadata=metadata,
        )

        # Set correct status (add_task defaults to 'pending')
        if status != "pending":
            tasks_db.update_task(task_id, status=status)

        new_count += 1

    total = len(unique_tasks)
    print(f"Migrated {total} tasks ({new_count} new, {skip_count} skipped as duplicates)")


if __name__ == "__main__":
    main()
