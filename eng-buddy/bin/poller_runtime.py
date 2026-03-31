#!/usr/bin/env python3
"""Shared runtime helpers for eng-buddy background pollers."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
LOCK_DIR = BASE_DIR / "runtime" / "locks"
SETTINGS_CANDIDATES = [
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude.json",
]


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def background_ai_enabled() -> bool:
    """Background AI is opt-in so pollers stay collection-only by default."""
    return _truthy(os.environ.get("ENG_BUDDY_ALLOW_BACKGROUND_CLAUDE"))


def _load_mcp_credentials() -> dict[str, str]:
    for candidate in SETTINGS_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text())
        except Exception:
            continue

        servers = data.get("mcpServers") or data.get("mcp_servers") or {}
        freshservice_env = (servers.get("freshservice-mcp") or {}).get("env") or {}
        jira_env = (servers.get("mcp-atlassian") or {}).get("env") or {}
        slack_env = (servers.get("slack") or {}).get("env") or {}

        fs_domain = str(freshservice_env.get("FRESHSERVICE_DOMAIN", "")).strip()
        if fs_domain.endswith(".freshservice.com"):
            fs_domain = fs_domain[: -len(".freshservice.com")]

        return {
            "FRESHSERVICE_API_KEY": str(freshservice_env.get("FRESHSERVICE_APIKEY", "")).strip(),
            "FRESHSERVICE_DOMAIN": fs_domain,
            "JIRA_BASE_URL": str(jira_env.get("JIRA_URL", "")).strip(),
            "JIRA_EMAIL": str(jira_env.get("JIRA_USERNAME", "")).strip(),
            "JIRA_API_TOKEN": str(jira_env.get("JIRA_API_TOKEN", "")).strip(),
            "SLACK_BOT_TOKEN": str(slack_env.get("SLACK_BOT_TOKEN", "")).strip(),
            "SLACK_TEAM_ID": str(slack_env.get("SLACK_TEAM_ID", "")).strip(),
        }
    return {}


_MCP_CREDENTIALS = _load_mcp_credentials()


def credential(key: str, fallback: str = "") -> str:
    return _MCP_CREDENTIALS.get(key) or os.environ.get(key, fallback)


@contextlib.contextmanager
def single_instance(lock_name: str):
    """Prevent overlapping poller runs that can multiply Claude usage and DB locks."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f"{lock_name}.lock"
    handle = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError(f"{lock_name} already running")

    handle.seek(0)
    handle.truncate()
    handle.write(
        json.dumps(
            {
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    handle.flush()

    try:
        yield lock_path
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
