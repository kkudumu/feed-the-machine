# Smart Pollers, Dashboard Tabs & Learning Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade eng-buddy with smart Slack/Gmail/Calendar tabs, morning briefing, and a persistent learning engine that captures work patterns for future automation.

**Architecture:** Three pollers (Slack 5m, Gmail 10m, Calendar 30m) collect raw data, batch-classify via Claude CLI with persistent context injection, and write enriched cards to inbox.db. Dashboard renders two-section layouts per tab. Learning engine persists stakeholder graph, patterns, and work traces across sessions.

**Tech Stack:** Python 3, FastAPI, SQLite, Claude CLI (`claude --print`), Gmail MCP, Slack API, Google Calendar MCP, xterm.js, SSE

**Design Doc:** `docs/plans/2026-03-07-smart-pollers-design.md`

---

## Task 1: Database Schema Migration

**Files:**
- Create: `dashboard/migrate.py`
- Modify: `dashboard/server.py:27-30` (call migration on startup)

**Step 1: Write the migration script**

```python
# dashboard/migrate.py
"""Run idempotent schema migrations on inbox.db."""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "eng-buddy" / "inbox.db"

MIGRATIONS = [
    # New columns for smart classification
    "ALTER TABLE cards ADD COLUMN section TEXT DEFAULT 'needs-action'",
    "ALTER TABLE cards ADD COLUMN draft_response TEXT",
    "ALTER TABLE cards ADD COLUMN context_notes TEXT",
    "ALTER TABLE cards ADD COLUMN responded INTEGER DEFAULT 0",
    "ALTER TABLE cards ADD COLUMN filter_suggested INTEGER DEFAULT 0",
    # Stats table
    """CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        metric TEXT NOT NULL,
        value REAL DEFAULT 0,
        details TEXT
    )""",
    # Briefing cache
    """CREATE TABLE IF NOT EXISTS briefings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        generated_at TEXT NOT NULL
    )""",
    # Filter suggestions tracking
    """CREATE TABLE IF NOT EXISTS filter_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        pattern TEXT NOT NULL,
        ignore_count INTEGER DEFAULT 0,
        suggested_at TEXT,
        status TEXT DEFAULT 'tracking',
        filter_id TEXT
    )""",
]


def migrate():
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
                print(f"Migration warning: {e}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    migrate()
    print("Migrations complete.")
```

**Step 2: Call migration on server startup**

In `server.py`, inside the `lifespan` function (line 27), add:

```python
from migrate import migrate

@asynccontextmanager
async def lifespan(app: FastAPI):
    STATIC_DIR.mkdir(exist_ok=True)
    migrate()
    yield
```

**Step 3: Test migration is idempotent**

```bash
cd ~/.claude/skills/eng-buddy/dashboard
python migrate.py && python migrate.py  # should run twice without error
```

**Step 4: Commit**

```bash
git add dashboard/migrate.py
git commit -m "Add idempotent schema migration for smart pollers"
```

---

## Task 2: Persistent Memory — Learning Engine Foundation

**Files:**
- Create: `bin/brain.py` (shared module for all pollers + server)
- Create: `memory/stakeholders.json` (template)
- Create: `memory/patterns.json` (template)
- Create: `memory/context.json` (template)

**Step 1: Create memory directory and template files**

```bash
mkdir -p ~/.claude/skills/eng-buddy/memory
```

`memory/context.json`:
```json
{
  "role": "IT Systems Engineer",
  "team": "IT Engineering",
  "company": "Klaviyo",
  "manager": "ashley.kronstat",
  "email": "kioja.kudumu@klaviyo.com",
  "tools": ["Okta", "Jamf", "Freshservice", "Jira", "Slack", "ConductorOne", "Google Workspace"],
  "preferences": {
    "response_tone": "friendly but concise",
    "never_auto_send": true,
    "deep_work_hours": "13:00-15:30",
    "standup_time": "10:00"
  },
  "current_priorities": [],
  "learned_rules": []
}
```

`memory/stakeholders.json`:
```json
{}
```

`memory/patterns.json`:
```json
{
  "patterns": [],
  "automation_opportunities": []
}
```

**Step 2: Write brain.py — shared context builder and learning parser**

```python
# bin/brain.py
"""
eng-buddy Learning Engine.
Builds context prompts from persistent memory and parses Claude responses
for new patterns, stakeholder updates, and automation opportunities.
"""
import json
import re
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path.home() / ".claude" / "eng-buddy" / "memory"
MEMORY_DIR.mkdir(exist_ok=True)


def _load(name, default=None):
    p = MEMORY_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return default if default is not None else {}


def _save(name, data):
    (MEMORY_DIR / name).write_text(json.dumps(data, indent=2))


def load_context():
    return _load("context.json", {})


def load_stakeholders():
    return _load("stakeholders.json", {})


def load_patterns():
    return _load("patterns.json", {"patterns": [], "automation_opportunities": []})


def load_traces():
    return _load("traces.json", {"traces": []})


def build_context_prompt(batch_items=None):
    """Build the persistent context block injected into every Claude CLI call."""
    ctx = load_context()
    stakeholders = load_stakeholders()
    patterns = load_patterns()

    # Pick relevant stakeholders if batch has sender info
    relevant = {}
    if batch_items:
        senders = set()
        for item in batch_items:
            s = item.get("sender_email", "") or item.get("from", "") or item.get("sender", "")
            if s:
                # Normalize to username
                username = s.split("@")[0].replace(".", "_") if "@" in s else s.lower().replace(" ", "_")
                senders.add(username)
        for key, val in stakeholders.items():
            normalized = key.replace(".", "_")
            if normalized in senders or any(normalized in s for s in senders):
                relevant[key] = val

    priorities_str = "\n".join(f"- {p}" for p in ctx.get("current_priorities", [])) or "None set"
    rules_str = "\n".join(f"- {r}" for r in ctx.get("learned_rules", [])) or "None yet"

    stakeholder_str = ""
    if relevant:
        parts = []
        for name, info in relevant.items():
            parts.append(f"  {name}: {info.get('role', 'unknown')} — {info.get('relationship', '')} — expects response in {info.get('avg_response_expectation', 'unknown')}")
        stakeholder_str = "\n".join(parts)
    else:
        stakeholder_str = "  No matching stakeholders for this batch."

    playbook_str = ""
    known = patterns.get("patterns", [])
    if known:
        parts = []
        for p in known[:10]:
            parts.append(f"  - {p['id']}: trigger={p.get('trigger', '?')}, steps={len(p.get('steps', []))}, used {p.get('times_used', 0)} times")
        playbook_str = "\n".join(parts)
    else:
        playbook_str = "  No playbooks captured yet."

    return f"""You are eng-buddy, an intelligent work assistant for {ctx.get('role', 'an engineer')} at {ctx.get('company', 'a company')}.
Manager: {ctx.get('manager', 'unknown')}
Team: {ctx.get('team', 'unknown')}
Response tone: {ctx.get('preferences', {}).get('response_tone', 'professional')}

Current priorities:
{priorities_str}

Learned rules (APPLY THESE):
{rules_str}

Relevant stakeholders:
{stakeholder_str}

Known playbooks:
{playbook_str}

AFTER completing your primary task, also output these sections if applicable (as JSON blocks):
- <!--STAKEHOLDER_UPDATES-->: [{{"name": "...", "field": "...", "value": "..."}}]
- <!--NEW_PATTERNS-->: [{{"trigger": "...", "steps": [...], "category": "..."}}]
- <!--AUTOMATION_OPPORTUNITIES-->: [{{"observation": "...", "suggestion": "..."}}]
- <!--LEARNED_RULES-->: ["rule text", ...]
- <!--WORK_TRACES-->: [{{"trigger": "...", "category": "...", "step_observed": "..."}}]
"""


def parse_learning(claude_response):
    """Parse Claude's response for learning sections and merge into memory."""
    sections = {
        "STAKEHOLDER_UPDATES": _parse_section(claude_response, "STAKEHOLDER_UPDATES"),
        "NEW_PATTERNS": _parse_section(claude_response, "NEW_PATTERNS"),
        "AUTOMATION_OPPORTUNITIES": _parse_section(claude_response, "AUTOMATION_OPPORTUNITIES"),
        "LEARNED_RULES": _parse_section(claude_response, "LEARNED_RULES"),
        "WORK_TRACES": _parse_section(claude_response, "WORK_TRACES"),
    }

    if sections["STAKEHOLDER_UPDATES"]:
        sh = load_stakeholders()
        for update in sections["STAKEHOLDER_UPDATES"]:
            name = update.get("name", "")
            if name:
                if name not in sh:
                    sh[name] = {}
                field = update.get("field", "")
                if field:
                    sh[name][field] = update.get("value", "")
                sh[name]["last_updated"] = datetime.now().isoformat()
        _save("stakeholders.json", sh)

    if sections["NEW_PATTERNS"]:
        pt = load_patterns()
        for pattern in sections["NEW_PATTERNS"]:
            pid = pattern.get("category", "unknown") + "-" + str(len(pt["patterns"]))
            pt["patterns"].append({
                "id": pid,
                "trigger": pattern.get("trigger", ""),
                "steps": pattern.get("steps", []),
                "category": pattern.get("category", ""),
                "automation_level": "observe",
                "times_used": 1,
                "detected_at": datetime.now().isoformat(),
            })
        _save("patterns.json", pt)

    if sections["AUTOMATION_OPPORTUNITIES"]:
        pt = load_patterns()
        for opp in sections["AUTOMATION_OPPORTUNITIES"]:
            pt["automation_opportunities"].append({
                "observation": opp.get("observation", ""),
                "suggestion": opp.get("suggestion", ""),
                "status": "pending_review",
                "detected_at": datetime.now().isoformat(),
            })
        _save("patterns.json", pt)

    if sections["LEARNED_RULES"]:
        ctx = load_context()
        existing = set(ctx.get("learned_rules", []))
        for rule in sections["LEARNED_RULES"]:
            if isinstance(rule, str) and rule not in existing:
                ctx.setdefault("learned_rules", []).append(rule)
        _save("context.json", ctx)

    if sections["WORK_TRACES"]:
        tr = load_traces()
        for trace in sections["WORK_TRACES"]:
            tr["traces"].append({
                **trace,
                "timestamp": datetime.now().isoformat(),
            })
        # Cap at 500 traces
        tr["traces"] = tr["traces"][-500:]
        _save("traces.json", tr)

    return sections


def _parse_section(text, section_name):
    """Extract a JSON block between <!--SECTION--> markers."""
    pattern = rf'<!--{section_name}-->\s*(\[.*?\])'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return []
```

**Step 3: Commit**

```bash
git add bin/brain.py
git add -f memory/context.json memory/stakeholders.json memory/patterns.json
git commit -m "Add learning engine foundation with persistent memory stores"
```

---

## Task 3: Rewrite Slack Poller — Smart Classification + inbox.db

**Files:**
- Rewrite: `bin/slack-poller.py`
- Reference: `bin/brain.py`

**Step 1: Rewrite slack-poller.py**

Key changes from existing:
- Add `write_to_inbox_db()` (Slack poller currently doesn't write to db)
- Expand scope: unreads + threads participated in last 3 days + @here
- Add `check_responded()`: if user replied after last message, mark responded
- After collection, batch call Claude CLI for classification + draft responses
- Inject `brain.build_context_prompt()` into Claude call
- Parse Claude response with `brain.parse_learning()`
- Keep existing daily log + notification behavior

The poller should:
1. Collect raw messages (existing logic, expanded scope)
2. For each thread, determine if user has responded (new)
3. Build batch payload: `[{sender, channel, text, thread_ts, responded, is_mention}]`
4. Call `claude --print` with context prompt + batch payload + classification instructions
5. Parse Claude's JSON response: `[{id, section, classification, draft_response, context_notes}]`
6. Write each to inbox.db with new fields
7. Parse learning sections from Claude response
8. Update state, write daily log

**Claude classification prompt template:**

```
{brain.build_context_prompt(batch)}

Classify each Slack message below. For each, return JSON:
- section: "needs-action" or "no-action"
- classification: "needs-response", "fyi", "responded", "noise"
- draft_response: For needs-action items, write a context-aware draft reply. Use available info about Jira tickets, Freshservice tickets, or other systems mentioned. null for no-action.
- context_notes: Brief context about why this needs action or what the status is. null if obvious.

Messages:
{json.dumps(batch_items, indent=2)}

Return ONLY a JSON array. No prose.
```

**Step 2: Update LaunchAgent plist to 5 min (300s)**

Modify `bin/com.engbuddy.slackpoller.plist` line 13: change `<integer>600</integer>` to `<integer>300</integer>`.

**Step 3: Test manually**

```bash
cd ~/.claude/skills/eng-buddy && python bin/slack-poller.py
# Verify: cards appear in inbox.db with section, draft_response fields
```

**Step 4: Commit**

```bash
git add bin/slack-poller.py bin/com.engbuddy.slackpoller.plist
git commit -m "Rewrite Slack poller with smart classification and draft responses"
```

---

## Task 4: Rewrite Gmail Poller — Smart Classification + Adaptive Filtering

**Files:**
- Rewrite: `bin/gmail-poller.py`
- Reference: `bin/brain.py`

**Step 1: Rewrite gmail-poller.py**

Key changes from existing:
- Remove watch-file dependency — scan ALL inbox emails from last 3 days
- Claude CLI classifies everything: `action-needed`, `alert/fyi`, `noise`
- For action-needed: Claude drafts responses with cross-MCP context
- Track ignored cards per sender pattern for adaptive filter suggestions
- Inject brain context, parse learning

The poller should:
1. Fetch all inbox emails from last 3 days via Gmail OAuth (existing auth works)
2. Deduplicate against seen_msg_ids in state
3. Build batch payload: `[{from, subject, snippet, labels, thread_id}]`
4. Call `claude --print` with context prompt + batch + classification instructions
5. Parse Claude response: `[{id, section, classification, draft_response, context_notes}]`
6. Write to inbox.db
7. Update filter_suggestions table: increment ignore_count for patterns marked noise
8. When ignore_count >= 10, set `suggested_at` to now, `status` to "suggest"
9. Parse learning sections

**Claude classification prompt template:**

```
{brain.build_context_prompt(batch)}

Classify each email below as:
- section: "action-needed", "alert", or "noise"
- classification: more specific label (e.g., "needs-response", "offboarding-fyi", "security-alert", "marketing-spam")
- draft_response: For action-needed emails that need a reply, draft one. null otherwise.
- context_notes: Brief context. For alerts, a one-line summary. null for noise.

Emails:
{json.dumps(batch_items, indent=2)}

Return ONLY a JSON array. No prose.
```

**Step 2: Update LaunchAgent plist to 10 min (600s)**

`bin/com.engbuddy.gmailpoller.plist` — already 600s, no change needed.

**Step 3: Test manually**

```bash
cd ~/.claude/skills/eng-buddy && python bin/gmail-poller.py
# Verify: cards in inbox.db with action-needed/alert/noise sections
```

**Step 4: Commit**

```bash
git add bin/gmail-poller.py
git commit -m "Rewrite Gmail poller with smart classification and adaptive filtering"
```

---

## Task 5: Create Calendar Poller

**Files:**
- Create: `bin/calendar-poller.py`
- Create: `bin/com.engbuddy.calendarpoller.plist`

**Step 1: Write calendar-poller.py**

This poller is different — it calls Claude CLI which uses Google Calendar MCP to fetch events, then enriches them with Jira/email context.

```python
#!/usr/bin/env python3
"""
eng-buddy Calendar Poller
Fetches today's events via Claude CLI + Google Calendar MCP.
Enriches events with context from Jira/Freshservice/email.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, date, timezone
from pathlib import Path

# Allow importing brain.py from same directory
sys.path.insert(0, str(Path(__file__).parent))
import brain

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
DB_PATH = BASE_DIR / "inbox.db"
STATE_FILE = BASE_DIR / "calendar-poller-state.json"


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_events():
    """Use Claude CLI to fetch today's calendar events via Google Calendar MCP."""
    today = date.today().isoformat()
    prompt = (
        f"Use the Google Calendar MCP list-events tool to get all events for today ({today}). "
        f"Use calendarId 'primary'. "
        f"Return ONLY a JSON array of objects with keys: "
        f"id, summary, start (ISO string), end (ISO string), "
        f"location, hangout_link (Google Meet/Zoom URL if present), "
        f"attendees (array of email strings), description (first 200 chars). "
        f"No prose, just the JSON array."
    )
    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "--print", prompt],
            capture_output=True, text=True, timeout=30
        )
        match = re.search(r'\[.*\]', result.stdout, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M')}] Calendar fetch failed: {e}")
    return []


def enrich_events(events):
    """Call Claude CLI to add context notes for each event."""
    if not events:
        return []

    context = brain.build_context_prompt(events)
    events_json = json.dumps(events, indent=2)

    prompt = f"""{context}

Here are today's calendar events. For each, add:
- context_notes: Relevant context from Jira tickets, recent emails, or Slack threads related to the meeting topic or attendees. Include prep suggestions.
- priority: "high" (needs prep), "normal", or "low" (social/optional)
- prep_needed: true/false

Events:
{events_json}

Return ONLY a JSON array with the original fields plus context_notes, priority, prep_needed. No prose."""

    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "--print", prompt],
            capture_output=True, text=True, timeout=45
        )
        match = re.search(r'\[.*\]', result.stdout, re.DOTALL)
        if match:
            enriched = json.loads(match.group(0))
            brain.parse_learning(result.stdout)
            return enriched
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M')}] Calendar enrichment failed: {e}")

    return events


def write_to_db(events):
    """Write calendar events as cards to inbox.db."""
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    today = date.today().isoformat()

    # Clear today's calendar cards and rewrite (events may have changed)
    conn.execute(
        "DELETE FROM cards WHERE source = 'calendar' AND date(timestamp) = ?",
        [today]
    )

    for event in events:
        summary = f"{event.get('start', '?')[:5]} — {event.get('summary', 'No title')}"
        section = "needs-action" if event.get("prep_needed") else "no-action"
        proposed = json.dumps([{
            "type": "calendar_event",
            "summary": event.get("summary", ""),
            "start": event.get("start", ""),
            "end": event.get("end", ""),
            "hangout_link": event.get("hangout_link", ""),
            "attendees": event.get("attendees", []),
        }])
        conn.execute(
            """INSERT INTO cards
               (source, timestamp, summary, classification, status,
                proposed_actions, execution_status, section, context_notes)
               VALUES ('calendar', ?, ?, ?, 'pending', ?, 'not_run', ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                summary,
                event.get("priority", "normal"),
                proposed,
                section,
                event.get("context_notes", ""),
            )
        )

    conn.commit()
    conn.close()


def main():
    state = load_state()
    now = datetime.now()

    # Skip if already fetched this half-hour
    last_fetch = state.get("last_fetch", "")
    current_slot = now.strftime("%Y-%m-%d-%H") + ("-00" if now.minute < 30 else "-30")
    if last_fetch == current_slot:
        print(f"[{now.strftime('%H:%M')}] Already fetched this slot, skipping")
        return

    print(f"[{now.strftime('%H:%M')}] Fetching calendar events...")
    events = fetch_events()

    if events:
        print(f"[{now.strftime('%H:%M')}] Enriching {len(events)} events with context...")
        events = enrich_events(events)
        write_to_db(events)
        print(f"[{now.strftime('%H:%M')}] Wrote {len(events)} calendar cards to inbox.db")
    else:
        print(f"[{now.strftime('%H:%M')}] No events found for today")

    state["last_fetch"] = current_slot
    save_state(state)


if __name__ == "__main__":
    main()
```

**Step 2: Create LaunchAgent plist (30 min = 1800s)**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.engbuddy.calendarpoller</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/python3</string>
        <string>/Users/kioja.kudumu/.claude/eng-buddy/bin/calendar-poller.py</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>StandardOutPath</key>
    <string>/Users/kioja.kudumu/.claude/eng-buddy/calendar-poller.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/kioja.kudumu/.claude/eng-buddy/calendar-poller.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

**Step 3: Test manually**

```bash
cd ~/.claude/skills/eng-buddy && python bin/calendar-poller.py
```

**Step 4: Commit**

```bash
git add bin/calendar-poller.py bin/com.engbuddy.calendarpoller.plist
git commit -m "Add Calendar poller with event enrichment via Google Calendar MCP"
```

---

## Task 6: Dashboard Server — New API Endpoints

**Files:**
- Modify: `dashboard/server.py`

**Step 1: Update card API to support section filtering**

Add `section` query param to `GET /api/cards`:

```python
@app.get("/api/cards")
async def get_cards(source: str = None, status: str = "pending", section: str = None):
    conn = get_db()
    try:
        query = "SELECT * FROM cards WHERE status = ?"
        params = [status]
        if source:
            query += " AND source = ?"
            params.append(source)
        if section:
            query += " AND section = ?"
            params.append(section)
        query += " ORDER BY timestamp DESC"
        # ... rest unchanged
```

**Step 2: Add send-draft endpoints**

```python
@app.post("/api/cards/{card_id}/send-slack")
async def send_slack_draft(card_id: int):
    """Send the draft response to Slack via MCP."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", [card_id]).fetchone()
        if not row:
            raise HTTPException(404, "card not found")
        card = dict(row)
    finally:
        conn.close()

    draft = card.get("draft_response", "")
    if not draft:
        raise HTTPException(400, "no draft response")

    actions = json.loads(card.get("proposed_actions") or "[]")
    channel = ""
    thread_ts = ""
    for a in actions:
        channel = a.get("channel_id", channel)
        thread_ts = a.get("thread_ts", thread_ts)

    if not channel:
        raise HTTPException(400, "no channel info in card")

    prompt = (
        f"Use the Slack MCP slack_reply_to_thread tool. "
        f"Channel: {channel}, thread_ts: {thread_ts}, "
        f"text: {json.dumps(draft)}"
    )
    result = subprocess.run(
        ["claude", "--dangerously-skip-permissions", "--print", prompt],
        capture_output=True, text=True, timeout=30
    )

    conn = get_db()
    conn.execute(
        "UPDATE cards SET status = 'completed', responded = 1, section = 'no-action' WHERE id = ?",
        [card_id]
    )
    conn.commit()
    conn.close()

    _record_stat("drafts_sent")
    return {"status": "sent", "output": result.stdout[:500]}


@app.post("/api/cards/{card_id}/send-email")
async def send_email_draft(card_id: int):
    """Send the draft email response via Gmail MCP."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", [card_id]).fetchone()
        if not row:
            raise HTTPException(404, "card not found")
        card = dict(row)
    finally:
        conn.close()

    draft = card.get("draft_response", "")
    if not draft:
        raise HTTPException(400, "no draft response")

    actions = json.loads(card.get("proposed_actions") or "[]")
    thread_id = ""
    to_email = ""
    subject = ""
    for a in actions:
        thread_id = a.get("thread_id", thread_id)
        to_email = a.get("to_email", to_email)
        subject = a.get("subject", subject)

    prompt = (
        f"Use the Gmail MCP send_email tool to reply. "
        f"To: {to_email}, Subject: Re: {subject}, "
        f"Body: {json.dumps(draft)}, "
        f"threadId: {thread_id}"
    )
    result = subprocess.run(
        ["claude", "--dangerously-skip-permissions", "--print", prompt],
        capture_output=True, text=True, timeout=30
    )

    conn = get_db()
    conn.execute(
        "UPDATE cards SET status = 'completed', responded = 1, section = 'no-action' WHERE id = ?",
        [card_id]
    )
    conn.commit()
    conn.close()

    _record_stat("drafts_sent")
    return {"status": "sent", "output": result.stdout[:500]}
```

**Step 3: Add briefing endpoint**

```python
@app.get("/api/briefing")
async def get_briefing(regenerate: bool = False):
    """Generate or return cached morning briefing."""
    import time
    today = date.today().isoformat()

    conn = get_db()
    try:
        # Check cache
        if not regenerate:
            row = conn.execute(
                "SELECT content FROM briefings WHERE date = ?", [today]
            ).fetchone()
            if row:
                return json.loads(row[0])

        # Gather data for briefing
        pending_cards = conn.execute(
            "SELECT source, section, summary, context_notes, draft_response FROM cards WHERE status = 'pending' ORDER BY timestamp DESC LIMIT 30"
        ).fetchall()

        # Get yesterday's stats
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        stats = conn.execute(
            "SELECT metric, SUM(value) FROM stats WHERE date = ? GROUP BY metric", [yesterday]
        ).fetchall()
    finally:
        conn.close()

    cards_data = [dict(r) for r in pending_cards]
    stats_data = {r[0]: r[1] for r in stats} if stats else {}

    # Build briefing prompt
    sys_path = Path(__file__).parent.parent / "bin"
    sys.path.insert(0, str(sys_path))
    from brain import build_context_prompt

    context = build_context_prompt()
    prompt = f"""{context}

Generate a morning briefing for today ({today}). You have:

PENDING CARDS:
{json.dumps(cards_data, indent=2)}

YESTERDAY'S STATS:
{json.dumps(stats_data, indent=2)}

Return a JSON object with these sections:
{{
  "date": "{today}",
  "meetings": [{{  "time": "HH:MM", "title": "...", "prep": "..." }}],
  "needs_response": [{{"source": "slack|gmail", "summary": "...", "age": "...", "has_draft": true}}],
  "alerts": [{{"summary": "...", "urgency": "high|medium|low"}}],
  "sprint_status": {{"in_progress": 0, "todo": 0, "done": 0, "blockers": []}},
  "cognitive_load": {{"level": "LOW|MODERATE|HIGH|OVERLOADED", "meeting_count": 0, "action_count": 0, "deep_work_window": "HH:MM-HH:MM", "heaviest_block": "HH:MM-HH:MM"}},
  "stats": {{"drafts_sent": 0, "cards_triaged": 0, "time_saved_min": 0, "week_total_triaged": 0}},
  "heads_up": ["stakeholder waiting...", "SLA deadline...", ...],
  "pep_talk": "Personalized encouragement based on workload and recent velocity."
}}

Return ONLY the JSON. No prose."""

    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "--print", prompt],
            capture_output=True, text=True, timeout=60
        )
        match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
        if match:
            briefing = json.loads(match.group(0))
        else:
            briefing = {"error": "Failed to generate briefing", "raw": result.stdout[:500]}
    except Exception as e:
        briefing = {"error": str(e)}

    # Cache it
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO briefings (date, content, generated_at) VALUES (?, ?, ?)",
            [today, json.dumps(briefing), datetime.now().isoformat()]
        )
        conn.commit()
    finally:
        conn.close()

    return briefing


def _record_stat(metric, value=1, details=None):
    """Record a stat to the stats table."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO stats (date, metric, value, details) VALUES (?, ?, ?, ?)",
            [date.today().isoformat(), metric, value, details]
        )
        conn.commit()
    finally:
        conn.close()
```

**Step 4: Add adaptive filter endpoints**

```python
@app.get("/api/filters/suggestions")
async def get_filter_suggestions():
    """Return pending filter suggestions."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM filter_suggestions WHERE status = 'suggest' ORDER BY ignore_count DESC"
        ).fetchall()
        return {"suggestions": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/filters/create")
async def create_gmail_filter(body: dict):
    """Create a Gmail filter via MCP and record it."""
    pattern = body.get("pattern", "")
    label_name = body.get("label", "")
    suggestion_id = body.get("suggestion_id")

    if not pattern or not label_name:
        raise HTTPException(400, "pattern and label required")

    prompt = (
        f"Use the Gmail MCP. First, use get_or_create_label to ensure label '{label_name}' exists. "
        f"Then use create_filter with criteria matching from:{pattern}, "
        f"and action to add label '{label_name}' and skip inbox (removeLabelIds: ['INBOX']). "
        f"Return the filter ID."
    )
    result = subprocess.run(
        ["claude", "--dangerously-skip-permissions", "--print", prompt],
        capture_output=True, text=True, timeout=30
    )

    if suggestion_id:
        conn = get_db()
        conn.execute(
            "UPDATE filter_suggestions SET status = 'created' WHERE id = ?",
            [suggestion_id]
        )
        conn.commit()
        conn.close()

    _record_stat("filters_created")
    return {"status": "created", "output": result.stdout[:500]}


@app.post("/api/filters/dismiss")
async def dismiss_filter_suggestion(body: dict):
    """Dismiss a filter suggestion."""
    suggestion_id = body.get("suggestion_id")
    permanent = body.get("permanent", False)
    conn = get_db()
    status = "never" if permanent else "dismissed"
    conn.execute(
        "UPDATE filter_suggestions SET status = ? WHERE id = ?",
        [status, suggestion_id]
    )
    conn.commit()
    conn.close()
    return {"status": status}
```

**Step 5: Add card dismiss endpoint**

```python
@app.post("/api/cards/{card_id}/dismiss")
async def dismiss_card(card_id: int):
    """Move card to no-action section."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE cards SET section = 'no-action' WHERE id = ?", [card_id]
        )
        conn.commit()

        # Track for adaptive filtering
        row = conn.execute("SELECT source, summary FROM cards WHERE id = ?", [card_id]).fetchone()
        if row and row[0] == "gmail":
            _track_ignored_pattern(conn, row[1])

        return {"id": card_id, "section": "no-action"}
    finally:
        conn.close()


def _track_ignored_pattern(conn, summary):
    """Increment ignore count for sender pattern."""
    # Extract sender from summary (format: "Sender: Subject")
    sender = summary.split(":")[0].strip() if ":" in summary else summary[:50]
    row = conn.execute(
        "SELECT id, ignore_count FROM filter_suggestions WHERE pattern = ? AND status IN ('tracking', 'suggest')",
        [sender]
    ).fetchone()
    if row:
        new_count = row[1] + 1
        status = "suggest" if new_count >= 10 else "tracking"
        conn.execute(
            "UPDATE filter_suggestions SET ignore_count = ?, status = ?, suggested_at = CASE WHEN ? = 'suggest' THEN datetime('now') ELSE suggested_at END WHERE id = ?",
            [new_count, status, status, row[0]]
        )
    else:
        conn.execute(
            "INSERT INTO filter_suggestions (source, pattern, ignore_count, status) VALUES ('gmail', ?, 1, 'tracking')",
            [sender]
        )
    conn.commit()
```

**Step 6: Commit**

```bash
git add dashboard/server.py
git commit -m "Add smart card APIs: section filtering, send drafts, briefing, adaptive filters"
```

---

## Task 7: Dashboard Frontend — Tab Layouts

**Files:**
- Modify: `dashboard/static/index.html`
- Rewrite: `dashboard/static/app.js`
- Modify: `dashboard/static/style.css`

**Step 1: Update index.html — add briefing modal container**

Add before `</body>`:

```html
<div id="briefing-overlay" class="briefing-overlay" style="display:none;">
  <div class="briefing-modal" id="briefing-content"></div>
</div>
```

**Step 2: Update app.js — two-section rendering + briefing**

Key additions to app.js:

1. `renderTwoSectionView(cards, source)` — splits cards by section, renders two collapsible groups
2. `renderSlackCard(card)` — card with SEND DRAFT / REFINE / DISMISS buttons
3. `renderGmailCard(card)` — card with SEND DRAFT / OPEN IN GMAIL / ACK / DISMISS
4. `renderCalendarView(cards)` — agenda timeline with JOIN / PREP NOTES
5. `renderFilterSuggestion(suggestion)` — CREATE FILTER / NOT NOW / NEVER
6. `loadBriefing()` — fetches and renders morning briefing modal
7. `sendDraft(id, type)` — POST to send-slack or send-email
8. `dismissCard(id)` — POST to dismiss
9. `createFilter(suggestionId, pattern, label)` — POST to create filter
10. Tab handlers updated: Slack/Gmail load two-section view, Calendar loads agenda, Jira loads sprint board

For the Slack tab filter button handler:
```javascript
if (activeFilter === 'slack') {
    loadTwoSectionView('slack');
} else if (activeFilter === 'gmail') {
    loadTwoSectionView('gmail');
} else if (activeFilter === 'calendar') {
    loadCalendarView();
} else if (activeFilter === 'jira') {
    loadSprintBoard();
} else {
    loadQueue(activeFilter);
}
```

`loadTwoSectionView(source)`:
```javascript
async function loadTwoSectionView(source) {
    const queue = document.getElementById('queue');
    queue.innerHTML = '<div style="color:#666;padding:40px;text-align:center;letter-spacing:4px">LOADING...</div>';

    const [needsR, noActionR, suggestionsR] = await Promise.all([
        fetch(`/api/cards?source=${source}&section=needs-action`),
        fetch(`/api/cards?source=${source}&section=no-action`),
        source === 'gmail' ? fetch('/api/filters/suggestions') : Promise.resolve(null),
    ]);

    const needs = await needsR.json();
    const noAction = await noActionR.json();
    const suggestions = suggestionsR ? await suggestionsR.json() : {suggestions: []};

    const needsHtml = needs.cards.map(c => renderSmartCard(c, source)).join('') || '<div class="section-empty">All clear</div>';
    const noActionHtml = noAction.cards.map(c => renderSmartCard(c, source)).join('') || '<div class="section-empty">Nothing here</div>';

    let suggestionsHtml = '';
    if (suggestions.suggestions.length) {
        suggestionsHtml = suggestions.suggestions.map(renderFilterSuggestion).join('');
    }

    queue.innerHTML = `
        <div class="section-group">
            <div class="section-header" onclick="toggleSection('needs')">
                <span>NEEDS ACTION / UNREAD</span>
                <span class="section-count">${needs.cards.length}</span>
                <span class="section-toggle" id="toggle-needs">▼</span>
            </div>
            <div class="section-body" id="section-needs">${needsHtml}</div>
        </div>
        <div class="section-group">
            <div class="section-header no-action" onclick="toggleSection('noaction')">
                <span>RESPONDED / NO ACTION</span>
                <span class="section-count">${noAction.cards.length}</span>
                <span class="section-toggle" id="toggle-noaction">▼</span>
            </div>
            <div class="section-body" id="section-noaction">${noActionHtml}</div>
        </div>
        ${suggestionsHtml}
    `;
}
```

**Step 3: Update style.css — two-section layout + briefing modal + calendar agenda**

Add section styles, briefing overlay/modal, calendar agenda timeline, filter suggestion card styles. See design doc Section 2-5 for visual spec.

**Step 4: Commit**

```bash
git add dashboard/static/index.html dashboard/static/app.js dashboard/static/style.css
git commit -m "Add two-section dashboard tabs, briefing modal, and calendar agenda view"
```

---

## Task 8: Morning Briefing — Auto-Show on First Load

**Files:**
- Modify: `dashboard/static/app.js` (init section)

**Step 1: Add briefing auto-load to init**

```javascript
// -- Init --
async function init() {
    loadQueue();
    connectSSE();
    loadTerminalSetting();

    // Show briefing on first load of the day
    const today = new Date().toISOString().slice(0, 10);
    const lastBriefing = localStorage.getItem('eng-buddy-last-briefing');
    if (lastBriefing !== today) {
        await loadBriefing();
        localStorage.setItem('eng-buddy-last-briefing', today);
    }
}

async function loadBriefing() {
    const overlay = document.getElementById('briefing-overlay');
    const content = document.getElementById('briefing-content');
    overlay.style.display = 'flex';
    content.innerHTML = '<div style="color:#666;padding:40px;text-align:center;letter-spacing:4px">GENERATING BRIEFING...</div>';

    try {
        const r = await fetch('/api/briefing');
        const data = await r.json();
        content.innerHTML = renderBriefing(data);
    } catch (e) {
        content.innerHTML = `<div style="color:#ea4335;padding:40px;">Briefing failed: ${e.message}</div>`;
    }
}

function dismissBriefing() {
    document.getElementById('briefing-overlay').style.display = 'none';
}
```

**Step 2: Commit**

```bash
git add dashboard/static/app.js
git commit -m "Add morning briefing auto-show on first daily load"
```

---

## Task 9: Integration Testing

**Files:**
- Modify: `dashboard/tests/test_server.py`

**Step 1: Add tests for new endpoints**

Test cases:
- `test_get_cards_with_section_filter` — verify section param works
- `test_dismiss_card` — verify card moves to no-action
- `test_briefing_caching` — verify briefing is generated then cached
- `test_filter_suggestion_tracking` — verify ignore_count increments
- `test_filter_suggestion_triggers_at_10` — verify status changes to suggest
- `test_migration_idempotent` — verify migrate.py runs twice without error

**Step 2: Run tests**

```bash
cd ~/.claude/skills/eng-buddy/dashboard && pip install pytest httpx && python -m pytest tests/ -v
```

**Step 3: Commit**

```bash
git add dashboard/tests/test_server.py
git commit -m "Add integration tests for smart poller endpoints"
```

---

## Task 10: Sync, Push, and Install LaunchAgents

**Step 1: Sync to runtime workspace**

```bash
cp -r ~/.claude/skills/eng-buddy/bin/* ~/.claude/eng-buddy/bin/
cp -r ~/.claude/skills/eng-buddy/dashboard/* ~/.claude/eng-buddy/dashboard/
cp -r ~/.claude/skills/eng-buddy/memory/* ~/.claude/eng-buddy/memory/ 2>/dev/null || true
```

**Step 2: Install new LaunchAgent**

```bash
cp ~/.claude/skills/eng-buddy/bin/com.engbuddy.calendarpoller.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.engbuddy.calendarpoller.plist
```

**Step 3: Reload existing LaunchAgents (updated intervals)**

```bash
launchctl unload ~/Library/LaunchAgents/com.engbuddy.slackpoller.plist 2>/dev/null
cp ~/.claude/skills/eng-buddy/bin/com.engbuddy.slackpoller.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.engbuddy.slackpoller.plist
```

**Step 4: Push to GitHub**

```bash
cd ~/.claude/skills/eng-buddy && ghp && git push origin main
```

---

## Dependency Graph

```
Task 1 (DB migration) ──┐
                         ├──> Task 3 (Slack poller)  ──┐
Task 2 (brain.py)    ───┤                              │
                         ├──> Task 4 (Gmail poller)  ──┤──> Task 7 (Frontend) ──> Task 8 (Briefing) ──> Task 9 (Tests) ──> Task 10 (Deploy)
                         ├──> Task 5 (Calendar poller)─┤
                         └──> Task 6 (Server APIs)  ───┘
```

**Parallelizable:**
- Tasks 1 + 2 (no deps, can run together)
- Tasks 3 + 4 + 5 (all depend on 1+2 but independent of each other)
- Task 6 can start after 1, parallel with 3-5
- Task 7 needs 6 done
- Tasks 8-10 are sequential
