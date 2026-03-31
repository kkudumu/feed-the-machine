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
