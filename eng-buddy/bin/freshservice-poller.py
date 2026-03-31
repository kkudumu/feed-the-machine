#!/usr/bin/env python3
"""
eng-buddy Freshservice Poller
Fetches tickets from two Freshservice views via the REST API:
  1. "Assigned To Kioja Unresolved" — agent_id + status Open/Pending
  2. "[IT-Systems] Open System Tickets" — workspace 2, group Global IT/Systems, status Open
Writes/updates cards in inbox.db; removes stale cards no longer in either view.
"""
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

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
STATE_FILE = BASE_DIR / "freshservice-ingestor-state.json"
HEALTH_FILE = BASE_DIR / "health" / "freshservice.json"
DB_PATH = BASE_DIR / "inbox.db"

FRESHSERVICE_DOMAIN = os.environ.get("FRESHSERVICE_DOMAIN") or credential("FRESHSERVICE_DOMAIN", "klaviyo")
if FRESHSERVICE_DOMAIN and not FRESHSERVICE_DOMAIN.endswith(".freshservice.com"):
    FRESHSERVICE_DOMAIN = f"{FRESHSERVICE_DOMAIN}.freshservice.com"
API_KEY = os.environ.get("FRESHSERVICE_API_KEY") or credential("FRESHSERVICE_API_KEY")
AGENT_ID = int(os.environ.get("ENG_BUDDY_FRESHSERVICE_AGENT_ID", "15004391041"))
GROUP_ID = int(os.environ.get("ENG_BUDDY_FRESHSERVICE_GROUP_ID", "15000745688"))
WORKSPACE_ID = int(os.environ.get("ENG_BUDDY_FRESHSERVICE_WORKSPACE_ID", "2"))

DASHBOARD_INVALIDATE_URL = os.environ.get(
    "ENG_BUDDY_DASHBOARD_INVALIDATE_URL",
    "http://127.0.0.1:7777/api/cache-invalidate",
)

# Status mapping
STATUS_MAP = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}


def _api_get(path, params=None):
    """Make a GET request to the Freshservice API. Returns parsed JSON."""
    if not API_KEY or not FRESHSERVICE_DOMAIN:
        raise RuntimeError("Missing Freshservice credentials")
    url = f"https://{FRESHSERVICE_DOMAIN}{path}"
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    auth = b64encode(f"{API_KEY}:X".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"  HTTP {e.code} for {url}: {body}")
        raise


def _fetch_filter(query, workspace_id=None, per_page=30):
    """Fetch all pages from the filter endpoint. Returns list of tickets."""
    tickets = []
    page = 1
    while True:
        params = {"query": f'"{query}"', "per_page": per_page, "page": page}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        data = _api_get("/api/v2/tickets/filter", params)
        batch = data.get("tickets", [])
        tickets.extend(batch)
        total = data.get("total", 0)
        if len(tickets) >= total or not batch:
            break
        page += 1
    return tickets


def fetch_view1_assigned_unresolved():
    """View 1: Assigned To Kioja, status Open or Pending."""
    query = f"agent_id:{AGENT_ID} AND (status:2 OR status:3)"
    return _fetch_filter(query)


def fetch_view2_it_systems_open():
    """View 2: IT-Systems Open System Tickets (workspace 2, group, status Open)."""
    query = f"group_id:{GROUP_ID} AND status:2"
    return _fetch_filter(query, workspace_id=WORKSPACE_ID)


def ticket_url(ticket_id):
    return f"https://{FRESHSERVICE_DOMAIN}/a/tickets/{ticket_id}"


def card_summary(ticket):
    """Build a concise card summary from ticket data."""
    tid = ticket["id"]
    subject = ticket.get("subject", "").strip()
    ttype = ticket.get("type", "Ticket")
    return f"#{tid} [{ttype}] {subject}"


def card_classification(ticket):
    """Map ticket priority to card classification."""
    p = ticket.get("priority", 2)
    if p >= 3:
        return "action-required"
    return "needs-response"


def write_health(status, ticket_count):
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps({
        "status": status,
        "last_poll": datetime.now(timezone.utc).isoformat(),
        "ticket_count": ticket_count,
    }))


def invalidate_dashboard_cache():
    payload = json.dumps({"source": "freshservice"}).encode("utf-8")
    req = urllib.request.Request(
        DASHBOARD_INVALIDATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2):
            return
    except (urllib.error.URLError, TimeoutError, OSError):
        return


def main():
    try:
        with single_instance("freshservice-poller"):
            now = datetime.now(timezone.utc).isoformat()
            print(f"[{datetime.now()}] Freshservice poller starting...")

            try:
                v1 = fetch_view1_assigned_unresolved()
                print(f"  View 1 (Assigned/Unresolved): {len(v1)} tickets")
            except Exception as e:
                print(f"  View 1 failed: {e}")
                v1 = []

            try:
                v2 = fetch_view2_it_systems_open()
                print(f"  View 2 (IT-Systems Open): {len(v2)} tickets")
            except Exception as e:
                print(f"  View 2 failed: {e}")
                v2 = []

            all_tickets = {}
            for ticket in v1:
                all_tickets[ticket["id"]] = ticket
            for ticket in v2:
                all_tickets[ticket["id"]] = ticket

            total = len(all_tickets)
            print(f"  Combined unique tickets: {total}")

            if not all_tickets and not v1 and not v2:
                print("  No tickets fetched — skipping DB update to avoid wiping on API error.")
                write_health("error", 0)
                return

            conn = sqlite3.connect(DB_PATH)
            valid_summaries = set()
            changed = False

            for ticket in all_tickets.values():
                summary = card_summary(ticket)
                valid_summaries.add(summary)
                classification = card_classification(ticket)
                status_label = STATUS_MAP.get(ticket.get("status"), "Open")
                priority_label = PRIORITY_MAP.get(ticket.get("priority"), "Medium")
                url = ticket_url(ticket["id"])

                proposed = json.dumps([{
                    "type": "review_freshservice_ticket",
                    "draft": f"Review Freshservice ticket #{ticket['id']}: {ticket.get('subject', '')}",
                    "source": "freshservice",
                    "url": url,
                }])

                metadata = json.dumps({
                    "ticket_id": ticket["id"],
                    "status": status_label,
                    "priority": priority_label,
                    "type": ticket.get("type", ""),
                    "requester_id": ticket.get("requester_id"),
                    "group_id": ticket.get("group_id"),
                    "agent_id": ticket.get("agent_id"),
                    "created_at": ticket.get("created_at"),
                    "updated_at": ticket.get("updated_at"),
                    "url": url,
                })

                before = conn.total_changes
                conn.execute(
                    """INSERT INTO cards
                       (source, timestamp, summary, classification, status, section,
                        proposed_actions, analysis_metadata, execution_status)
                       VALUES (?, ?, ?, ?, 'pending', 'needs-action', ?, ?, 'not_run')
                       ON CONFLICT(source, summary) DO UPDATE SET
                           timestamp=excluded.timestamp,
                           classification=excluded.classification,
                           proposed_actions=excluded.proposed_actions,
                           analysis_metadata=excluded.analysis_metadata""",
                    ("freshservice", now, summary, classification, proposed, metadata),
                )
                if conn.total_changes > before:
                    changed = True

            existing = conn.execute(
                "SELECT id, summary FROM cards WHERE source='freshservice'"
            ).fetchall()
            stale_ids = [row[0] for row in existing if row[1] not in valid_summaries]
            if stale_ids:
                placeholders = ",".join("?" * len(stale_ids))
                conn.execute(
                    f"DELETE FROM cards WHERE id IN ({placeholders})", stale_ids
                )
                changed = True
                print(f"  Removed {len(stale_ids)} stale cards")

            conn.commit()
            conn.close()

            STATE_FILE.write_text(json.dumps({"last_checked": now}))
            write_health("ok", total)

            if changed:
                invalidate_dashboard_cache()

            print(f"[{datetime.now()}] Done — {total} tickets synced.")
    except RuntimeError as exc:
        print(f"[{datetime.now()}] {exc}")


if __name__ == "__main__":
    import sys
    # Accept --refresh-now flag (used by start-pollers.sh) — just run normally
    main()
