#!/usr/bin/env python3
"""
eng-buddy Freshservice collector shim

This script used to run a multi-stage LLM enrichment pipeline in the
background. It is now collection-only: it syncs Freshservice tickets into
inbox.db by delegating to the direct REST poller and marks cards as collected
without invoking Claude.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from poller_runtime import single_instance

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
DB_PATH = BASE_DIR / "inbox.db"
HEALTH_FILE = BASE_DIR / "health" / "freshservice-enrichment.json"
POLLER_PATH = Path(__file__).with_name("freshservice-poller.py")

STAGE_LLM_CONFIG = {
    "classify": {"cli": "disabled", "args": []},
    "enrich": {"cli": "disabled", "args": []},
    "detect_patterns": {"cli": "disabled", "args": []},
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_unenriched_cards():
    if not DB_PATH.exists():
        return []
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM cards
               WHERE source = 'freshservice'
                 AND COALESCE(enrichment_status, 'not_enriched') != 'collection_only'"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def enrich_single_card(card):
    if not DB_PATH.exists():
        return {"status": "skipped", "reason": "missing_db"}

    card_id = card.get("id")
    if not card_id:
        return {"status": "skipped", "reason": "missing_card_id"}

    conn = get_db()
    try:
        conn.execute(
            "UPDATE cards SET enrichment_status = 'collection_only' WHERE id = ?",
            [card_id],
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "collection_only", "card_id": card_id}


def write_health(status: str, synced_count: int, errors: int = 0):
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(
        json.dumps(
            {
                "status": status,
                "last_run": datetime.now(timezone.utc).isoformat(),
                "synced_count": synced_count,
                "errors": errors,
                "mode": "collection_only",
            }
        )
    )


def _load_freshservice_poller():
    spec = importlib.util.spec_from_file_location("freshservice_poller", POLLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main():
    try:
        with single_instance("freshservice-enrichment"):
            poller = _load_freshservice_poller()
            poller.main()

            cards = fetch_unenriched_cards()
            for card in cards:
                enrich_single_card(card)

            write_health("ok", len(cards))
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] Freshservice collection-only sync complete "
                f"({len(cards)} card(s) marked collection_only)."
            )
    except RuntimeError as exc:
        print(f"[{datetime.now(timezone.utc).isoformat()}] {exc}")
    except Exception as exc:
        write_health("error", 0, errors=1)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Freshservice sync failed: {exc}")


if __name__ == "__main__":
    main()
