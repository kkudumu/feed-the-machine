#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


ENG_BUDDY_ROOT = Path.home() / ".claude" / "eng-buddy"
TASKS_DIR = ENG_BUDDY_ROOT / "tasks"
ACTIVE_TASKS_PATH = TASKS_DIR / "active-tasks.md"
CHECKLIST_PATH = TASKS_DIR / "active-tasks-checklist.md"

COMPLETED_PREFIXES = ("completed", "closed", "done", "cancelled")


@dataclass
class TaskBlock:
    number: int
    title: str
    section: str
    status: str
    start: int
    end: int
    status_line_idx: int | None


def is_completed_status(status: str) -> bool:
    normalized = status.strip().lower()
    return normalized.startswith(COMPLETED_PREFIXES)


def parse_task_blocks(content: str) -> list[TaskBlock]:
    lines = content.splitlines()
    blocks: list[TaskBlock] = []
    section = "unknown"
    current: dict | None = None

    def flush(end_index: int) -> None:
        nonlocal current
        if not current:
            return
        blocks.append(
            TaskBlock(
                number=current["number"],
                title=current["title"],
                section=current["section"],
                status=current["status"],
                start=current["start"],
                end=end_index,
                status_line_idx=current["status_line_idx"],
            )
        )
        current = None

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()

        if line.startswith("## "):
            flush(idx)
            section = line[3:].strip().lower().replace(" ", "-")
            continue

        task_match = re.match(r"^###\s+#(\d+)\s*-\s*(.+)$", line)
        if task_match:
            flush(idx)
            current = {
                "number": int(task_match.group(1)),
                "title": task_match.group(2).strip(),
                "section": section,
                "status": "unknown",
                "start": idx,
                "status_line_idx": None,
            }
            continue

        if current is None:
            continue

        status_match = re.match(r"^\*\*Status\*\*:\s*(.+)$", line)
        if status_match:
            current["status"] = status_match.group(1).strip()
            current["status_line_idx"] = idx

    flush(len(lines))
    return blocks


def latest_blocks_by_number(blocks: list[TaskBlock]) -> list[TaskBlock]:
    latest: dict[int, TaskBlock] = {}
    order: list[int] = []
    for block in blocks:
        if block.number not in latest:
            order.append(block.number)
        latest[block.number] = block
    return [latest[number] for number in order if number in latest]


def parse_checklist(content: str) -> dict[int, bool]:
    current_section = ""
    states: dict[int, bool] = {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            continue

        match = re.match(r"^- \[([ xX])\]\s+`?#(\d+)`?(?:\s*-\s*|\s+)(.+)$", line)
        if not match:
            continue

        checked = match.group(1).lower() == "x"
        number = int(match.group(2))

        if current_section == "active":
            states[number] = False
        elif current_section == "completed":
            states[number] = True
        else:
            states[number] = checked

    return states


def update_status_line(lines: list[str], block: TaskBlock, checked: bool) -> bool:
    if block.status_line_idx is None:
        return False

    current_completed = is_completed_status(block.status)
    if current_completed == checked:
        return False

    if checked:
        new_status = f"completed ({date.today().isoformat()})"
    else:
        new_status = "pending"

    lines[block.status_line_idx] = f"**Status**: {new_status}"
    return True


def render_checklist(blocks: list[TaskBlock]) -> str:
    latest = latest_blocks_by_number(blocks)
    active = [block for block in latest if not is_completed_status(block.status)]
    completed = [block for block in latest if is_completed_status(block.status)]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Active Tasks Checklist",
        "",
        "Generated from `tasks/active-tasks.md` by `sync-task-lists.py`.",
        "Checkbox edits may be used to mark tasks complete or reopen them, but titles and task details still come from `active-tasks.md`.",
        f"Last synchronized: {timestamp}",
        "",
        "## Active",
        "",
    ]

    if active:
        for block in active:
            lines.append(f"- [ ] `#{block.number}` {block.title}")
    else:
        lines.append("- [ ] No active tasks")

    lines.extend(["", "## Completed", ""])
    if completed:
        for block in completed:
            lines.append(f"- [x] `#{block.number}` {block.title}")
    else:
        lines.append("- [x] No completed tasks")

    lines.append("")
    return "\n".join(lines)


def sync(prefer: str = "newer", dry_run: bool = False) -> tuple[int, int]:
    if not ACTIVE_TASKS_PATH.exists():
        raise FileNotFoundError(f"Missing source task file: {ACTIVE_TASKS_PATH}")

    active_text = ACTIVE_TASKS_PATH.read_text(encoding="utf-8")
    active_lines = active_text.splitlines()
    blocks = parse_task_blocks(active_text)
    checklist_states = {}
    checklist_exists = CHECKLIST_PATH.exists()

    active_mtime = ACTIVE_TASKS_PATH.stat().st_mtime
    checklist_mtime = CHECKLIST_PATH.stat().st_mtime if checklist_exists else 0.0

    if checklist_exists:
        checklist_states = parse_checklist(CHECKLIST_PATH.read_text(encoding="utf-8"))

    apply_checklist_overrides = False
    if checklist_exists and checklist_states:
        if prefer == "checklist":
            apply_checklist_overrides = True
        elif prefer == "newer" and checklist_mtime > active_mtime:
            apply_checklist_overrides = True

    overrides_applied = 0
    if apply_checklist_overrides:
        latest = {block.number: block for block in latest_blocks_by_number(blocks)}
        for number, checked in checklist_states.items():
            block = latest.get(number)
            if block and update_status_line(active_lines, block, checked):
                overrides_applied += 1

    if overrides_applied:
        active_text = "\n".join(active_lines) + "\n"
        blocks = parse_task_blocks(active_text)
        if not dry_run:
            ACTIVE_TASKS_PATH.write_text(active_text, encoding="utf-8")

    checklist_text = render_checklist(blocks)
    if not dry_run:
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        CHECKLIST_PATH.write_text(checklist_text, encoding="utf-8")

    return len(latest_blocks_by_number(blocks)), overrides_applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep eng-buddy task files synchronized.")
    parser.add_argument(
        "--prefer",
        choices=("newer", "tasks", "checklist"),
        default="newer",
        help="Choose which file wins when task status and checklist checkboxes disagree.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing changes.")
    args = parser.parse_args()

    try:
        task_count, overrides_applied = sync(prefer=args.prefer, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    mode = "previewed" if args.dry_run else "synchronized"
    print(
        f"{mode} {task_count} unique tasks between "
        f"{ACTIVE_TASKS_PATH.name} and {CHECKLIST_PATH.name}; "
        f"applied {overrides_applied} checklist override(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
