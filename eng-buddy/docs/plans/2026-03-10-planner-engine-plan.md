# Planning Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone planning engine that automatically generates step-by-step execution plans for incoming dashboard cards, using playbook matching and LLM fallback via Claude CLI.

**Architecture:** New `bin/planner/` Python module with 5 files (models, store, prompter, planner, worker). Integrates with existing PlaybookManager for matching, ToolRegistry for available tools, and brain.py for learned context. Background worker daemon polls for unplanned cards. Dashboard server gets 5 new API routes and 2 new SSE events.

**Tech Stack:** Python 3.11+, dataclasses, JSON persistence, SQLite (inbox.db), Claude CLI subprocess, pytest

**Design doc:** `docs/plans/2026-03-10-planner-engine-design.md`

**Key reference files:**
- `bin/playbook_engine/models.py` — PlaybookStep, ActionBinding, Playbook (compatibility target)
- `bin/playbook_engine/manager.py` — PlaybookManager.match_ticket(), save_draft()
- `bin/playbook_engine/registry.py` — ToolRegistry (tool catalog, defaults)
- `bin/brain.py` — build_context_prompt() (learned rules, stakeholders)
- `dashboard/server.py` — SSE via _stale_sources set, existing playbook API routes
- `bin/playbook_engine/test_models.py` — test patterns to follow

---

### Task 1: Plan data models

**Files:**
- Create: `bin/planner/__init__.py`
- Create: `bin/planner/models.py`
- Create: `bin/planner/test_models.py`

**Step 1: Write the failing test**

Create `bin/planner/test_models.py`:

```python
import pytest
from models import Plan, Phase, PlanStep


def test_plan_step_from_dict():
    raw = {
        "index": 1,
        "summary": "Create Jira ticket",
        "detail": "Create ITWORK2 ticket under SSO epic",
        "action_type": "mcp",
        "tool": "mcp__mcp-atlassian__jira_create_issue",
        "params": {"project": "ITWORK2"},
        "param_sources": {},
        "draft_content": None,
        "risk": "low",
        "status": "pending",
        "output": None,
    }
    step = PlanStep.from_dict(raw)
    assert step.index == 1
    assert step.tool == "mcp__mcp-atlassian__jira_create_issue"
    assert step.risk == "low"
    assert step.status == "pending"


def test_plan_step_round_trip():
    raw = {
        "index": 2,
        "summary": "Send Slack notification",
        "detail": "Notify #it-ops channel",
        "action_type": "mcp",
        "tool": "mcp__slack__slack_post_message",
        "params": {"channel": "it-ops"},
        "param_sources": {},
        "draft_content": "SSO ticket created for {{app_name}}",
        "risk": "medium",
        "status": "pending",
        "output": None,
    }
    step = PlanStep.from_dict(raw)
    assert step.to_dict() == raw


def test_phase_from_dict():
    raw = {
        "name": "Setup",
        "steps": [
            {
                "index": 1,
                "summary": "Look up requester",
                "detail": "Find requester info",
                "action_type": "mcp",
                "tool": "mcp__freshservice-mcp__get_requester_id",
                "params": {},
                "param_sources": {},
                "draft_content": None,
                "risk": "low",
                "status": "pending",
                "output": None,
            }
        ],
    }
    phase = Phase.from_dict(raw)
    assert phase.name == "Setup"
    assert len(phase.steps) == 1
    assert phase.steps[0].summary == "Look up requester"


def test_plan_from_dict():
    raw = {
        "id": "plan-42-1710000000",
        "card_id": 42,
        "source": "playbook",
        "playbook_id": "sso-onboarding",
        "confidence": 0.85,
        "phases": [
            {
                "name": "Setup",
                "steps": [
                    {
                        "index": 1,
                        "summary": "Create Jira ticket",
                        "detail": "Create under SSO epic",
                        "action_type": "mcp",
                        "tool": "mcp__mcp-atlassian__jira_create_issue",
                        "params": {"project": "ITWORK2"},
                        "param_sources": {},
                        "draft_content": None,
                        "risk": "low",
                        "status": "pending",
                        "output": None,
                    }
                ],
            }
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    }
    plan = Plan.from_dict(raw)
    assert plan.id == "plan-42-1710000000"
    assert plan.card_id == 42
    assert plan.source == "playbook"
    assert plan.confidence == 0.85
    assert len(plan.phases) == 1
    assert plan.phases[0].steps[0].tool == "mcp__mcp-atlassian__jira_create_issue"


def test_plan_round_trip_json(tmp_path):
    raw = {
        "id": "plan-99-1710000000",
        "card_id": 99,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.7,
        "phases": [],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    }
    plan = Plan.from_dict(raw)
    path = tmp_path / "test-plan.json"
    plan.save(str(path))
    loaded = Plan.load(str(path))
    assert loaded.id == plan.id
    assert loaded.card_id == plan.card_id
    assert loaded.source == plan.source


def test_plan_all_steps():
    plan = Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
            ]},
            {"name": "Execute", "steps": [
                {"index": 2, "summary": "s2", "detail": "", "action_type": "mcp", "tool": "t2", "params": {}, "param_sources": {}, "draft_content": None, "risk": "medium", "status": "pending", "output": None},
                {"index": 3, "summary": "s3", "detail": "", "action_type": "playwright", "tool": "t3", "params": {}, "param_sources": {}, "draft_content": None, "risk": "high", "status": "pending", "output": None},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })
    all_steps = plan.all_steps()
    assert len(all_steps) == 3
    assert [s.index for s in all_steps] == [1, 2, 3]


def test_plan_get_step():
    plan = Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
                {"index": 2, "summary": "s2", "detail": "", "action_type": "mcp", "tool": "t2", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })
    step = plan.get_step(2)
    assert step is not None
    assert step.summary == "s2"
    assert plan.get_step(99) is None


def test_plan_has_missing_tools():
    plan = Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [
            {"name": "Execute", "steps": [
                {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "__MISSING__", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None, "missing_capability": {"description": "Okta admin", "domain": "identity", "systems": ["Okta"]}},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })
    assert plan.has_missing_tools() is True
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_models.py -v
```

Expected: FAIL — module `models` not found

**Step 3: Write the models**

Create `bin/planner/__init__.py`:

```python
```

Create `bin/planner/models.py`:

```python
"""Plan data models — phases, steps, and execution plans for dashboard cards."""

import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class PlanStep:
    index: int
    summary: str
    detail: str
    action_type: str  # "api", "mcp", "playwright"
    tool: str  # exact MCP tool name or "__MISSING__"
    params: dict = field(default_factory=dict)
    param_sources: dict = field(default_factory=dict)
    draft_content: Optional[str] = None
    risk: str = "low"  # "low", "medium", "high"
    status: str = "pending"  # "pending", "approved", "skipped", "edited", "executing", "done", "failed"
    output: Optional[str] = None
    missing_capability: Optional[dict] = None  # set when tool == "__MISSING__"

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        return cls(
            index=d["index"],
            summary=d["summary"],
            detail=d["detail"],
            action_type=d["action_type"],
            tool=d["tool"],
            params=d.get("params", {}),
            param_sources=d.get("param_sources", {}),
            draft_content=d.get("draft_content"),
            risk=d.get("risk", "low"),
            status=d.get("status", "pending"),
            output=d.get("output"),
            missing_capability=d.get("missing_capability"),
        )

    def to_dict(self) -> dict:
        d = {
            "index": self.index,
            "summary": self.summary,
            "detail": self.detail,
            "action_type": self.action_type,
            "tool": self.tool,
            "params": self.params,
            "param_sources": self.param_sources,
            "draft_content": self.draft_content,
            "risk": self.risk,
            "status": self.status,
            "output": self.output,
        }
        if self.missing_capability:
            d["missing_capability"] = self.missing_capability
        return d


@dataclass
class Phase:
    name: str
    steps: list  # list of PlanStep

    @classmethod
    def from_dict(cls, d: dict) -> "Phase":
        return cls(
            name=d["name"],
            steps=[PlanStep.from_dict(s) for s in d.get("steps", [])],
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class Plan:
    id: str
    card_id: int
    source: str  # "playbook", "llm", "hybrid"
    playbook_id: Optional[str]
    confidence: float
    phases: list  # list of Phase
    status: str  # "pending", "approved", "executing", "completed", "failed"
    created_at: str
    executed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            id=d["id"],
            card_id=d["card_id"],
            source=d["source"],
            playbook_id=d.get("playbook_id"),
            confidence=d["confidence"],
            phases=[Phase.from_dict(p) for p in d.get("phases", [])],
            status=d.get("status", "pending"),
            created_at=d["created_at"],
            executed_at=d.get("executed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "card_id": self.card_id,
            "source": self.source,
            "playbook_id": self.playbook_id,
            "confidence": self.confidence,
            "phases": [p.to_dict() for p in self.phases],
            "status": self.status,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
        }

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "Plan":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def all_steps(self) -> list:
        """Return all steps across all phases, in order."""
        steps = []
        for phase in self.phases:
            steps.extend(phase.steps)
        return steps

    def get_step(self, index: int) -> Optional["PlanStep"]:
        """Find a step by global index."""
        for step in self.all_steps():
            if step.index == index:
                return step
        return None

    def has_missing_tools(self) -> bool:
        """Check if any step has a __MISSING__ tool."""
        return any(s.tool == "__MISSING__" for s in self.all_steps())
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_models.py -v
```

Expected: 8 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/
git commit -m "Add plan data models with Phase, PlanStep, and Plan dataclasses"
```

---

### Task 2: Plan store (persistence layer)

**Files:**
- Create: `bin/planner/store.py`
- Create: `bin/planner/test_store.py`

**Step 1: Write the failing test**

Create `bin/planner/test_store.py`:

```python
import pytest
from pathlib import Path
from models import Plan
from store import PlanStore


@pytest.fixture
def store(tmp_path):
    plans_dir = tmp_path / "plans"
    db_path = tmp_path / "inbox.db"
    return PlanStore(str(plans_dir), str(db_path))


def _make_plan(card_id: int, source: str = "llm") -> Plan:
    return Plan.from_dict({
        "id": f"plan-{card_id}-0",
        "card_id": card_id,
        "source": source,
        "playbook_id": None,
        "confidence": 0.7,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "step 1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
            ]},
        ],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })


def test_save_and_get(store):
    plan = _make_plan(42)
    store.save(plan)
    loaded = store.get(42)
    assert loaded is not None
    assert loaded.card_id == 42
    assert loaded.source == "llm"


def test_get_nonexistent(store):
    assert store.get(999) is None


def test_save_overwrites(store):
    plan1 = _make_plan(42)
    store.save(plan1)
    plan2 = _make_plan(42, source="playbook")
    store.save(plan2)
    loaded = store.get(42)
    assert loaded.source == "playbook"


def test_delete(store):
    plan = _make_plan(42)
    store.save(plan)
    assert store.delete(42) is True
    assert store.get(42) is None


def test_delete_nonexistent(store):
    assert store.delete(999) is False


def test_has_plan(store):
    assert store.has_plan(42) is False
    store.save(_make_plan(42))
    assert store.has_plan(42) is True


def test_list_by_status(store):
    store.save(_make_plan(1))
    plan2 = _make_plan(2)
    plan2.status = "completed"
    store.save(plan2)
    pending = store.list_by_status("pending")
    assert len(pending) == 1
    assert pending[0].card_id == 1


def test_cards_needing_plans(store):
    """Cards with status pending and no plan should be returned."""
    import sqlite3
    conn = sqlite3.connect(str(store.db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, source TEXT, status TEXT, summary TEXT, context_notes TEXT, timestamp TEXT, classification TEXT, section TEXT)")
    conn.execute("INSERT INTO cards VALUES (1, 'gmail', 'pending', 'test card', '', '2026-03-10', 'high', '')")
    conn.execute("INSERT INTO cards VALUES (2, 'slack', 'pending', 'another card', '', '2026-03-10', 'low', '')")
    conn.execute("INSERT INTO cards VALUES (3, 'jira', 'completed', 'done card', '', '2026-03-10', 'low', '')")
    conn.commit()
    conn.close()

    store.save(_make_plan(1))  # card 1 already has a plan
    needing = store.cards_needing_plans()
    assert len(needing) == 1
    assert needing[0]["id"] == 2
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_store.py -v
```

Expected: FAIL — module `store` not found

**Step 3: Write the store**

Create `bin/planner/store.py`:

```python
"""Plan persistence — JSON files + SQLite index."""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from models import Plan


class PlanStore:
    def __init__(self, plans_dir: str, db_path: str):
        self.plans_dir = Path(plans_dir)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                card_id INTEGER PRIMARY KEY,
                plan_id TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def save(self, plan: Plan) -> str:
        path = self.plans_dir / f"{plan.card_id}.json"
        plan.save(str(path))

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO plans (card_id, plan_id, source, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (plan.card_id, plan.id, plan.source, plan.status, plan.created_at),
            )
            conn.commit()
        finally:
            conn.close()
        return str(path)

    def get(self, card_id: int) -> Optional[Plan]:
        path = self.plans_dir / f"{card_id}.json"
        if path.exists():
            return Plan.load(str(path))
        return None

    def delete(self, card_id: int) -> bool:
        path = self.plans_dir / f"{card_id}.json"
        if not path.exists():
            return False
        path.unlink()
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM plans WHERE card_id = ?", (card_id,))
            conn.commit()
        finally:
            conn.close()
        return True

    def has_plan(self, card_id: int) -> bool:
        return (self.plans_dir / f"{card_id}.json").exists()

    def list_by_status(self, status: str) -> list:
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT card_id FROM plans WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        finally:
            conn.close()
        plans = []
        for (card_id,) in rows:
            plan = self.get(card_id)
            if plan:
                plans.append(plan)
        return plans

    def cards_needing_plans(self) -> list:
        """Find cards with status 'pending' that don't have a plan yet."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT c.* FROM cards c
                LEFT JOIN plans p ON c.id = p.card_id
                WHERE c.status = 'pending' AND p.card_id IS NULL
                ORDER BY c.id ASC
            """).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def update_status(self, card_id: int, status: str) -> None:
        plan = self.get(card_id)
        if plan:
            plan.status = status
            self.save(plan)
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_store.py -v
```

Expected: 8 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/store.py bin/planner/test_store.py
git commit -m "Add PlanStore with JSON persistence and SQLite index"
```

---

### Task 3: Playbook-to-plan converter

**Files:**
- Create: `bin/planner/converter.py`
- Create: `bin/planner/test_converter.py`

**Step 1: Write the failing test**

Create `bin/planner/test_converter.py`:

```python
import pytest
import sys
from pathlib import Path

# Allow importing from playbook_engine
sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan, Phase, PlanStep
from converter import playbook_to_plan


def _make_playbook_dict():
    return {
        "id": "sso-onboarding",
        "name": "SSO Onboarding",
        "version": 1,
        "confidence": "high",
        "trigger_patterns": [{"ticket_type": "Service Request", "keywords": ["SSO"], "source": ["freshservice"]}],
        "created_from": "session",
        "executions": 5,
        "steps": [
            {
                "id": 1,
                "name": "Create Jira ticket",
                "action": {"tool": "mcp__mcp-atlassian__jira_create_issue", "params": {"project": "ITWORK2"}},
                "auth_required": False,
                "human_required": False,
            },
            {
                "id": 2,
                "name": "Update Freshservice status",
                "action": {"tool": "mcp__freshservice-mcp__update_ticket", "params": {"status": 3}},
                "auth_required": False,
                "human_required": False,
            },
            {
                "id": 3,
                "name": "Notify requester",
                "action": {"tool": "mcp__freshservice-mcp__send_ticket_reply", "params": {}},
                "auth_required": False,
                "human_required": False,
            },
        ],
    }


def test_converts_playbook_to_plan():
    from importlib import import_module
    pb_models = import_module("models", package="playbook_engine")
    # Use the playbook_engine models
    sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))
    from models import Playbook as PBPlaybook
    pb = PBPlaybook.from_dict(_make_playbook_dict())

    plan = playbook_to_plan(pb, card_id=42)
    assert plan.card_id == 42
    assert plan.source == "playbook"
    assert plan.playbook_id == "sso-onboarding"
    assert plan.status == "pending"


def test_groups_steps_into_phases():
    sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))
    from models import Playbook as PBPlaybook
    pb = PBPlaybook.from_dict(_make_playbook_dict())

    plan = playbook_to_plan(pb, card_id=42)
    phase_names = [p.name for p in plan.phases]
    # Should have at least Setup and Communicate (notification is communication)
    assert len(plan.phases) >= 1
    total_steps = sum(len(p.steps) for p in plan.phases)
    assert total_steps == 3


def test_maps_confidence():
    sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))
    from models import Playbook as PBPlaybook
    pb = PBPlaybook.from_dict(_make_playbook_dict())

    plan = playbook_to_plan(pb, card_id=42)
    # "high" confidence playbook -> 0.9+ confidence float
    assert plan.confidence >= 0.8


def test_infers_action_type():
    sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))
    from models import Playbook as PBPlaybook
    pb = PBPlaybook.from_dict(_make_playbook_dict())

    plan = playbook_to_plan(pb, card_id=42)
    steps = plan.all_steps()
    # All steps use MCP tools
    assert all(s.action_type == "mcp" for s in steps)


def test_infers_risk():
    sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))
    from models import Playbook as PBPlaybook
    pb = PBPlaybook.from_dict(_make_playbook_dict())

    plan = playbook_to_plan(pb, card_id=42)
    steps = plan.all_steps()
    # send_ticket_reply is a communication action -> medium risk
    reply_step = [s for s in steps if "reply" in s.tool][0]
    assert reply_step.risk in ("medium", "low")
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_converter.py -v
```

Expected: FAIL — module `converter` not found

**Step 3: Write the converter**

Create `bin/planner/converter.py`:

```python
"""Convert Playbook objects into Plan objects for the approval flow."""

import time
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Allow importing playbook_engine models
sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan, Phase, PlanStep

if TYPE_CHECKING:
    from models import Playbook as PBPlaybook


CONFIDENCE_MAP = {"low": 0.4, "medium": 0.7, "high": 0.95}

# Tools whose primary action is sending/modifying external state
MEDIUM_RISK_PATTERNS = ["send_", "reply", "post_message", "update_", "transition_", "create_issue", "create_ticket"]
HIGH_RISK_PATTERNS = ["delete_", "remove_", "drop_", "reset_"]

# Phase classification heuristics based on tool domains
COMMUNICATE_TOOLS = ["slack", "gmail", "send_", "reply", "post_message", "draft_email", "send_email"]
SETUP_TOOLS = ["get_", "search_", "list_", "filter_", "find_", "read_"]


def _infer_action_type(tool: str) -> str:
    if "playwright" in tool:
        return "playwright"
    return "mcp"


def _infer_risk(tool: str) -> str:
    tool_lower = tool.lower()
    if any(p in tool_lower for p in HIGH_RISK_PATTERNS):
        return "high"
    if any(p in tool_lower for p in MEDIUM_RISK_PATTERNS):
        return "medium"
    return "low"


def _classify_phase(tool: str, step_name: str) -> str:
    combined = (tool + " " + step_name).lower()
    if any(p in combined for p in COMMUNICATE_TOOLS):
        return "Communicate"
    if any(p in combined for p in SETUP_TOOLS):
        return "Setup"
    return "Execute"


def playbook_to_plan(playbook: "PBPlaybook", card_id: int) -> Plan:
    """Convert a matched Playbook into a Plan with phased steps."""
    phase_buckets: dict[str, list[PlanStep]] = {}
    phase_order = ["Setup", "Execute", "Communicate"]

    for i, pb_step in enumerate(playbook.steps, start=1):
        phase_name = _classify_phase(pb_step.action.tool, pb_step.name)
        plan_step = PlanStep(
            index=i,
            summary=pb_step.name,
            detail=f"Playbook step from '{playbook.name}' v{playbook.version}",
            action_type=_infer_action_type(pb_step.action.tool),
            tool=pb_step.action.tool,
            params=dict(pb_step.action.params),
            param_sources={k: v.to_dict() for k, v in pb_step.action.param_sources.items()},
            draft_content=None,
            risk=_infer_risk(pb_step.action.tool),
            status="pending",
            output=None,
        )
        if phase_name not in phase_buckets:
            phase_buckets[phase_name] = []
        phase_buckets[phase_name].append(plan_step)

    # Build phases in canonical order, re-index steps globally
    phases = []
    global_index = 1
    for phase_name in phase_order:
        if phase_name in phase_buckets:
            for step in phase_buckets[phase_name]:
                step.index = global_index
                global_index += 1
            phases.append(Phase(name=phase_name, steps=phase_buckets[phase_name]))

    return Plan(
        id=f"plan-{card_id}-{int(time.time())}",
        card_id=card_id,
        source="playbook",
        playbook_id=playbook.id,
        confidence=CONFIDENCE_MAP.get(playbook.confidence, 0.5),
        phases=phases,
        status="pending",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        executed_at=None,
    )
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_converter.py -v
```

Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/converter.py bin/planner/test_converter.py
git commit -m "Add playbook-to-plan converter with phase classification and risk inference"
```

---

### Task 4: LLM planning prompter

**Files:**
- Create: `bin/planner/prompter.py`
- Create: `bin/planner/test_prompter.py`

**Step 1: Write the failing test**

Create `bin/planner/test_prompter.py`:

```python
import pytest
import json
from prompter import build_planning_prompt, parse_plan_response


def test_build_prompt_includes_card_context():
    card = {"id": 1, "source": "freshservice", "summary": "SSO setup for Okta", "context_notes": "Requester: jdoe"}
    tools_summary = [{"name": "jira", "capabilities": ["create_issue"]}]
    learned_context = "Always assign to kioja.kudumu"
    example_plans = []

    prompt = build_planning_prompt(card, tools_summary, learned_context, example_plans)
    assert "SSO setup for Okta" in prompt
    assert "freshservice" in prompt
    assert "Requester: jdoe" in prompt


def test_build_prompt_includes_tools():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    tools_summary = [
        {"name": "jira", "prefix": "mcp__mcp-atlassian__jira_", "capabilities": ["create_issue", "update_issue"]},
        {"name": "slack", "prefix": "mcp__slack__slack_", "capabilities": ["post_message"]},
    ]
    prompt = build_planning_prompt(card, tools_summary, "", [])
    assert "jira" in prompt
    assert "create_issue" in prompt
    assert "slack" in prompt


def test_build_prompt_includes_learned_context():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    prompt = build_planning_prompt(card, [], "Always use board 70 for Jira", [])
    assert "board 70" in prompt


def test_build_prompt_includes_examples():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    example = {"id": "plan-example", "card_id": 0, "source": "playbook", "phases": [{"name": "Setup", "steps": []}]}
    prompt = build_planning_prompt(card, [], "", [example])
    assert "plan-example" in prompt


def test_build_prompt_includes_feedback():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    prompt = build_planning_prompt(card, [], "", [], feedback="Step 3 should use Slack not email")
    assert "Step 3 should use Slack not email" in prompt


def test_build_prompt_includes_missing_tool_instruction():
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}
    prompt = build_planning_prompt(card, [], "", [])
    assert "__MISSING__" in prompt


def test_parse_plan_response_valid():
    response = json.dumps({
        "confidence": 0.8,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "Look up user", "detail": "Find user in system", "action_type": "mcp", "tool": "mcp__freshservice-mcp__get_requester_id", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low"},
            ]},
        ],
    })
    plan = parse_plan_response(response, card_id=42)
    assert plan is not None
    assert plan.card_id == 42
    assert plan.source == "llm"
    assert len(plan.phases) == 1
    assert plan.phases[0].steps[0].status == "pending"


def test_parse_plan_response_extracts_json_from_markdown():
    response = """Here's my analysis:

```json
{
    "confidence": 0.7,
    "phases": [
        {"name": "Execute", "steps": [
            {"index": 1, "summary": "Do thing", "detail": "Details", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": null, "risk": "low"}
        ]}
    ]
}
```

That should work!"""
    plan = parse_plan_response(response, card_id=99)
    assert plan is not None
    assert plan.confidence == 0.7


def test_parse_plan_response_returns_none_on_garbage():
    plan = parse_plan_response("this is not json at all", card_id=1)
    assert plan is None
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_prompter.py -v
```

Expected: FAIL — module `prompter` not found

**Step 3: Write the prompter**

Create `bin/planner/prompter.py`:

```python
"""Build Claude CLI prompts for LLM planning and parse responses."""

import json
import re
import time
from typing import Optional
from models import Plan, Phase, PlanStep

PLAN_SCHEMA = """{
  "confidence": 0.0-1.0,
  "phases": [
    {
      "name": "Setup" | "Execute" | "Communicate" | "Tooling Setup",
      "steps": [
        {
          "index": 1,
          "summary": "Human-readable step name",
          "detail": "Full description of what this step does",
          "action_type": "api" | "mcp" | "playwright",
          "tool": "exact_mcp_tool_name OR __MISSING__",
          "params": {"key": "value"},
          "param_sources": {},
          "draft_content": "editable text content if step produces messages/comments" | null,
          "risk": "low" | "medium" | "high",
          "missing_capability": {"description": "...", "domain": "...", "systems": ["..."]} | null
        }
      ]
    }
  ]
}"""


def build_planning_prompt(
    card: dict,
    tools_summary: list,
    learned_context: str,
    example_plans: list,
    feedback: Optional[str] = None,
) -> str:
    sections = []

    sections.append(
        "You are eng-buddy's planning engine. Given a card from the dashboard, "
        "produce a step-by-step execution plan using the available tools.\n"
    )

    # Card context
    sections.append("## Card\n")
    sections.append(f"- **ID**: {card.get('id')}")
    sections.append(f"- **Source**: {card.get('source')}")
    sections.append(f"- **Summary**: {card.get('summary')}")
    if card.get("context_notes"):
        sections.append(f"- **Context**: {card.get('context_notes')}")
    sections.append("")

    # Available tools
    if tools_summary:
        sections.append("## Available Tools\n")
        for tool in tools_summary:
            caps = ", ".join(tool.get("capabilities", []))
            prefix = tool.get("prefix", "")
            sections.append(f"- **{tool['name']}** (prefix: `{prefix}`): {caps}")
        sections.append("")

    # Learned context
    if learned_context:
        sections.append("## Learned Context\n")
        sections.append(learned_context)
        sections.append("")

    # Example plans
    if example_plans:
        sections.append("## Example Plans\n")
        for ex in example_plans[:3]:
            sections.append(f"```json\n{json.dumps(ex, indent=2)}\n```\n")

    # Feedback from rejected plan
    if feedback:
        sections.append("## Previous Plan Feedback\n")
        sections.append(f"The previous plan was rejected because: {feedback}\n")

    # Instructions
    sections.append("## Instructions\n")
    sections.append("- Group steps into phases: \"Setup\" (data gathering, lookups), \"Execute\" (main actions, ticket creation, admin changes), \"Communicate\" (notifications, replies, status updates)")
    sections.append("- Each step MUST use an exact tool name from the Available Tools list (use the prefix + capability name)")
    sections.append("- If a step requires a tool not in the Available Tools list, set tool to \"__MISSING__\" and include a \"missing_capability\" object with description, domain, and systems fields")
    sections.append("- Mark steps with draft_content when they produce user-visible text (email bodies, Slack messages, Jira comments)")
    sections.append("- Assess risk per step: \"low\" (read/create), \"medium\" (send/update), \"high\" (delete/access changes/admin)")
    sections.append("- Self-assess confidence 0.0-1.0 based on how well you understand the card's intent")
    sections.append("")

    # Output format
    sections.append("## Output Format\n")
    sections.append("Respond with ONLY valid JSON matching this schema:\n")
    sections.append(f"```json\n{PLAN_SCHEMA}\n```")

    return "\n".join(sections)


def parse_plan_response(response: str, card_id: int) -> Optional[Plan]:
    """Parse LLM response into a Plan object. Handles raw JSON or markdown-wrapped JSON."""
    json_str = None

    # Try extracting from markdown code block first
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Try parsing the whole response as JSON
        json_str = response.strip()

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    # Ensure all steps have required defaults
    for phase in data.get("phases", []):
        for step in phase.get("steps", []):
            step.setdefault("status", "pending")
            step.setdefault("output", None)
            step.setdefault("param_sources", {})
            step.setdefault("params", {})

    return Plan(
        id=f"plan-{card_id}-{int(time.time())}",
        card_id=card_id,
        source="llm",
        playbook_id=None,
        confidence=data.get("confidence", 0.5),
        phases=[Phase.from_dict(p) for p in data.get("phases", [])],
        status="pending",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        executed_at=None,
    )
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_prompter.py -v
```

Expected: 9 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/prompter.py bin/planner/test_prompter.py
git commit -m "Add LLM planning prompter with prompt builder and response parser"
```

---

### Task 5: Core planner (match → plan → store orchestration)

**Files:**
- Create: `bin/planner/planner.py`
- Create: `bin/planner/test_planner.py`

**Step 1: Write the failing test**

Create `bin/planner/test_planner.py`:

```python
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan
from store import PlanStore
from planner import CardPlanner


@pytest.fixture
def planner(tmp_path):
    plans_dir = tmp_path / "plans"
    db_path = tmp_path / "inbox.db"
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    # Create minimal registry
    (registry_dir / "_registry.yml").write_text("tools: {}")
    return CardPlanner(
        plans_dir=str(plans_dir),
        db_path=str(db_path),
        playbooks_dir=str(playbooks_dir),
        registry_dir=str(registry_dir),
    )


def test_plan_card_with_no_playbook_match(planner):
    """When no playbook matches, should attempt LLM planning."""
    card = {"id": 1, "source": "freshservice", "summary": "New SSO request", "context_notes": ""}

    mock_response = json.dumps({
        "confidence": 0.7,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "Look up ticket", "detail": "Get ticket details", "action_type": "mcp",
                 "tool": "mcp__freshservice-mcp__get_ticket_by_id", "params": {}, "risk": "low"},
            ]},
        ],
    })

    with patch("planner._call_claude_cli", return_value=mock_response):
        plan = planner.plan_card(card)

    assert plan is not None
    assert plan.source == "llm"
    assert plan.card_id == 1
    assert len(plan.all_steps()) == 1
    # Plan should be persisted
    assert planner.store.has_plan(1)


def test_plan_card_with_playbook_match(planner):
    """When a playbook matches, should convert it to a plan without LLM."""
    # Create a matching playbook
    from models import Playbook as PBPlaybook
    pb = PBPlaybook.from_dict({
        "id": "test-pb",
        "name": "Test",
        "version": 1,
        "confidence": "high",
        "trigger_patterns": [{"keywords": ["SSO"], "source": ["freshservice"]}],
        "created_from": "session",
        "executions": 5,
        "steps": [
            {"id": 1, "name": "Do thing", "action": {"tool": "mcp__jira__create_issue", "params": {}},
             "auth_required": False, "human_required": False},
        ],
    })
    from manager import PlaybookManager
    mgr = PlaybookManager(planner.playbooks_dir)
    mgr.save(pb)

    # Re-create planner so it picks up the playbook
    planner2 = CardPlanner(
        plans_dir=planner.store.plans_dir,
        db_path=str(planner.store.db_path),
        playbooks_dir=planner.playbooks_dir,
        registry_dir=planner.registry_dir,
    )

    card = {"id": 2, "source": "freshservice", "summary": "SSO setup for Linear", "context_notes": ""}
    plan = planner2.plan_card(card)

    assert plan is not None
    assert plan.source == "playbook"
    assert plan.playbook_id == "test-pb"


def test_plan_card_deduplication(planner):
    """Should not re-plan a card that already has a plan."""
    card = {"id": 1, "source": "gmail", "summary": "test", "context_notes": ""}

    mock_response = json.dumps({
        "confidence": 0.7,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "risk": "low"},
        ]}],
    })

    with patch("planner._call_claude_cli", return_value=mock_response):
        plan1 = planner.plan_card(card)
        plan2 = planner.plan_card(card)

    # Second call should return existing plan, not create a new one
    assert plan2.id == plan1.id


def test_plan_card_detects_missing_tools(planner):
    """Plans with __MISSING__ tools should be flagged."""
    card = {"id": 3, "source": "freshservice", "summary": "Okta admin task", "context_notes": ""}

    mock_response = json.dumps({
        "confidence": 0.5,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Access Okta", "detail": "Need Okta admin", "action_type": "mcp",
             "tool": "__MISSING__", "params": {}, "risk": "high",
             "missing_capability": {"description": "Okta admin API", "domain": "identity", "systems": ["Okta"]}},
        ]}],
    })

    with patch("planner._call_claude_cli", return_value=mock_response):
        plan = planner.plan_card(card)

    assert plan is not None
    assert plan.has_missing_tools()
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_planner.py -v
```

Expected: FAIL — module `planner` not found

**Step 3: Write the planner**

Create `bin/planner/planner.py`:

```python
"""Core planner — orchestrates playbook matching, LLM planning, and storage."""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan
from store import PlanStore
from converter import playbook_to_plan
from prompter import build_planning_prompt, parse_plan_response

# Lazy imports for playbook engine
_pb_manager = None
_tool_registry = None


def _call_claude_cli(prompt: str) -> str:
    """Shell out to Claude CLI for LLM planning."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        result = subprocess.run(
            ["claude", "--print", "-p", f"$(cat {prompt_file})"],
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return ""
    finally:
        Path(prompt_file).unlink(missing_ok=True)


def _get_tools_summary(registry) -> list:
    """Build a concise tools summary for the LLM prompt."""
    summary = []
    for name, info in registry.tools.items():
        summary.append({
            "name": name,
            "prefix": info.get("prefix", ""),
            "capabilities": info.get("capabilities", []),
            "domains": info.get("domains", []),
        })
    return summary


def _get_learned_context() -> str:
    """Get learned context from brain.py."""
    brain_path = Path(__file__).parent.parent / "brain.py"
    if not brain_path.exists():
        return ""
    try:
        result = subprocess.run(
            [sys.executable, str(brain_path), "--build-context"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_example_plans(pb_manager) -> list:
    """Get top 3 promoted playbooks as example plans for few-shot prompting."""
    playbooks = pb_manager.list_playbooks()
    playbooks.sort(key=lambda p: p.executions, reverse=True)
    examples = []
    for pb in playbooks[:3]:
        plan = playbook_to_plan(pb, card_id=0)
        examples.append(plan.to_dict())
    return examples


class CardPlanner:
    def __init__(self, plans_dir: str, db_path: str, playbooks_dir: str, registry_dir: str):
        self.store = PlanStore(plans_dir, db_path)
        self.playbooks_dir = playbooks_dir
        self.registry_dir = registry_dir

    def _get_pb_manager(self):
        from manager import PlaybookManager
        return PlaybookManager(self.playbooks_dir)

    def _get_registry(self):
        from registry import ToolRegistry
        return ToolRegistry(self.registry_dir)

    def plan_card(self, card: dict, feedback: Optional[str] = None) -> Optional[Plan]:
        """Generate a plan for a card. Returns existing plan if one exists (dedup)."""
        card_id = card["id"]

        # Deduplication: return existing plan unless re-planning with feedback
        if not feedback and self.store.has_plan(card_id):
            return self.store.get(card_id)

        # Try playbook matching first
        pb_manager = self._get_pb_manager()
        matches = pb_manager.match_ticket(
            ticket_type=card.get("classification", ""),
            text=card.get("summary", ""),
            source=card.get("source", ""),
        )

        if matches:
            # Use best match (sorted by execution count)
            plan = playbook_to_plan(matches[0], card_id=card_id)
            self.store.save(plan)
            return plan

        # No playbook match — fall back to LLM planning
        registry = self._get_registry()
        tools_summary = _get_tools_summary(registry)
        learned_context = _get_learned_context()
        example_plans = _get_example_plans(pb_manager)

        prompt = build_planning_prompt(
            card=card,
            tools_summary=tools_summary,
            learned_context=learned_context,
            example_plans=example_plans,
            feedback=feedback,
        )

        response = _call_claude_cli(prompt)
        if not response:
            return None

        plan = parse_plan_response(response, card_id=card_id)
        if plan:
            self.store.save(plan)
        return plan

    def regenerate(self, card_id: int, feedback: Optional[str] = None) -> Optional[Plan]:
        """Delete existing plan and re-plan with optional feedback."""
        self.store.delete(card_id)
        # Need the card data — read from inbox.db
        import sqlite3
        conn = sqlite3.connect(str(self.store.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        card = dict(row)
        return self.plan_card(card, feedback=feedback)
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_planner.py -v
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/planner.py bin/planner/test_planner.py
git commit -m "Add core CardPlanner with playbook matching, LLM fallback, and deduplication"
```

---

### Task 6: Background worker daemon

**Files:**
- Create: `bin/planner/worker.py`
- Create: `bin/planner/test_worker.py`

**Step 1: Write the failing test**

Create `bin/planner/test_worker.py`:

```python
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from worker import PlannerWorker


@pytest.fixture
def worker_env(tmp_path):
    db_path = tmp_path / "inbox.db"
    plans_dir = tmp_path / "plans"
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "_registry.yml").write_text("tools: {}")
    lock_path = tmp_path / "planner.lock"

    # Create cards table
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, source TEXT, status TEXT, summary TEXT, context_notes TEXT, timestamp TEXT, classification TEXT, section TEXT)")
    conn.commit()
    conn.close()

    return {
        "db_path": str(db_path),
        "plans_dir": str(plans_dir),
        "playbooks_dir": str(playbooks_dir),
        "registry_dir": str(registry_dir),
        "lock_path": str(lock_path),
    }


def test_worker_processes_unplanned_cards(worker_env):
    # Insert a pending card
    conn = sqlite3.connect(worker_env["db_path"])
    conn.execute("INSERT INTO cards VALUES (1, 'gmail', 'pending', 'Budget review', '', '2026-03-10', 'high', '')")
    conn.commit()
    conn.close()

    worker = PlannerWorker(**worker_env)

    with patch.object(worker.planner, "plan_card", return_value=MagicMock()) as mock_plan:
        processed = worker.process_once()

    assert processed == 1
    mock_plan.assert_called_once()
    call_card = mock_plan.call_args[0][0]
    assert call_card["id"] == 1


def test_worker_skips_already_planned(worker_env):
    conn = sqlite3.connect(worker_env["db_path"])
    conn.execute("INSERT INTO cards VALUES (1, 'gmail', 'pending', 'Budget review', '', '2026-03-10', 'high', '')")
    conn.commit()
    conn.close()

    worker = PlannerWorker(**worker_env)

    # First run plans the card
    with patch.object(worker.planner, "plan_card", return_value=MagicMock()):
        worker.process_once()

    # Mark as having a plan
    worker.planner.store.save(MagicMock(
        card_id=1, id="plan-1-0", source="llm", status="pending",
        created_at="2026-03-10", to_dict=lambda: {
            "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
            "confidence": 0.7, "phases": [], "status": "pending",
            "created_at": "2026-03-10", "executed_at": None,
        },
        save=lambda path: None,
    ))

    # Second run should find no cards needing plans
    with patch.object(worker.planner, "plan_card") as mock_plan:
        processed = worker.process_once()

    assert processed == 0


def test_worker_respects_lock(worker_env):
    # Create lock file
    Path(worker_env["lock_path"]).write_text("locked")

    worker = PlannerWorker(**worker_env)
    assert worker.acquire_lock() is False


def test_worker_acquires_and_releases_lock(worker_env):
    worker = PlannerWorker(**worker_env)
    assert worker.acquire_lock() is True
    assert Path(worker_env["lock_path"]).exists()
    worker.release_lock()
    assert not Path(worker_env["lock_path"]).exists()
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_worker.py -v
```

Expected: FAIL — module `worker` not found

**Step 3: Write the worker**

Create `bin/planner/worker.py`:

```python
"""Background worker daemon — polls for unplanned cards and generates plans."""

import time
import logging
import os
import sys
from pathlib import Path

from planner import CardPlanner

logger = logging.getLogger("planner-worker")

DEFAULT_POLL_INTERVAL = 30  # seconds
NOTIFY_URL = "http://localhost:7777/api/cache-invalidate"


class PlannerWorker:
    def __init__(self, db_path: str, plans_dir: str, playbooks_dir: str, registry_dir: str, lock_path: str):
        self.planner = CardPlanner(
            plans_dir=plans_dir,
            db_path=db_path,
            playbooks_dir=playbooks_dir,
            registry_dir=registry_dir,
        )
        self.lock_path = Path(lock_path)

    def acquire_lock(self) -> bool:
        if self.lock_path.exists():
            # Check if lock is stale (older than 5 minutes)
            try:
                age = time.time() - self.lock_path.stat().st_mtime
                if age < 300:
                    return False
            except OSError:
                pass
        try:
            self.lock_path.write_text(str(os.getpid()))
            return True
        except OSError:
            return False

    def release_lock(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def process_once(self) -> int:
        """Process all unplanned pending cards. Returns count of cards planned."""
        cards = self.planner.store.cards_needing_plans()
        planned = 0
        for card in cards:
            try:
                plan = self.planner.plan_card(card)
                if plan:
                    planned += 1
                    logger.info(f"Planned card {card['id']}: {plan.source} ({len(plan.all_steps())} steps)")
                    self._notify_dashboard(card["source"])
            except Exception as e:
                logger.error(f"Failed to plan card {card['id']}: {e}")
        return planned

    def _notify_dashboard(self, source: str) -> None:
        """Notify dashboard SSE that plans are ready."""
        try:
            import urllib.request
            import json
            data = json.dumps({"source": source}).encode()
            req = urllib.request.Request(
                NOTIFY_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Dashboard might not be running

    def run(self, interval: int = DEFAULT_POLL_INTERVAL) -> None:
        """Main loop — poll and plan."""
        logger.info(f"Planner worker starting (interval={interval}s)")
        while True:
            if self.acquire_lock():
                try:
                    self.process_once()
                finally:
                    self.release_lock()
            else:
                logger.debug("Lock held by another process, skipping cycle")
            time.sleep(interval)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="eng-buddy planner worker")
    parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--once", action="store_true", help="Process once and exit")
    args = parser.parse_args()

    base = Path.home() / ".claude" / "eng-buddy"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(str(base / "planner.log")),
            logging.StreamHandler(),
        ],
    )

    worker = PlannerWorker(
        db_path=str(base / "inbox.db"),
        plans_dir=str(base / "plans"),
        playbooks_dir=str(base / "playbooks"),
        registry_dir=str(Path(__file__).parent.parent / "playbook_engine" / ".." / ".." / "playbooks" / "tool-registry"),
        lock_path=str(base / "planner.lock"),
    )

    if args.once:
        worker.process_once()
    else:
        worker.run(interval=args.interval)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_worker.py -v
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/worker.py bin/planner/test_worker.py
git commit -m "Add planner background worker with lock, polling, and dashboard notification"
```

---

### Task 7: Dashboard API routes for plans

**Files:**
- Modify: `dashboard/server.py` (add 5 new routes + 2 SSE events)
- Create: `dashboard/tests/test_plan_api.py`

**Step 1: Write the failing test**

Create `dashboard/tests/test_plan_api.py`:

```python
import pytest
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add bin/planner to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bin" / "planner"))

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database and plans directory."""
    db_path = tmp_path / "inbox.db"
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "_registry.yml").write_text("tools: {}")

    # Create cards table and insert test card
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, source TEXT, status TEXT, summary TEXT, context_notes TEXT, timestamp TEXT, classification TEXT, section TEXT)")
    conn.execute("INSERT INTO cards VALUES (1, 'freshservice', 'pending', 'SSO for Okta', 'req: jdoe', '2026-03-10', 'high', '')")
    conn.commit()
    conn.close()

    # Patch paths in server module
    with patch("dashboard.server.PLANS_DIR", str(plans_dir)), \
         patch("dashboard.server.DB_PATH", str(db_path)), \
         patch("dashboard.server.PLAYBOOKS_DIR", str(playbooks_dir)), \
         patch("dashboard.server.REGISTRY_DIR", str(registry_dir)):
        from dashboard.server import app
        yield TestClient(app)


def test_get_plan_404_when_none(client):
    response = client.get("/api/cards/1/plan")
    assert response.status_code == 404


def test_get_plan_returns_plan(client, tmp_path):
    # Save a plan directly
    plan_data = {
        "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
        "confidence": 0.8, "status": "pending", "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
        "phases": [{"name": "Setup", "steps": [
            {"index": 1, "summary": "Look up ticket", "detail": "Get details", "action_type": "mcp",
             "tool": "mcp__freshservice-mcp__get_ticket_by_id", "params": {}, "param_sources": {},
             "draft_content": None, "risk": "low", "status": "pending", "output": None},
        ]}],
    }
    plans_dir = tmp_path / "plans"
    (plans_dir / "1.json").write_text(json.dumps(plan_data))

    response = client.get("/api/cards/1/plan")
    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["card_id"] == 1


def test_update_step_approve(client, tmp_path):
    # Save a plan
    plan_data = {
        "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
        "confidence": 0.8, "status": "pending", "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
        "phases": [{"name": "Setup", "steps": [
            {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp",
             "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None,
             "risk": "low", "status": "pending", "output": None},
        ]}],
    }
    plans_dir = tmp_path / "plans"
    (plans_dir / "1.json").write_text(json.dumps(plan_data))

    response = client.patch("/api/cards/1/plan/steps/1", json={"status": "approved"})
    assert response.status_code == 200
    assert response.json()["step"]["status"] == "approved"


def test_update_step_edit_draft(client, tmp_path):
    plan_data = {
        "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
        "confidence": 0.8, "status": "pending", "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
        "phases": [{"name": "Communicate", "steps": [
            {"index": 1, "summary": "Reply", "detail": "", "action_type": "mcp",
             "tool": "t1", "params": {}, "param_sources": {},
             "draft_content": "Original draft", "risk": "medium",
             "status": "pending", "output": None},
        ]}],
    }
    plans_dir = tmp_path / "plans"
    (plans_dir / "1.json").write_text(json.dumps(plan_data))

    response = client.patch("/api/cards/1/plan/steps/1", json={
        "status": "approved",
        "draft_content": "Edited draft text",
    })
    assert response.status_code == 200
    step = response.json()["step"]
    assert step["status"] == "edited"
    assert step["draft_content"] == "Edited draft text"


def test_approve_remaining(client, tmp_path):
    plan_data = {
        "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
        "confidence": 0.8, "status": "pending", "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
        "phases": [{"name": "Setup", "steps": [
            {"index": 1, "summary": "s1", "detail": "", "action_type": "mcp", "tool": "t1", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "approved", "output": None},
            {"index": 2, "summary": "s2", "detail": "", "action_type": "mcp", "tool": "t2", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
            {"index": 3, "summary": "s3", "detail": "", "action_type": "mcp", "tool": "t3", "params": {}, "param_sources": {}, "draft_content": None, "risk": "low", "status": "pending", "output": None},
        ]}],
    }
    plans_dir = tmp_path / "plans"
    (plans_dir / "1.json").write_text(json.dumps(plan_data))

    response = client.post("/api/cards/1/plan/approve-remaining", json={"from_index": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["approved_count"] == 2


def test_regenerate(client, tmp_path):
    plans_dir = tmp_path / "plans"
    plan_data = {
        "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
        "confidence": 0.8, "status": "pending", "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None, "phases": [],
    }
    (plans_dir / "1.json").write_text(json.dumps(plan_data))

    response = client.post("/api/cards/1/plan/regenerate", json={"feedback": "Wrong tools"})
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    # Old plan should be deleted
    assert not (plans_dir / "1.json").exists()
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy
python -m pytest dashboard/tests/test_plan_api.py -v
```

Expected: FAIL — routes don't exist yet

**Step 3: Add plan API routes to server.py**

Read the existing server.py to find the right insertion point (after playbook routes), then add these routes. The exact insertion point and import adjustments will depend on the current state of server.py. Add the following block after the existing `/api/playbooks` routes:

```python
# ── Plan API ─────────────────────────────────────────────────────────────
# These routes support the step-by-step plan approval flow.

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent / "bin" / "planner"))

from store import PlanStore as _PlanStore
from planner import CardPlanner as _CardPlanner

# Plan infrastructure paths
PLANS_DIR = str(Path.home() / ".claude" / "eng-buddy" / "plans")
PLAYBOOKS_DIR = str(Path.home() / ".claude" / "eng-buddy" / "playbooks")
REGISTRY_DIR = str(Path(__file__).parent.parent / "playbooks" / "tool-registry")

def _get_plan_store():
    return _PlanStore(PLANS_DIR, DB_PATH)

def _get_card_planner():
    return _CardPlanner(
        plans_dir=PLANS_DIR,
        db_path=DB_PATH,
        playbooks_dir=PLAYBOOKS_DIR,
        registry_dir=REGISTRY_DIR,
    )


@app.get("/api/cards/{card_id}/plan")
async def get_card_plan(card_id: int):
    store = _get_plan_store()
    plan = store.get(card_id)
    if not plan:
        raise HTTPException(404, "No plan for this card")
    return {"plan": plan.to_dict()}


@app.patch("/api/cards/{card_id}/plan/steps/{step_index}")
async def update_plan_step(card_id: int, step_index: int, body: dict):
    store = _get_plan_store()
    plan = store.get(card_id)
    if not plan:
        raise HTTPException(404, "No plan for this card")

    step = plan.get_step(step_index)
    if not step:
        raise HTTPException(404, f"Step {step_index} not found")

    new_status = body.get("status", step.status)
    new_draft = body.get("draft_content")

    # If draft_content changed, mark as edited
    if new_draft is not None and new_draft != step.draft_content:
        step.draft_content = new_draft
        step.status = "edited"
    else:
        step.status = new_status

    store.save(plan)
    _stale_sources.add("plans")
    return {"step": step.to_dict()}


@app.post("/api/cards/{card_id}/plan/approve-remaining")
async def approve_remaining_steps(card_id: int, body: dict):
    store = _get_plan_store()
    plan = store.get(card_id)
    if not plan:
        raise HTTPException(404, "No plan for this card")

    from_index = body.get("from_index", 1)
    approved = 0
    for step in plan.all_steps():
        if step.index >= from_index and step.status == "pending":
            step.status = "approved"
            approved += 1

    store.save(plan)
    _stale_sources.add("plans")
    return {"approved_count": approved, "plan": plan.to_dict()}


@app.post("/api/cards/{card_id}/plan/execute")
async def execute_plan(card_id: int):
    store = _get_plan_store()
    plan = store.get(card_id)
    if not plan:
        raise HTTPException(404, "No plan for this card")

    # Build execution prompt from approved/edited steps
    lines = [f"Execute this plan for card #{card_id}. Follow each step exactly.\n"]
    step_count = 0
    skipped = []
    for phase in plan.phases:
        lines.append(f"\n## Phase: {phase.name}\n")
        for step in phase.steps:
            if step.status == "skipped":
                skipped.append(step.index)
                lines.append(f"Step {step.index}: [SKIPPED] {step.summary}")
                continue
            if step.status not in ("approved", "edited"):
                skipped.append(step.index)
                continue
            step_count += 1
            lines.append(f"Step {step.index}: {step.summary}")
            lines.append(f"  Tool: {step.tool}")
            if step.params:
                lines.append(f"  Params: {json.dumps(step.params)}")
            if step.draft_content:
                lines.append(f"  Content: {step.draft_content}")
            lines.append("")

    prompt_text = "\n".join(lines)

    # Write prompt and launch in Terminal (same pattern as playbook execute)
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(prompt_text)
        prompt_file = f.name

    plan.status = "executing"
    store.save(plan)

    cmd = f'claude --print -p "$(cat {prompt_file})"'
    script = f'''tell application "Terminal"
        activate
        do script "{cmd}"
    end tell'''
    subprocess.Popen(["osascript", "-e", script])

    return {"status": "dispatched", "steps": step_count, "skipped": skipped}


@app.post("/api/cards/{card_id}/plan/regenerate")
async def regenerate_plan(card_id: int, body: dict):
    store = _get_plan_store()
    store.delete(card_id)
    # Queue for re-planning (worker will pick it up, or we could plan inline)
    _stale_sources.add("plans")
    return {"status": "queued", "feedback": body.get("feedback")}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy
python -m pytest dashboard/tests/test_plan_api.py -v
```

Expected: 6 tests PASS

Note: The test fixture setup may need adjustment based on how server.py imports are structured. The test should mock the plan store paths to use tmp_path. If imports fail, the executing engineer should adjust the fixture to properly patch the module-level path constants.

**Step 5: Commit**

```bash
git add dashboard/server.py dashboard/tests/test_plan_api.py
git commit -m "Add plan API routes: get, update step, approve remaining, execute, regenerate"
```

---

### Task 8: Plan-to-playbook learning loop

**Files:**
- Create: `bin/planner/learner.py`
- Create: `bin/planner/test_learner.py`

**Step 1: Write the failing test**

Create `bin/planner/test_learner.py`:

```python
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan, Phase, PlanStep
from learner import plan_to_draft_playbook


def _make_completed_plan() -> Plan:
    return Plan.from_dict({
        "id": "plan-42-0",
        "card_id": 42,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.8,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "Look up requester", "detail": "Find in Freshservice",
                 "action_type": "mcp", "tool": "mcp__freshservice-mcp__get_requester_id",
                 "params": {"email": "jdoe@company.com"}, "param_sources": {},
                 "draft_content": None, "risk": "low", "status": "done", "output": "Found: req-123"},
            ]},
            {"name": "Execute", "steps": [
                {"index": 2, "summary": "Create Jira ticket", "detail": "Under SSO epic",
                 "action_type": "mcp", "tool": "mcp__mcp-atlassian__jira_create_issue",
                 "params": {"project": "ITWORK2", "summary": "[SSO] Okta"},
                 "param_sources": {}, "draft_content": None, "risk": "low",
                 "status": "done", "output": "Created ITWORK2-9999"},
            ]},
            {"name": "Communicate", "steps": [
                {"index": 3, "summary": "Notify requester", "detail": "Send reply",
                 "action_type": "mcp", "tool": "mcp__freshservice-mcp__send_ticket_reply",
                 "params": {}, "param_sources": {},
                 "draft_content": "Hi, I've created ticket ITWORK2-9999 for your SSO request.",
                 "risk": "medium", "status": "done", "output": "Sent"},
            ]},
        ],
        "status": "completed",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": "2026-03-10T09:05:00Z",
    })


def test_converts_plan_to_draft_playbook():
    plan = _make_completed_plan()
    card = {"id": 42, "source": "freshservice", "summary": "SSO setup for Okta", "classification": "Service Request"}

    pb = plan_to_draft_playbook(plan, card)
    assert pb.id.startswith("auto-")
    assert pb.confidence == "low"
    assert pb.created_from == "plan-learning"
    assert len(pb.steps) == 3


def test_preserves_tool_bindings():
    plan = _make_completed_plan()
    card = {"id": 42, "source": "freshservice", "summary": "SSO setup for Okta", "classification": "Service Request"}

    pb = plan_to_draft_playbook(plan, card)
    assert pb.steps[0].action.tool == "mcp__freshservice-mcp__get_requester_id"
    assert pb.steps[1].action.tool == "mcp__mcp-atlassian__jira_create_issue"
    assert pb.steps[1].action.params.get("project") == "ITWORK2"


def test_extracts_trigger_patterns():
    plan = _make_completed_plan()
    card = {"id": 42, "source": "freshservice", "summary": "SSO setup for Okta", "classification": "Service Request"}

    pb = plan_to_draft_playbook(plan, card)
    assert len(pb.trigger_patterns) >= 1
    tp = pb.trigger_patterns[0]
    assert "freshservice" in tp.source
    assert any("sso" in kw.lower() for kw in tp.keywords)


def test_skips_skipped_steps():
    plan = _make_completed_plan()
    plan.phases[0].steps[0].status = "skipped"
    card = {"id": 42, "source": "freshservice", "summary": "SSO for Okta", "classification": ""}

    pb = plan_to_draft_playbook(plan, card)
    assert len(pb.steps) == 2  # skipped step excluded
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_learner.py -v
```

Expected: FAIL — module `learner` not found

**Step 3: Write the learner**

Create `bin/planner/learner.py`:

```python
"""Learning loop — convert completed LLM plans into draft playbooks."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan
from models import Playbook, PlaybookStep, ActionBinding, TriggerPattern, ParamSource

# Known IT domain keywords for trigger pattern extraction
KNOWN_KEYWORDS = [
    "sso", "saml", "scim", "oidc", "onboarding", "offboarding",
    "certificate", "renewal", "provisioning", "deprovisioning",
    "access", "permissions", "mfa", "2fa", "password", "reset",
    "account", "license", "audit", "compliance", "okta", "azure",
    "google", "slack", "jira", "freshservice",
]


def _extract_keywords(text: str) -> list:
    """Extract IT domain keywords from text."""
    text_lower = text.lower()
    return [kw for kw in KNOWN_KEYWORDS if kw in text_lower]


def _slugify(text: str) -> str:
    """Convert text to a valid playbook ID slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    slug = slug.strip("-")[:50]
    return f"auto-{slug}" if slug else "auto-unnamed"


def plan_to_draft_playbook(plan: Plan, card: dict) -> Playbook:
    """Convert a completed Plan into a draft Playbook for future matching."""
    # Extract trigger patterns from card metadata
    keywords = _extract_keywords(card.get("summary", ""))
    source_list = [card.get("source", "")] if card.get("source") else []
    trigger = TriggerPattern(
        ticket_type=card.get("classification", ""),
        keywords=keywords,
        source=source_list,
    )

    # Convert plan steps to playbook steps, skipping skipped/failed
    pb_steps = []
    step_id = 1
    for phase in plan.phases:
        for step in phase.steps:
            if step.status in ("skipped", "failed"):
                continue
            action = ActionBinding(
                tool=step.tool,
                params=dict(step.params),
                param_sources={
                    k: ParamSource.from_dict(v)
                    for k, v in step.param_sources.items()
                },
            )
            pb_step = PlaybookStep(
                id=step_id,
                name=step.summary,
                action=action,
                auth_required=step.action_type == "playwright",
                auth_method="stored_session" if step.action_type == "playwright" else None,
                human_required=False,
                optional=False,
            )
            pb_steps.append(pb_step)
            step_id += 1

    playbook_id = _slugify(card.get("summary", "unnamed"))

    return Playbook(
        id=playbook_id,
        name=card.get("summary", "Auto-generated playbook"),
        version=1,
        confidence="low",
        trigger_patterns=[trigger],
        created_from="plan-learning",
        executions=0,
        steps=pb_steps,
    )
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_learner.py -v
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/learner.py bin/planner/test_learner.py
git commit -m "Add plan-to-playbook learning loop for auto-generating draft playbooks"
```

---

### Task 9: Expansion agent prompter

**Files:**
- Create: `bin/planner/expander.py`
- Create: `bin/planner/test_expander.py`

**Step 1: Write the failing test**

Create `bin/planner/test_expander.py`:

```python
import pytest
import json
from models import Plan, Phase, PlanStep
from expander import build_expansion_prompt, parse_expansion_response, inject_tooling_phase


def _make_plan_with_missing() -> Plan:
    return Plan.from_dict({
        "id": "plan-1-0",
        "card_id": 1,
        "source": "llm",
        "playbook_id": None,
        "confidence": 0.5,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Access Okta admin", "detail": "Need Okta admin console",
             "action_type": "mcp", "tool": "__MISSING__", "params": {}, "param_sources": {},
             "draft_content": None, "risk": "high", "status": "pending", "output": None,
             "missing_capability": {"description": "Okta admin API", "domain": "identity", "systems": ["Okta"]}},
            {"index": 2, "summary": "Update ticket", "detail": "", "action_type": "mcp",
             "tool": "mcp__freshservice-mcp__update_ticket", "params": {}, "param_sources": {},
             "draft_content": None, "risk": "low", "status": "pending", "output": None},
        ]}],
        "status": "pending",
        "created_at": "2026-03-10T09:00:00Z",
        "executed_at": None,
    })


def test_build_expansion_prompt():
    plan = _make_plan_with_missing()
    prompt = build_expansion_prompt(plan)
    assert "Okta" in prompt
    assert "identity" in prompt
    assert "__MISSING__" in prompt


def test_parse_expansion_mcp_install():
    response = json.dumps({
        "expansions": [
            {
                "for_step_index": 1,
                "solution_type": "mcp_server",
                "package": "@okta/mcp-server",
                "config": {"api_key": "env:OKTA_API_KEY"},
                "registry_entry": {
                    "name": "okta",
                    "prefix": "mcp__okta__",
                    "capabilities": ["list_users", "get_user", "assign_app"],
                    "domains": ["identity_management"],
                },
                "new_tool_name": "mcp__okta__assign_app",
            }
        ]
    })
    expansions = parse_expansion_response(response)
    assert len(expansions) == 1
    assert expansions[0]["solution_type"] == "mcp_server"
    assert expansions[0]["package"] == "@okta/mcp-server"


def test_parse_expansion_playwright():
    response = json.dumps({
        "expansions": [
            {
                "for_step_index": 1,
                "solution_type": "playwright",
                "url": "https://admin.okta.com/admin/apps",
                "new_tool_name": "mcp__playwright__browser_navigate",
            }
        ]
    })
    expansions = parse_expansion_response(response)
    assert expansions[0]["solution_type"] == "playwright"


def test_parse_expansion_returns_empty_on_garbage():
    expansions = parse_expansion_response("not json")
    assert expansions == []


def test_inject_tooling_phase():
    plan = _make_plan_with_missing()
    expansions = [{
        "for_step_index": 1,
        "solution_type": "mcp_server",
        "package": "@okta/mcp-server",
        "config": {"api_key": "env:OKTA_API_KEY"},
        "registry_entry": {"name": "okta", "prefix": "mcp__okta__"},
        "new_tool_name": "mcp__okta__assign_app",
    }]

    updated = inject_tooling_phase(plan, expansions)
    assert updated.phases[0].name == "Tooling Setup"
    # All tooling steps should be high risk
    for step in updated.phases[0].steps:
        assert step.risk == "high"
    # Original __MISSING__ step should now have the new tool
    execute_phase = [p for p in updated.phases if p.name == "Execute"][0]
    assert execute_phase.steps[0].tool == "mcp__okta__assign_app"
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_expander.py -v
```

Expected: FAIL — module `expander` not found

**Step 3: Write the expander**

Create `bin/planner/expander.py`:

```python
"""Capability expansion agent — discovers and proposes new tools for missing capabilities."""

import json
import re
from typing import Optional
from models import Plan, Phase, PlanStep


def build_expansion_prompt(plan: Plan) -> str:
    """Build a prompt for the expansion agent to research missing tools."""
    missing = []
    for step in plan.all_steps():
        if step.tool == "__MISSING__" and step.missing_capability:
            missing.append({
                "step_index": step.index,
                "summary": step.summary,
                "capability": step.missing_capability,
            })

    sections = [
        "You are eng-buddy's capability expansion agent. The planner needs tools that don't exist in our registry yet.\n",
        "## Missing Capabilities\n",
    ]

    for m in missing:
        cap = m["capability"]
        sections.append(f"- **Step {m['step_index']}**: {m['summary']}")
        sections.append(f"  Description: {cap.get('description', 'Unknown')}")
        sections.append(f"  Domain: {cap.get('domain', 'Unknown')}")
        sections.append(f"  Systems: {', '.join(cap.get('systems', []))}")
        sections.append("")

    sections.append("## Instructions\n")
    sections.append("For each missing capability, research and propose ONE of these solutions:")
    sections.append("1. **mcp_server**: An existing MCP server package (npm). Include package name, config, and registry entry.")
    sections.append("2. **api**: A public REST API. Include base URL, auth method, and key endpoints.")
    sections.append("3. **playwright**: Browser automation. Include the URL to navigate to.")
    sections.append("4. **custom_script**: A Python script to write. Include the full script code.")
    sections.append("")
    sections.append("Search the web for MCP servers first (check npm, GitHub). Fall back to APIs, then Playwright, then custom scripts.\n")
    sections.append("## Output Format\n")
    sections.append("Respond with ONLY valid JSON:")
    sections.append('```json\n{"expansions": [\n  {\n    "for_step_index": 1,\n    "solution_type": "mcp_server" | "api" | "playwright" | "custom_script",\n    "package": "npm package name (for mcp_server)",\n    "config": {},\n    "registry_entry": {"name": "...", "prefix": "...", "capabilities": [], "domains": []},\n    "new_tool_name": "exact MCP tool name to use in the step",\n    "url": "for playwright",\n    "script_code": "for custom_script"\n  }\n]}\n```')

    return "\n".join(sections)


def parse_expansion_response(response: str) -> list:
    """Parse expansion agent response into a list of expansion proposals."""
    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
    json_str = match.group(1) if match else response.strip()

    try:
        data = json.loads(json_str)
        return data.get("expansions", [])
    except (json.JSONDecodeError, TypeError):
        return []


def inject_tooling_phase(plan: Plan, expansions: list) -> Plan:
    """Add Phase 0: Tooling Setup to the plan and fix __MISSING__ steps."""
    tooling_steps = []
    step_index = 1  # Tooling steps get low indices, everything else shifts

    # Map expansions by step index
    expansion_map = {e["for_step_index"]: e for e in expansions}

    for exp in expansions:
        solution = exp["solution_type"]
        if solution == "mcp_server":
            tooling_steps.append(PlanStep(
                index=step_index,
                summary=f"Install {exp.get('package', 'MCP server')}",
                detail=f"npm install -g {exp.get('package', '')}. Add to Claude MCP config.",
                action_type="api",
                tool="local_scripts",
                params={"package": exp.get("package"), "config": exp.get("config", {})},
                risk="high",
                status="pending",
            ))
            step_index += 1

            if exp.get("registry_entry"):
                tooling_steps.append(PlanStep(
                    index=step_index,
                    summary=f"Register {exp['registry_entry'].get('name', 'tool')} in tool registry",
                    detail=f"Add entry to _registry.yml and create defaults file.",
                    action_type="api",
                    tool="local_scripts",
                    params={"registry_entry": exp["registry_entry"]},
                    risk="high",
                    status="pending",
                ))
                step_index += 1

        elif solution == "custom_script":
            tooling_steps.append(PlanStep(
                index=step_index,
                summary=f"Create custom script for {exp.get('for_step_index', '?')}",
                detail=exp.get("script_code", "Script code not provided"),
                action_type="api",
                tool="local_scripts",
                params={"script_code": exp.get("script_code", "")},
                risk="high",
                status="pending",
            ))
            step_index += 1

    # Re-index existing steps after tooling phase
    for phase in plan.phases:
        for step in phase.steps:
            step.index = step_index
            step_index += 1
            # Replace __MISSING__ tools with expansion proposals
            if step.tool == "__MISSING__" and step.index - len(tooling_steps) in expansion_map:
                original_index = step.index - len(tooling_steps)
            # Check by matching the original step context
            for orig_idx, exp in expansion_map.items():
                if step.tool == "__MISSING__" and step.missing_capability:
                    cap_systems = step.missing_capability.get("systems", [])
                    exp_systems = exp.get("registry_entry", {}).get("name", "")
                    if any(s.lower() in exp_systems.lower() for s in cap_systems) or orig_idx == step.index:
                        step.tool = exp.get("new_tool_name", step.tool)
                        step.missing_capability = None
                        break

    # Insert tooling phase at the beginning
    if tooling_steps:
        tooling_phase = Phase(name="Tooling Setup", steps=tooling_steps)
        plan.phases.insert(0, tooling_phase)

    return plan
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_expander.py -v
```

Expected: 5 tests PASS

Note: The `inject_tooling_phase` step re-indexing logic may need refinement during implementation. The core test validates that the Tooling Setup phase is inserted and __MISSING__ tools are replaced. If the index matching logic is too fragile, simplify it to match by `missing_capability.systems` only.

**Step 5: Commit**

```bash
git add bin/planner/expander.py bin/planner/test_expander.py
git commit -m "Add capability expansion agent with MCP discovery and tooling phase injection"
```

---

### Task 10: Wire expansion into core planner

**Files:**
- Modify: `bin/planner/planner.py`
- Modify: `bin/planner/test_planner.py`

**Step 1: Write the failing test**

Add to `bin/planner/test_planner.py`:

```python
def test_plan_card_triggers_expansion_for_missing_tools(planner):
    """When LLM plan has __MISSING__ tools, expansion agent should run."""
    card = {"id": 5, "source": "freshservice", "summary": "Okta SSO setup", "context_notes": ""}

    # First call returns plan with missing tools
    missing_response = json.dumps({
        "confidence": 0.5,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Access Okta", "detail": "", "action_type": "mcp",
             "tool": "__MISSING__", "params": {}, "risk": "high",
             "missing_capability": {"description": "Okta admin", "domain": "identity", "systems": ["Okta"]}},
        ]}],
    })

    # Expansion agent response
    expansion_response = json.dumps({
        "expansions": [{
            "for_step_index": 1,
            "solution_type": "playwright",
            "url": "https://admin.okta.com",
            "new_tool_name": "mcp__playwright__browser_navigate",
        }]
    })

    call_count = {"n": 0}
    def mock_cli(prompt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return missing_response
        return expansion_response

    with patch("planner._call_claude_cli", side_effect=mock_cli):
        plan = planner.plan_card(card)

    assert plan is not None
    # Should have a Tooling Setup phase or the __MISSING__ should be resolved
    has_tooling = any(p.name == "Tooling Setup" for p in plan.phases)
    has_missing = plan.has_missing_tools()
    # Either tooling phase was added or missing tools were resolved
    assert has_tooling or not has_missing
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_planner.py::test_plan_card_triggers_expansion_for_missing_tools -v
```

Expected: FAIL — expansion not wired in yet

**Step 3: Add expansion to planner.py**

In `bin/planner/planner.py`, update the `plan_card` method. Add import at top:

```python
from expander import build_expansion_prompt, parse_expansion_response, inject_tooling_phase
```

Then in `plan_card`, after parsing the LLM response, add the expansion check:

```python
        plan = parse_plan_response(response, card_id=card_id)
        if plan and plan.has_missing_tools():
            # Run expansion agent
            expansion_prompt = build_expansion_prompt(plan)
            expansion_response = _call_claude_cli(expansion_prompt)
            if expansion_response:
                expansions = parse_expansion_response(expansion_response)
                if expansions:
                    plan = inject_tooling_phase(plan, expansions)

        if plan:
            self.store.save(plan)
        return plan
```

**Step 4: Run all planner tests**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_planner.py -v
```

Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add bin/planner/planner.py bin/planner/test_planner.py
git commit -m "Wire capability expansion into core planner for __MISSING__ tool resolution"
```

---

### Task 11: LaunchAgent for planner worker

**Files:**
- Create: `bin/start-planner.sh`
- Modify: `bin/start-pollers.sh` (add planner to the startup sequence)

**Step 1: Create the planner LaunchAgent script**

Create `bin/start-planner.sh`:

```bash
#!/bin/bash
# Start the planner background worker as a LaunchAgent
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$HOME/.claude/eng-buddy"
PLIST_NAME="com.eng-buddy.planner"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

mkdir -p "$RUNTIME_DIR"

# Copy worker script to runtime
cp "$SKILL_DIR/bin/planner/worker.py" "$RUNTIME_DIR/planner-worker.py"
cp -r "$SKILL_DIR/bin/planner/" "$RUNTIME_DIR/planner/"
cp -r "$SKILL_DIR/bin/playbook_engine/" "$RUNTIME_DIR/playbook_engine/"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>${RUNTIME_DIR}/planner/worker.py</string>
        <string>--interval</string>
        <string>30</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${RUNTIME_DIR}/planner.log</string>
    <key>StandardErrorPath</key>
    <string>${RUNTIME_DIR}/planner.log</string>
    <key>WorkingDirectory</key>
    <string>${RUNTIME_DIR}</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Planner worker started (interval=30s)"
echo "Logs: $RUNTIME_DIR/planner.log"
```

**Step 2: Make executable**

```bash
chmod +x /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/start-planner.sh
```

**Step 3: Test that it runs without error**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy
bash bin/start-planner.sh
```

Expected: "Planner worker started" message. Check logs with `tail -f ~/.claude/eng-buddy/planner.log`.

**Step 4: Verify it's running**

```bash
launchctl list | grep planner
```

Expected: Shows `com.eng-buddy.planner` in the list.

**Step 5: Commit**

```bash
git add bin/start-planner.sh
git commit -m "Add LaunchAgent startup script for planner background worker"
```

---

### Task 12: Integration test — end-to-end plan flow

**Files:**
- Create: `bin/planner/test_integration.py`

**Step 1: Write the integration test**

Create `bin/planner/test_integration.py`:

```python
"""End-to-end integration test for the planning pipeline."""

import pytest
import sqlite3
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "playbook_engine"))

from models import Plan
from store import PlanStore
from planner import CardPlanner
from learner import plan_to_draft_playbook


@pytest.fixture
def env(tmp_path):
    db_path = tmp_path / "inbox.db"
    plans_dir = tmp_path / "plans"
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "_registry.yml").write_text("""tools:
  jira:
    prefix: "mcp__mcp-atlassian__jira_"
    capabilities: [create_issue, update_issue, add_comment]
    domains: [ticket_management]
  freshservice:
    prefix: "mcp__freshservice-mcp__"
    capabilities: [get_ticket_by_id, update_ticket, send_ticket_reply]
    domains: [service_desk]
  slack:
    prefix: "mcp__slack__slack_"
    capabilities: [post_message]
    domains: [communication]
""")

    # Create cards table
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, source TEXT, status TEXT, summary TEXT, context_notes TEXT, timestamp TEXT, classification TEXT, section TEXT)")
    conn.execute("INSERT INTO cards VALUES (1, 'freshservice', 'pending', 'SSO setup for Linear', 'Requester: jdoe', '2026-03-10', 'Service Request', '')")
    conn.commit()
    conn.close()

    return {
        "db_path": str(db_path),
        "plans_dir": str(plans_dir),
        "playbooks_dir": str(playbooks_dir),
        "registry_dir": str(registry_dir),
    }


def test_full_pipeline_llm_plan_to_draft_playbook(env):
    """Card → LLM plan → approve → execute → draft playbook."""
    planner = CardPlanner(**env)

    card = {"id": 1, "source": "freshservice", "summary": "SSO setup for Linear",
            "context_notes": "Requester: jdoe", "classification": "Service Request"}

    # Mock LLM response with a reasonable plan
    llm_response = json.dumps({
        "confidence": 0.75,
        "phases": [
            {"name": "Setup", "steps": [
                {"index": 1, "summary": "Get ticket details", "detail": "Fetch Freshservice ticket",
                 "action_type": "mcp", "tool": "mcp__freshservice-mcp__get_ticket_by_id",
                 "params": {"ticket_id": 1}, "risk": "low"},
            ]},
            {"name": "Execute", "steps": [
                {"index": 2, "summary": "Create Jira ticket", "detail": "Under SSO epic",
                 "action_type": "mcp", "tool": "mcp__mcp-atlassian__jira_create_issue",
                 "params": {"project": "ITWORK2", "summary": "[SSO] Linear"},
                 "draft_content": None, "risk": "low"},
            ]},
            {"name": "Communicate", "steps": [
                {"index": 3, "summary": "Reply to requester", "detail": "Confirm ticket creation",
                 "action_type": "mcp", "tool": "mcp__freshservice-mcp__send_ticket_reply",
                 "params": {},
                 "draft_content": "Hi jdoe, I've created Jira ticket ITWORK2-XXXX for your SSO request.",
                 "risk": "medium"},
            ]},
        ],
    })

    with patch("planner._call_claude_cli", return_value=llm_response):
        plan = planner.plan_card(card)

    # Verify plan structure
    assert plan is not None
    assert plan.source == "llm"
    assert len(plan.phases) == 3
    assert len(plan.all_steps()) == 3

    # Simulate approval
    for step in plan.all_steps():
        step.status = "approved"
    plan.all_steps()[2].draft_content = "Hi jdoe, I've created Jira ticket ITWORK2-9999 for your Linear SSO request."
    plan.all_steps()[2].status = "edited"

    # Simulate execution completion
    for step in plan.all_steps():
        if step.status != "edited":
            step.status = "done"
        else:
            step.status = "done"
    plan.status = "completed"
    planner.store.save(plan)

    # Learning loop: convert to draft playbook
    from manager import PlaybookManager
    pb = plan_to_draft_playbook(plan, card)
    mgr = PlaybookManager(env["playbooks_dir"])
    mgr.save_draft(pb)

    # Verify draft was created
    drafts = mgr.list_drafts()
    assert len(drafts) == 1
    assert drafts[0].created_from == "plan-learning"
    assert len(drafts[0].steps) == 3

    # Verify the draft would match a similar future card
    matches = mgr.match_ticket(ticket_type="Service Request", text="SSO setup for Okta", source="freshservice")
    # Drafts aren't in approved, so match_ticket won't find it
    # But after promotion it would
    mgr.promote_draft(pb.id)
    matches = mgr.match_ticket(ticket_type="Service Request", text="SSO setup for Okta", source="freshservice")
    assert len(matches) >= 1


def test_deduplication_prevents_double_planning(env):
    """Same card should not be planned twice."""
    planner = CardPlanner(**env)
    card = {"id": 1, "source": "freshservice", "summary": "SSO setup for Linear", "context_notes": ""}

    llm_response = json.dumps({
        "confidence": 0.7,
        "phases": [{"name": "Execute", "steps": [
            {"index": 1, "summary": "Do thing", "detail": "", "action_type": "mcp",
             "tool": "t1", "params": {}, "risk": "low"},
        ]}],
    })

    call_count = {"n": 0}
    def counting_cli(prompt):
        call_count["n"] += 1
        return llm_response

    with patch("planner._call_claude_cli", side_effect=counting_cli):
        plan1 = planner.plan_card(card)
        plan2 = planner.plan_card(card)

    # CLI should only be called once
    assert call_count["n"] == 1
    assert plan1.id == plan2.id
```

**Step 2: Run the integration test**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest test_integration.py -v
```

Expected: 2 tests PASS

**Step 3: Run the full planner test suite**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/bin/planner
python -m pytest -v
```

Expected: All tests PASS (~30+ tests across all test files)

**Step 4: Commit**

```bash
git add bin/planner/test_integration.py
git commit -m "Add end-to-end integration tests for planning pipeline"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Plan data models (Plan, Phase, PlanStep) | 8 |
| 2 | PlanStore (JSON + SQLite persistence) | 8 |
| 3 | Playbook-to-plan converter | 5 |
| 4 | LLM planning prompter + response parser | 9 |
| 5 | Core CardPlanner (match → plan → store) | 4 |
| 6 | Background worker daemon | 4 |
| 7 | Dashboard API routes (5 endpoints) | 6 |
| 8 | Plan-to-playbook learning loop | 4 |
| 9 | Expansion agent (missing tool discovery) | 5 |
| 10 | Wire expansion into core planner | 1 |
| 11 | LaunchAgent startup script | 0 (manual) |
| 12 | End-to-end integration tests | 2 |

**Total: 12 tasks, ~56 tests**

Covers: data models, persistence, playbook matching, LLM planning, capability expansion, dashboard API, learning loop, background worker, and integration testing.
