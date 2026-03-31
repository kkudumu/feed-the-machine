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
    with patch.object(worker.planner, "plan_card", return_value=MagicMock()):
        worker.process_once()

    # Manually mark as planned in the store
    from models import Plan
    plan = Plan.from_dict({
        "id": "plan-1-0", "card_id": 1, "source": "llm", "playbook_id": None,
        "confidence": 0.7, "phases": [], "status": "pending",
        "created_at": "2026-03-10", "executed_at": None,
    })
    worker.planner.store.save(plan)

    with patch.object(worker.planner, "plan_card") as mock_plan:
        processed = worker.process_once()
    assert processed == 0


def test_worker_respects_lock(worker_env):
    Path(worker_env["lock_path"]).write_text("locked")
    worker = PlannerWorker(**worker_env)
    assert worker.acquire_lock() is False


def test_worker_acquires_and_releases_lock(worker_env):
    worker = PlannerWorker(**worker_env)
    assert worker.acquire_lock() is True
    assert Path(worker_env["lock_path"]).exists()
    worker.release_lock()
    assert not Path(worker_env["lock_path"]).exists()
