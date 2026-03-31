"""Background worker daemon — polls for unplanned cards and generates plans."""

import time
import logging
import importlib.util
import os
import sys
from pathlib import Path

# Load planner.py via importlib to avoid collision with the 'planner' package dir.
# Use a unique alias to avoid overwriting sys.modules["planner_module"] which
# test_planner.py also registers (causes cross-test contamination in pytest).
_planner_spec = importlib.util.spec_from_file_location(
    "planner_worker_mod", Path(__file__).parent / "planner.py"
)
_planner_mod = importlib.util.module_from_spec(_planner_spec)
sys.modules["planner_worker_mod"] = _planner_mod
_planner_spec.loader.exec_module(_planner_mod)
CardPlanner = _planner_mod.CardPlanner

logger = logging.getLogger("planner-worker")

DEFAULT_POLL_INTERVAL = 30
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
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            # Check if lock is stale (older than 5 minutes)
            try:
                age = time.time() - self.lock_path.stat().st_mtime
                if age >= 300:
                    self.lock_path.unlink(missing_ok=True)
                    return self.acquire_lock()
            except OSError:
                pass
            return False
        except OSError:
            return False

    def release_lock(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def process_once(self) -> int:
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
        try:
            import urllib.request
            import json
            data = json.dumps({"source": source}).encode()
            req = urllib.request.Request(
                NOTIFY_URL, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def run(self, interval: int = DEFAULT_POLL_INTERVAL) -> None:
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
