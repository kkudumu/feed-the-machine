"""Structured memory system with separated memory types.

Suggestion 4 from the brain dump:
"Self-learning will be trash unless you separate memory types:
- Episodic memory: what happened in this specific run
- Procedural memory: how a type of task gets done
- Semantic memory: facts about systems, people, apps, permissions
- Policy memory: what is allowed, risky, or approval-gated
- Preference memory: how you like to work"
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryType(str, Enum):
    EPISODIC = "episodic"       # what happened in a specific run
    PROCEDURAL = "procedural"   # how a type of task gets done
    SEMANTIC = "semantic"       # facts about systems, people, apps
    POLICY = "policy"           # what is allowed, risky, approval-gated
    PREFERENCE = "preference"   # how the user likes to work


# ---------------------------------------------------------------------------
# Memory entries
# ---------------------------------------------------------------------------

@dataclass
class EpisodicMemory:
    """What happened in a specific execution run."""
    run_id: str
    card_id: Optional[int] = None
    playbook_id: Optional[str] = None
    action_taken: str = ""
    outcome: str = ""  # "success", "failure", "partial"
    duration_seconds: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0
    error_message: str = ""
    lessons: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "type": MemoryType.EPISODIC.value,
            "run_id": self.run_id,
            "card_id": self.card_id,
            "playbook_id": self.playbook_id,
            "action_taken": self.action_taken,
            "outcome": self.outcome,
            "duration_seconds": self.duration_seconds,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "error_message": self.error_message,
            "lessons": self.lessons,
            "timestamp": self.timestamp,
        }


@dataclass
class ProceduralMemory:
    """How a type of task gets done — extracted from successful runs."""
    task_type: str  # "sso-setup", "access-request", etc.
    description: str = ""
    typical_steps: List[str] = field(default_factory=list)
    typical_tools: List[str] = field(default_factory=list)
    typical_duration_seconds: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    last_successful_run: Optional[str] = None
    tips: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "type": MemoryType.PROCEDURAL.value,
            "task_type": self.task_type,
            "description": self.description,
            "typical_steps": self.typical_steps,
            "typical_tools": self.typical_tools,
            "typical_duration_seconds": self.typical_duration_seconds,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_successful_run": self.last_successful_run,
            "tips": self.tips,
            "updated_at": self.updated_at,
        }


@dataclass
class SemanticFact:
    """A fact about a system, person, app, or permission."""
    subject: str       # "okta", "jira", "ashley.kronstat", "freshservice-portal"
    predicate: str     # "has_capability", "is_managed_by", "requires_auth"
    value: str         # "saml-sso", "IT Engineering", "oauth2"
    confidence: float = 1.0
    source: str = ""   # where we learned this
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "type": MemoryType.SEMANTIC.value,
            "subject": self.subject,
            "predicate": self.predicate,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "updated_at": self.updated_at,
        }


@dataclass
class PolicyRule:
    """What is allowed, risky, or requires approval."""
    rule_id: str
    description: str
    scope: str = "global"    # "global", "jira", "freshservice", "okta", etc.
    action: str = "warn"     # "allow", "warn", "require_approval", "deny"
    conditions: dict = field(default_factory=dict)  # when does this apply
    source: str = "learned"  # "learned", "configured", "policy-pack"
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "type": MemoryType.POLICY.value,
            "rule_id": self.rule_id,
            "description": self.description,
            "scope": self.scope,
            "action": self.action,
            "conditions": self.conditions,
            "source": self.source,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class PreferenceEntry:
    """How the user likes to work."""
    key: str           # "response_tone", "auto_close_resolved", "jira_template"
    value: Any = None
    category: str = ""  # "communication", "workflow", "ui", "scheduling"
    source: str = "observed"  # "observed", "configured", "default"
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "type": MemoryType.PREFERENCE.value,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "source": self.source,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Memory Store
# ---------------------------------------------------------------------------

class MemoryStore:
    """SQLite-backed memory store with separated memory types.

    Provides typed storage and retrieval for all five memory categories.
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
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(memory_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_key ON memory(memory_type, key)"
            )
            conn.commit()
        finally:
            conn.close()

    # -- Generic operations --

    def store(self, memory_type: str, key: str, data: dict) -> int:
        """Store or update a memory entry. Returns row ID."""
        conn = self._conn()
        now = datetime.now().isoformat()
        try:
            # Upsert: check if key exists for this type
            existing = conn.execute(
                "SELECT id FROM memory WHERE memory_type = ? AND key = ?",
                (memory_type, key),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE memory SET data = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(data), now, existing["id"]),
                )
                conn.commit()
                return existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO memory (memory_type, key, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (memory_type, key, json.dumps(data), now, now),
                )
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def append(self, memory_type: str, key: str, data: dict) -> int:
        """Append a new memory entry (does not upsert). Returns row ID."""
        conn = self._conn()
        now = datetime.now().isoformat()
        try:
            cursor = conn.execute(
                "INSERT INTO memory (memory_type, key, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (memory_type, key, json.dumps(data), now, now),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get(self, memory_type: str, key: str) -> Optional[dict]:
        """Retrieve a memory entry by type and key."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT data FROM memory WHERE memory_type = ? AND key = ? ORDER BY updated_at DESC LIMIT 1",
                (memory_type, key),
            ).fetchone()
            return json.loads(row["data"]) if row else None
        finally:
            conn.close()

    def list_by_type(self, memory_type: str, limit: int = 100) -> List[dict]:
        """List all entries of a given memory type."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT key, data, created_at, updated_at FROM memory WHERE memory_type = ? ORDER BY updated_at DESC LIMIT ?",
                (memory_type, limit),
            ).fetchall()
            results = []
            for r in rows:
                d = json.loads(r["data"])
                d["_key"] = r["key"]
                d["_created_at"] = r["created_at"]
                d["_updated_at"] = r["updated_at"]
                results.append(d)
            return results
        finally:
            conn.close()

    def search(self, memory_type: str, query: str, limit: int = 20) -> List[dict]:
        """Search memory entries by type with a LIKE query on key and data."""
        conn = self._conn()
        like = f"%{query}%"
        try:
            rows = conn.execute(
                "SELECT key, data FROM memory WHERE memory_type = ? AND (key LIKE ? OR data LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                (memory_type, like, like, limit),
            ).fetchall()
            results = []
            for r in rows:
                d = json.loads(r["data"])
                d["_key"] = r["key"]
                results.append(d)
            return results
        finally:
            conn.close()

    def delete(self, memory_type: str, key: str) -> bool:
        """Delete a memory entry."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM memory WHERE memory_type = ? AND key = ?",
                (memory_type, key),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # -- Typed convenience methods --

    def store_episodic(self, mem: EpisodicMemory) -> int:
        return self.append(MemoryType.EPISODIC.value, mem.run_id, mem.to_dict())

    def store_procedural(self, mem: ProceduralMemory) -> int:
        return self.store(MemoryType.PROCEDURAL.value, mem.task_type, mem.to_dict())

    def store_fact(self, fact: SemanticFact) -> int:
        key = f"{fact.subject}:{fact.predicate}"
        return self.store(MemoryType.SEMANTIC.value, key, fact.to_dict())

    def store_policy(self, rule: PolicyRule) -> int:
        return self.store(MemoryType.POLICY.value, rule.rule_id, rule.to_dict())

    def store_preference(self, pref: PreferenceEntry) -> int:
        return self.store(MemoryType.PREFERENCE.value, pref.key, pref.to_dict())

    def get_procedural(self, task_type: str) -> Optional[dict]:
        return self.get(MemoryType.PROCEDURAL.value, task_type)

    def get_preference(self, key: str) -> Optional[dict]:
        return self.get(MemoryType.PREFERENCE.value, key)

    def get_policy(self, rule_id: str) -> Optional[dict]:
        return self.get(MemoryType.POLICY.value, rule_id)

    def get_facts_about(self, subject: str) -> List[dict]:
        return self.search(MemoryType.SEMANTIC.value, subject)

    def get_recent_episodes(self, limit: int = 20) -> List[dict]:
        return self.list_by_type(MemoryType.EPISODIC.value, limit=limit)

    def get_all_policies(self, active_only: bool = True) -> List[dict]:
        policies = self.list_by_type(MemoryType.POLICY.value, limit=500)
        if active_only:
            policies = [p for p in policies if p.get("active", True)]
        return policies

    def get_all_preferences(self) -> List[dict]:
        return self.list_by_type(MemoryType.PREFERENCE.value, limit=500)
