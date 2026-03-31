#!/usr/bin/env python3
"""
eng-buddy Jira Poller
Fetches Jira issues assigned to the configured user via the Jira REST API.
Writes cards to inbox.db without routing through Claude.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

from poller_runtime import credential, single_instance

try:
    import tasks_db
    HAS_TASKS_DB = True
except ImportError:
    HAS_TASKS_DB = False

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
STATE_FILE = BASE_DIR / "jira-ingestor-state.json"
DB_PATH = BASE_DIR / "inbox.db"

JIRA_USER = os.environ.get("ENG_BUDDY_JIRA_USER") or credential("JIRA_EMAIL")
JIRA_BOARD_NAME = os.environ.get("ENG_BUDDY_JIRA_BOARD_NAME", "Systems")
JIRA_PROJECT_KEY = os.environ.get("ENG_BUDDY_JIRA_PROJECT_KEY", "ITWORK2")
JIRA_BASE_URL = credential("JIRA_BASE_URL").rstrip("/")
JIRA_API_TOKEN = credential("JIRA_API_TOKEN")


def set_last_checked(ts: str):
    STATE_FILE.write_text(json.dumps({"last_checked": ts}))


def _jira_get(path: str, params: dict[str, str] | None = None) -> dict:
    if not JIRA_BASE_URL or not JIRA_USER or not JIRA_API_TOKEN:
        raise RuntimeError("Missing Jira credentials")

    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)

    token = b64encode(f"{JIRA_USER}:{JIRA_API_TOKEN}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{JIRA_BASE_URL}{path}{query}",
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _pick_board(boards: list[dict]) -> dict | None:
    if not boards:
        return None

    preferred = []
    fallback = []
    target_name = JIRA_BOARD_NAME.lower()
    target_project = JIRA_PROJECT_KEY.lower()
    for board in boards:
        name = str(board.get("name") or "").lower()
        location = board.get("location") or {}
        location_name = str(location.get("name") or "").lower()
        if target_name in name and target_project in location_name:
            preferred.append(board)
        elif target_name in name:
            preferred.append(board)
        else:
            fallback.append(board)
    return (preferred or fallback or [None])[0]


def _pick_active_sprint(sprints: list[dict]) -> dict | None:
    if not sprints:
        return None

    preferred = []
    fallback = []
    for sprint in sprints:
        if str(sprint.get("state") or "").lower() != "active":
            continue
        name = str(sprint.get("name") or "").upper()
        if JIRA_PROJECT_KEY.upper() in name or name.startswith("SYSTEMS"):
            preferred.append(sprint)
        else:
            fallback.append(sprint)
    return (preferred or fallback or [None])[0]


def _issue_url(issue_key: str) -> str:
    return f"{JIRA_BASE_URL}/browse/{issue_key}" if issue_key else ""


def fetch_jira_issues() -> list[dict]:
    if not JIRA_BASE_URL or not JIRA_USER or not JIRA_API_TOKEN:
        print(f"[{datetime.now()}] Jira credentials missing, skipping sync.")
        return []

    board_payload = _jira_get(
        "/rest/agile/1.0/board",
        {"projectKeyOrId": JIRA_PROJECT_KEY, "maxResults": "50"},
    )
    board = _pick_board(board_payload.get("values", []))

    sprint = None
    if board and board.get("id"):
        sprint_payload = _jira_get(
            f"/rest/agile/1.0/board/{board['id']}/sprint",
            {"state": "active", "maxResults": "20"},
        )
        sprint = _pick_active_sprint(sprint_payload.get("values", []))

    if sprint and sprint.get("id"):
        jql = (
            f'assignee = "{JIRA_USER}" AND project = {JIRA_PROJECT_KEY} '
            f'AND sprint = {sprint["id"]} ORDER BY priority DESC, status ASC'
        )
    else:
        jql = (
            f'assignee = "{JIRA_USER}" AND project = {JIRA_PROJECT_KEY} '
            "AND statusCategory != Done ORDER BY priority DESC, status ASC"
        )

    payload = _jira_get(
        "/rest/api/3/search",
        {
            "jql": jql,
            "fields": "summary,status,priority,issuetype,labels,updated",
            "maxResults": "30",
        },
    )

    issues = []
    for issue in payload.get("issues", []):
        fields = issue.get("fields") or {}
        issues.append(
            {
                "key": issue.get("key", ""),
                "summary": fields.get("summary", ""),
                "status": (fields.get("status") or {}).get("name", ""),
                "priority": ((fields.get("priority") or {}).get("name") or "needs-response"),
                "updated": fields.get("updated", ""),
                "url": _issue_url(issue.get("key", "")),
            }
        )
    return issues


def write_card(conn: sqlite3.Connection, issue: dict):
    jira_key = issue.get("key", "")
    summary = f"{jira_key} — {issue.get('summary', '')}".strip()
    proposed = json.dumps(
        [
            {
                "type": "review_jira_issue",
                "draft": f"Review and update Jira issue {jira_key}: {issue.get('summary', '')}",
                "source": "jira",
                "url": issue.get("url", ""),
            }
        ]
    )
    conn.execute(
        """INSERT INTO cards
           (source, timestamp, summary, classification, status, proposed_actions, execution_status)
           VALUES (?, ?, ?, ?, 'pending', ?, 'not_run')
           ON CONFLICT(source, summary) DO UPDATE SET
               timestamp=excluded.timestamp,
               classification=excluded.classification,
               proposed_actions=excluded.proposed_actions,
               execution_status='not_run'""",
        (
            "jira",
            datetime.now(timezone.utc).isoformat(),
            summary,
            str(issue.get("priority") or "needs-response").lower(),
            proposed,
        ),
    )


def main():
    try:
        with single_instance("jira-poller"):
            issues = fetch_jira_issues()
            if not issues:
                print(f"[{datetime.now()}] No Jira issues found.")
                return

            conn = sqlite3.connect(DB_PATH)
            try:
                for issue in issues:
                    write_card(conn, issue)
                conn.commit()
            finally:
                conn.close()

            # Upsert into tasks.db if available
            if HAS_TASKS_DB:
                for issue in issues:
                    try:
                        tasks_db.upsert_jira_task(
                            jira_key=issue["key"],
                            title=issue.get("summary", ""),
                            jira_status=issue.get("status", ""),
                            priority=issue.get("priority", "Medium"),
                            metadata={"url": issue.get("url", ""), "labels": issue.get("labels", [])},
                        )
                    except Exception as exc:
                        print(f"[{datetime.now()}] tasks_db upsert failed for {issue.get('key', '?')}: {exc}")
                print(f"[{datetime.now()}] Synced {len(issues)} issues to tasks.db")

            set_last_checked(datetime.now(timezone.utc).isoformat())
            print(f"[{datetime.now()}] Processed {len(issues)} Jira issues.")
    except RuntimeError as exc:
        print(f"[{datetime.now()}] {exc}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"[{datetime.now()}] Jira API error {exc.code}: {body}")
    except Exception as exc:
        print(f"[{datetime.now()}] Jira poller failed: {exc}")


if __name__ == "__main__":
    main()
