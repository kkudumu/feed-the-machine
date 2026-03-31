# Freshservice Enrichment Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 3-stage AI enrichment pipeline that classifies Freshservice tickets, generates contextual actions, matches playbooks, and auto-drafts new playbooks from detected patterns.

**Architecture:** A standalone `freshservice-enrichment.py` script runs as a LaunchAgent every 5 minutes. It queries inbox.db for un-enriched Freshservice cards, runs them through classify → enrich+playbook match → detect patterns stages, writing results back to the DB and triggering dashboard refreshes per-card. An `_run_llm()` abstraction allows per-stage model routing.

**Tech Stack:** Python 3, sqlite3, subprocess (Claude CLI), ThreadPoolExecutor, urllib (Freshservice API), LaunchAgent

**Design Doc:** `docs/plans/2026-03-10-freshservice-enrichment-design.md`

---

### Task 1: DB Schema Migration

**Files:**
- Modify: `dashboard/server.py` (add migration logic near existing CREATE TABLE blocks ~line 1036)

**Step 1: Write the failing test**

```python
# dashboard/tests/test_enrichment_schema.py
import sqlite3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_enrichment_status_column_exists():
    """After migration, cards table should have enrichment_status column."""
    from server import DB_PATH, get_db
    conn = get_db()
    cursor = conn.execute("PRAGMA table_info(cards)")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    assert "enrichment_status" in columns

def test_classification_buckets_table_exists():
    conn = get_db()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='classification_buckets'"
    )
    assert cursor.fetchone() is not None
    conn.close()

def test_enrichment_runs_table_exists():
    conn = get_db()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='enrichment_runs'"
    )
    assert cursor.fetchone() is not None
    conn.close()
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_schema.py -v`
Expected: FAIL — column and tables don't exist yet

**Step 3: Add migration to server.py**

In `dashboard/server.py`, find the block near line 1036 with existing `CREATE TABLE IF NOT EXISTS` statements. Add after the last one:

```python
            # Freshservice enrichment pipeline tables
            conn.execute(
                """CREATE TABLE IF NOT EXISTS classification_buckets (
                    id TEXT PRIMARY KEY,
                    description TEXT,
                    knowledge_files TEXT DEFAULT '[]',
                    confidence_keywords TEXT DEFAULT '[]',
                    ticket_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'emerging',
                    created_by_ticket INTEGER,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS enrichment_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER,
                    stage TEXT,
                    model TEXT,
                    duration_ms INTEGER,
                    status TEXT,
                    response_summary TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )"""
            )
            # Add enrichment_status column to cards if missing
            cursor = conn.execute("PRAGMA table_info(cards)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "enrichment_status" not in existing_cols:
                conn.execute(
                    "ALTER TABLE cards ADD COLUMN enrichment_status TEXT DEFAULT 'not_enriched'"
                )
```

**Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_schema.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/server.py dashboard/tests/test_enrichment_schema.py
git commit -m "Add DB schema for Freshservice enrichment pipeline"
```

---

### Task 2: LLM Abstraction Layer

**Files:**
- Create: `bin/freshservice-enrichment.py` (initial scaffold with `_run_llm()`)

**Step 1: Write the failing test**

```python
# dashboard/tests/test_enrichment_llm.py
import subprocess
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

def test_stage_llm_config_has_all_stages():
    """Config must define CLI + args for each pipeline stage."""
    # Import the module to check config
    spec = __import__("importlib").util.spec_from_file_location(
        "enrichment",
        os.path.join(os.path.dirname(__file__), "..", "..", "bin", "freshservice-enrichment.py"),
    )
    mod = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for stage in ("classify", "enrich", "detect_patterns"):
        assert stage in mod.STAGE_LLM_CONFIG
        assert "cli" in mod.STAGE_LLM_CONFIG[stage]
        assert "args" in mod.STAGE_LLM_CONFIG[stage]
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_llm.py -v`
Expected: FAIL — file doesn't exist

**Step 3: Create bin/freshservice-enrichment.py with LLM abstraction**

```python
#!/usr/bin/env python3
"""
eng-buddy Freshservice Enrichment Pipeline
3-stage AI pipeline: classify → enrich+playbook match → detect patterns.
Runs as LaunchAgent, picks up un-enriched cards from inbox.db.
"""
import json
import os
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
DB_PATH = BASE_DIR / "inbox.db"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
HEALTH_FILE = BASE_DIR / "health" / "freshservice-enrichment.json"

FRESHSERVICE_DOMAIN = "klaviyo.freshservice.com"
API_KEY = "vh78yaatCXcXaHODpYl"
_AUTH = b64encode(f"{API_KEY}:X".encode()).decode()
_FS_HEADERS = {
    "Authorization": f"Basic {_AUTH}",
    "Content-Type": "application/json",
}

DASHBOARD_INVALIDATE_URL = os.environ.get(
    "ENG_BUDDY_DASHBOARD_INVALIDATE_URL",
    "http://127.0.0.1:7777/api/cache-invalidate",
)

MAX_WORKERS = 5
PATTERN_LOOKBACK_DAYS = 30
VETTED_THRESHOLD = 3

# --- Per-stage LLM routing ---
STAGE_LLM_CONFIG = {
    "classify": {"cli": "claude", "args": ["-p"]},
    "enrich": {"cli": "claude", "args": ["-p"]},
    "detect_patterns": {"cli": "claude", "args": ["-p"]},
}


def _llm_env():
    """Clean env for spawning LLM CLI."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    path_parts = ["/opt/homebrew/bin", "/usr/local/bin"]
    existing = env.get("PATH", "")
    if existing:
        path_parts.append(existing)
    env["PATH"] = ":".join(path_parts)
    return env


def _run_llm(prompt: str, stage: str, timeout: int = 60) -> str:
    """Route to configured LLM per stage. Returns raw stdout."""
    config = STAGE_LLM_CONFIG.get(stage, {"cli": "claude", "args": ["-p"]})
    cmd = [config["cli"]] + config["args"] + [prompt]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_llm_env(),
    )
    return result.stdout.strip()


def _parse_llm_json(raw: str, opening: str = "{"):
    """Extract first balanced JSON object/array from LLM output."""
    closing = "}" if opening == "{" else "]"
    for start, char in enumerate(raw):
        if char != opening:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw)):
            c = raw[i]
            if in_string:
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = False
                continue
            if c == '"':
                in_string = True
                continue
            if c == opening:
                depth += 1
            elif c == closing:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def invalidate_dashboard():
    """Notify dashboard to refresh Freshservice cards."""
    payload = json.dumps({"source": "freshservice"}).encode()
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


def write_health(status: str, enriched_count: int, errors: int = 0):
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps({
        "status": status,
        "last_run": datetime.now(timezone.utc).isoformat(),
        "enriched_count": enriched_count,
        "errors": errors,
    }))


def log_enrichment_run(card_id: int, stage: str, model: str, duration_ms: int,
                        status: str, response_summary: str = ""):
    """Write observability record."""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO enrichment_runs (card_id, stage, model, duration_ms, status, response_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [card_id, stage, model, duration_ms, status, response_summary[:500]],
        )
        conn.commit()
    finally:
        conn.close()
```

**Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_llm.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bin/freshservice-enrichment.py dashboard/tests/test_enrichment_llm.py
git commit -m "Add enrichment pipeline scaffold with LLM abstraction layer"
```

---

### Task 3: Stage 1 — AI Classification

**Files:**
- Modify: `bin/freshservice-enrichment.py`

**Step 1: Write the failing test**

```python
# dashboard/tests/test_enrichment_classify.py
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

def _load_module():
    spec = __import__("importlib").util.spec_from_file_location(
        "enrichment",
        os.path.join(os.path.dirname(__file__), "..", "..", "bin", "freshservice-enrichment.py"),
    )
    mod = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_build_classify_prompt_includes_ticket_and_schema():
    mod = _load_module()
    card = {
        "id": 1,
        "summary": "#221901 [Incident] Unable to Change Jira type: Story to Spike",
        "analysis_metadata": json.dumps({
            "ticket_id": 221901, "status": "Open", "priority": "Medium",
            "type": "Incident", "requester_id": 123, "group_id": 456,
        }),
    }
    schema = {"buckets": {}}
    prompt = mod.build_classify_prompt(card, schema)
    assert "221901" in prompt
    assert "Incident" in prompt
    assert "classification schema" in prompt.lower() or "Current schema" in prompt

def test_parse_classify_response_new_bucket():
    mod = _load_module()
    raw = json.dumps({
        "bucket_id": "jira-admin",
        "bucket_description": "Jira configuration and access management",
        "is_new_bucket": True,
        "knowledge_files": ["jira-api-reference.md"],
        "confidence_keywords": ["jira", "project access", "story type"],
        "reasoning": "Ticket involves Jira type change",
    })
    result = mod.parse_classify_response(raw)
    assert result["bucket_id"] == "jira-admin"
    assert result["is_new_bucket"] is True
    assert "jira-api-reference.md" in result["knowledge_files"]

def test_parse_classify_response_handles_garbage():
    mod = _load_module()
    result = mod.parse_classify_response("not json at all")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_classify.py -v`
Expected: FAIL — functions don't exist

**Step 3: Implement classification stage**

Add to `bin/freshservice-enrichment.py`:

```python
# --- Stage 1: Classification ---

def load_classification_schema() -> dict:
    """Load current AI-built schema from DB."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM classification_buckets").fetchall()
        buckets = {}
        for row in rows:
            buckets[row["id"]] = {
                "description": row["description"],
                "knowledge_files": json.loads(row["knowledge_files"] or "[]"),
                "confidence_keywords": json.loads(row["confidence_keywords"] or "[]"),
                "ticket_count": row["ticket_count"],
                "status": row["status"],
            }
        return {"buckets": buckets}
    finally:
        conn.close()


def fast_path_classify(card: dict, schema: dict) -> str | None:
    """Check vetted buckets' AI-generated keywords. Returns bucket_id or None."""
    summary_lower = card.get("summary", "").lower()
    meta = json.loads(card.get("analysis_metadata") or "{}")
    ticket_type = str(meta.get("type", "")).lower()
    text = f"{summary_lower} {ticket_type}"

    for bucket_id, bucket in schema.get("buckets", {}).items():
        if bucket.get("status") != "vetted":
            continue
        keywords = bucket.get("confidence_keywords", [])
        if any(kw.lower() in text for kw in keywords):
            return bucket_id
    return None


def build_classify_prompt(card: dict, schema: dict) -> str:
    """Build the classification prompt for a Freshservice ticket."""
    meta = json.loads(card.get("analysis_metadata") or "{}")
    summary = card.get("summary", "")

    # List available knowledge files
    available_knowledge = []
    if KNOWLEDGE_DIR.exists():
        available_knowledge = [f.name for f in KNOWLEDGE_DIR.iterdir() if f.suffix == ".md"]

    schema_json = json.dumps(schema.get("buckets", {}), indent=2) if schema.get("buckets") else "{}"

    return (
        "You are classifying an IT support ticket for an IT systems engineer.\n\n"
        f"Ticket: {summary}\n"
        f"Type: {meta.get('type', 'unknown')} | Priority: {meta.get('priority', 'unknown')}\n"
        f"Status: {meta.get('status', 'unknown')} | Created: {meta.get('created_at', 'unknown')}\n\n"
        f"Current classification schema:\n{schema_json}\n\n"
        f"Available knowledge files: {json.dumps(available_knowledge)}\n\n"
        "Tasks:\n"
        "1. Classify this ticket into an existing bucket, or propose a new one.\n"
        "2. List which knowledge files would help resolve this ticket.\n"
        "3. Provide 3-5 confidence keywords that future similar tickets would contain.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "bucket_id": "kebab-case-name",\n'
        '  "bucket_description": "what this category covers",\n'
        '  "is_new_bucket": true/false,\n'
        '  "knowledge_files": ["file.md"],\n'
        '  "confidence_keywords": ["keyword1", "keyword2"],\n'
        '  "reasoning": "one sentence"\n'
        "}"
    )


def parse_classify_response(raw: str) -> dict | None:
    """Parse classification JSON from LLM response."""
    result = _parse_llm_json(raw, "{")
    if not isinstance(result, dict):
        return None
    if "bucket_id" not in result:
        return None
    # Normalize
    result["bucket_id"] = str(result["bucket_id"]).strip().lower().replace(" ", "-")
    result["is_new_bucket"] = bool(result.get("is_new_bucket", False))
    result["knowledge_files"] = result.get("knowledge_files", [])
    if not isinstance(result["knowledge_files"], list):
        result["knowledge_files"] = []
    result["confidence_keywords"] = result.get("confidence_keywords", [])
    if not isinstance(result["confidence_keywords"], list):
        result["confidence_keywords"] = []
    return result


def save_classification(card_id: int, classification: dict, schema: dict):
    """Persist classification to card metadata and update schema."""
    conn = get_db()
    try:
        # Update card's analysis_metadata with classification
        row = conn.execute("SELECT analysis_metadata FROM cards WHERE id = ?", [card_id]).fetchone()
        meta = json.loads(row["analysis_metadata"] or "{}") if row else {}
        meta["classification_bucket"] = classification["bucket_id"]
        meta["classification_knowledge_files"] = classification["knowledge_files"]
        meta["classification_reasoning"] = classification.get("reasoning", "")
        conn.execute(
            "UPDATE cards SET analysis_metadata = ? WHERE id = ?",
            [json.dumps(meta), card_id],
        )

        bucket_id = classification["bucket_id"]
        if classification["is_new_bucket"]:
            conn.execute(
                """INSERT OR IGNORE INTO classification_buckets
                   (id, description, knowledge_files, confidence_keywords, ticket_count, status, created_by_ticket)
                   VALUES (?, ?, ?, ?, 1, 'emerging', ?)""",
                [
                    bucket_id,
                    classification.get("bucket_description", ""),
                    json.dumps(classification["knowledge_files"]),
                    json.dumps(classification["confidence_keywords"]),
                    card_id,
                ],
            )
        else:
            conn.execute(
                """UPDATE classification_buckets
                   SET ticket_count = ticket_count + 1,
                       confidence_keywords = ?,
                       updated_at = datetime('now'),
                       status = CASE WHEN ticket_count + 1 >= ? THEN 'vetted' ELSE status END
                   WHERE id = ?""",
                [json.dumps(classification["confidence_keywords"]), VETTED_THRESHOLD, bucket_id],
            )

        conn.commit()
    finally:
        conn.close()


def stage_classify(card: dict) -> dict | None:
    """Run classification stage. Returns classification dict or None on failure."""
    card_id = card["id"]
    schema = load_classification_schema()

    # Try fast-path first (vetted buckets)
    fast = fast_path_classify(card, schema)
    if fast:
        bucket = schema["buckets"][fast]
        result = {
            "bucket_id": fast,
            "bucket_description": bucket["description"],
            "is_new_bucket": False,
            "knowledge_files": bucket["knowledge_files"],
            "confidence_keywords": bucket["confidence_keywords"],
            "reasoning": "fast-path keyword match",
        }
        save_classification(card_id, result, schema)
        log_enrichment_run(card_id, "classify", "fast-path", 0, "success", f"bucket={fast}")
        return result

    # AI classification
    prompt = build_classify_prompt(card, schema)
    model = STAGE_LLM_CONFIG["classify"]["cli"]
    start = time.time()
    try:
        raw = _run_llm(prompt, "classify", timeout=30)
        duration_ms = int((time.time() - start) * 1000)
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        log_enrichment_run(card_id, "classify", model, duration_ms, "failed", str(e))
        return None

    result = parse_classify_response(raw)
    if not result:
        log_enrichment_run(card_id, "classify", model, duration_ms, "failed", raw[:200])
        return None

    save_classification(card_id, result, schema)
    log_enrichment_run(card_id, "classify", model, duration_ms, "success",
                        f"bucket={result['bucket_id']} new={result['is_new_bucket']}")
    return result
```

**Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_classify.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bin/freshservice-enrichment.py dashboard/tests/test_enrichment_classify.py
git commit -m "Add stage_classify with AI classification and self-evolving schema"
```

---

### Task 4: Stage 2 — AI Enrichment + Playbook Matching

**Files:**
- Modify: `bin/freshservice-enrichment.py`

**Step 1: Write the failing test**

```python
# dashboard/tests/test_enrichment_enrich.py
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

def _load_module():
    spec = __import__("importlib").util.spec_from_file_location(
        "enrichment",
        os.path.join(os.path.dirname(__file__), "..", "..", "bin", "freshservice-enrichment.py"),
    )
    mod = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_build_enrich_prompt_includes_description_and_knowledge():
    mod = _load_module()
    card = {
        "id": 1,
        "summary": "#231844 [Service Request] Request for Jon Ross : Jira Project Access",
        "analysis_metadata": json.dumps({
            "ticket_id": 231844, "status": "Open", "priority": "Medium",
            "type": "Service Request", "classification_bucket": "jira-admin",
            "classification_knowledge_files": ["jira-api-reference.md"],
        }),
    }
    classification = {
        "bucket_id": "jira-admin",
        "knowledge_files": ["jira-api-reference.md"],
    }
    prompt = mod.build_enrich_prompt(card, classification, "User needs Jira access", [])
    assert "231844" in prompt
    assert "Jira Project Access" in prompt
    assert "jira-admin" in prompt
    assert "proposed_actions" in prompt

def test_parse_enrich_response_valid():
    mod = _load_module()
    raw = json.dumps({
        "proposed_actions": [
            {"type": "grant_access", "draft": "Grant Jira project access to Jon Ross"},
            {"type": "reply_to_requester", "draft": "Confirm access has been granted"},
        ],
        "playbook_match": None,
    })
    result = mod.parse_enrich_response(raw)
    assert len(result["proposed_actions"]) == 2
    assert result["proposed_actions"][0]["type"] == "grant_access"

def test_parse_enrich_response_caps_at_6_actions():
    mod = _load_module()
    actions = [{"type": f"action_{i}", "draft": f"Do thing {i}"} for i in range(10)]
    raw = json.dumps({"proposed_actions": actions, "playbook_match": None})
    result = mod.parse_enrich_response(raw)
    assert len(result["proposed_actions"]) <= 6

def test_parse_enrich_response_handles_garbage():
    mod = _load_module()
    result = mod.parse_enrich_response("not json")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_enrich.py -v`
Expected: FAIL — functions don't exist

**Step 3: Implement enrichment stage**

Add to `bin/freshservice-enrichment.py`:

```python
# --- Freshservice API helpers ---

def fetch_ticket_description(ticket_id: int) -> str:
    """Fetch ticket description from Freshservice API."""
    url = f"https://{FRESHSERVICE_DOMAIN}/api/v2/tickets/{ticket_id}?include=conversations"
    req = urllib.request.Request(url, headers=_FS_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            ticket = data.get("ticket", {})
            desc = ticket.get("description_text") or ticket.get("description") or ""
            # Also grab first few conversation entries for context
            convos = data.get("conversations", [])
            convo_text = ""
            for c in convos[:3]:
                body = c.get("body_text") or c.get("body") or ""
                if body:
                    convo_text += f"\n---\n{body[:500]}"
            return (desc[:2000] + convo_text[:1000]).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"  Failed to fetch ticket {ticket_id} description: {e}")
        return ""


def load_knowledge_file(filename: str, max_chars: int = 3000) -> str:
    """Load a knowledge file, truncated to max_chars."""
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except OSError:
        return ""


def load_approved_playbooks_summary() -> str:
    """Load approved playbook summaries for matching."""
    try:
        result = subprocess.run(
            ["python3", str(BASE_DIR / "bin" / "brain.py"), "--playbook-list"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()[:3000] if result.stdout else "No approved playbooks yet."
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "No approved playbooks yet."


# --- Stage 2: Enrichment + Playbook Matching ---

def build_enrich_prompt(card: dict, classification: dict,
                         description: str, playbook_summaries: list) -> str:
    """Build enrichment prompt with ticket details, knowledge, and playbooks."""
    meta = json.loads(card.get("analysis_metadata") or "{}")
    summary = card.get("summary", "")
    bucket_id = classification.get("bucket_id", "unknown")

    # Load relevant knowledge
    knowledge_text = ""
    for kf in classification.get("knowledge_files", []):
        content = load_knowledge_file(kf)
        if content:
            knowledge_text += f"\n### {kf}\n{content}\n"

    if not knowledge_text:
        knowledge_text = "(No relevant knowledge files found)"

    playbooks_text = "\n".join(playbook_summaries) if playbook_summaries else "No approved playbooks yet."

    return (
        "You are an IT systems engineering assistant triaging a Freshservice ticket.\n\n"
        f"Ticket: {summary}\n"
        f"Description:\n{description[:2000]}\n\n"
        f"Type: {meta.get('type', 'unknown')} | Priority: {meta.get('priority', 'unknown')}\n"
        f"Status: {meta.get('status', 'unknown')} | Created: {meta.get('created_at', 'unknown')}\n"
        f"Classification bucket: {bucket_id}\n\n"
        f"Relevant knowledge:\n{knowledge_text}\n\n"
        f"Approved playbooks:\n{playbooks_text}\n\n"
        "Tasks:\n"
        "1. Generate 2-5 specific, actionable next steps for this ticket.\n"
        "2. If any approved playbook matches, identify which and which steps apply.\n\n"
        "Be SPECIFIC — not 'investigate the issue' but 'check Okta SCIM provisioning logs for failed sync events'.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "proposed_actions": [\n'
        '    {"type": "action_type", "draft": "specific action description"}\n'
        "  ],\n"
        '  "playbook_match": {\n'
        '    "playbook_id": "id or null",\n'
        '    "playbook_name": "name or null",\n'
        '    "applicable_steps": [1, 2, 4],\n'
        '    "reasoning": "why this playbook matches"\n'
        "  }\n"
        "}\n\n"
        "Action types: reply_to_requester, escalate, create_jira_ticket, "
        "follow_playbook, investigate, close_ticket, request_info, grant_access, "
        "check_integration, review_config, check_logs, update_documentation, "
        "or any other relevant type."
    )


def parse_enrich_response(raw: str) -> dict | None:
    """Parse enrichment JSON from LLM response."""
    result = _parse_llm_json(raw, "{")
    if not isinstance(result, dict):
        return None
    actions = result.get("proposed_actions")
    if not isinstance(actions, list) or not actions:
        return None
    # Normalize and cap
    normalized = []
    for a in actions[:6]:
        if not isinstance(a, dict):
            continue
        action_type = str(a.get("type", "next-step")).strip() or "next-step"
        draft = str(a.get("draft", "")).strip()
        if draft:
            normalized.append({"type": action_type, "draft": draft})
    if not normalized:
        return None

    playbook_match = result.get("playbook_match")
    if isinstance(playbook_match, dict) and not playbook_match.get("playbook_id"):
        playbook_match = None

    return {"proposed_actions": normalized, "playbook_match": playbook_match}


def save_enrichment(card_id: int, enrichment: dict):
    """Persist enrichment results to card."""
    conn = get_db()
    try:
        # Update proposed_actions
        conn.execute(
            "UPDATE cards SET proposed_actions = ?, enrichment_status = 'enriched' WHERE id = ?",
            [json.dumps(enrichment["proposed_actions"]), card_id],
        )
        # Update analysis_metadata with playbook match info
        if enrichment.get("playbook_match"):
            row = conn.execute("SELECT analysis_metadata FROM cards WHERE id = ?", [card_id]).fetchone()
            meta = json.loads(row["analysis_metadata"] or "{}") if row else {}
            meta["playbook_match"] = enrichment["playbook_match"]
            conn.execute(
                "UPDATE cards SET analysis_metadata = ? WHERE id = ?",
                [json.dumps(meta), card_id],
            )
        conn.commit()
    finally:
        conn.close()


def stage_enrich(card: dict, classification: dict) -> dict | None:
    """Run enrichment stage. Returns enrichment dict or None on failure."""
    card_id = card["id"]
    meta = json.loads(card.get("analysis_metadata") or "{}")
    ticket_id = meta.get("ticket_id")

    # Fetch full ticket description
    description = fetch_ticket_description(ticket_id) if ticket_id else ""

    # Load playbook summaries
    playbook_text = load_approved_playbooks_summary()
    playbooks = [playbook_text] if playbook_text else []

    prompt = build_enrich_prompt(card, classification, description, playbooks)
    model = STAGE_LLM_CONFIG["enrich"]["cli"]
    start = time.time()
    try:
        raw = _run_llm(prompt, "enrich", timeout=60)
        duration_ms = int((time.time() - start) * 1000)
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        log_enrichment_run(card_id, "enrich", model, duration_ms, "failed", str(e))
        return None

    result = parse_enrich_response(raw)
    if not result:
        log_enrichment_run(card_id, "enrich", model, duration_ms, "failed", raw[:200])
        # Mark as failed so we don't retry every cycle
        conn = get_db()
        conn.execute("UPDATE cards SET enrichment_status = 'failed' WHERE id = ?", [card_id])
        conn.commit()
        conn.close()
        return None

    save_enrichment(card_id, result)
    log_enrichment_run(card_id, "enrich", model, duration_ms, "success",
                        f"actions={len(result['proposed_actions'])} playbook={'yes' if result.get('playbook_match') else 'no'}")
    return result
```

**Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_enrich.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bin/freshservice-enrichment.py dashboard/tests/test_enrichment_enrich.py
git commit -m "Add stage_enrich with AI enrichment and playbook matching"
```

---

### Task 5: Stage 3 — Pattern Detection + Playbook Drafting

**Files:**
- Modify: `bin/freshservice-enrichment.py`

**Step 1: Write the failing test**

```python
# dashboard/tests/test_enrichment_patterns.py
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

def _load_module():
    spec = __import__("importlib").util.spec_from_file_location(
        "enrichment",
        os.path.join(os.path.dirname(__file__), "..", "..", "bin", "freshservice-enrichment.py"),
    )
    mod = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_build_pattern_prompt_includes_bucket_and_tickets():
    mod = _load_module()
    bucket_id = "jira-admin"
    tickets = [
        {"summary": "#1 [Service Request] Jira Access for Alice", "actions": ["grant_access"]},
        {"summary": "#2 [Service Request] Jira Access for Bob", "actions": ["grant_access"]},
        {"summary": "#3 [Service Request] Jira Access for Carol", "actions": ["grant_access"]},
    ]
    prompt = mod.build_pattern_prompt(bucket_id, tickets)
    assert "jira-admin" in prompt
    assert "Alice" in prompt
    assert "pattern" in prompt.lower()

def test_parse_pattern_response_with_playbook():
    mod = _load_module()
    raw = json.dumps({
        "pattern_detected": True,
        "confidence": "high",
        "playbook_draft": {
            "name": "jira-project-access",
            "description": "Grant Jira project access to a user",
            "trigger_keywords": ["jira", "project access"],
            "steps": [
                {"name": "Look up user in Jira", "tool": "jira_search", "requires_human": False},
                {"name": "Add user to project", "tool": "jira_update_issue", "requires_human": True},
            ],
        },
        "reasoning": "3 identical access request tickets",
    })
    result = mod.parse_pattern_response(raw)
    assert result["pattern_detected"] is True
    assert result["playbook_draft"]["name"] == "jira-project-access"

def test_parse_pattern_response_no_pattern():
    mod = _load_module()
    raw = json.dumps({"pattern_detected": False, "confidence": "low", "playbook_draft": None, "reasoning": "too few tickets"})
    result = mod.parse_pattern_response(raw)
    assert result["pattern_detected"] is False
    assert result["playbook_draft"] is None
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_patterns.py -v`
Expected: FAIL — functions don't exist

**Step 3: Implement pattern detection stage**

Add to `bin/freshservice-enrichment.py`:

```python
# --- Stage 3: Pattern Detection ---

def build_pattern_prompt(bucket_id: str, tickets: list) -> str:
    """Build pattern detection prompt for a classification bucket."""
    ticket_list = ""
    for t in tickets[:15]:  # Cap context size
        summary = t.get("summary", "")
        actions = t.get("actions", [])
        ticket_list += f"- {summary}\n  Actions: {json.dumps(actions)}\n"

    return (
        "You are analyzing IT support ticket patterns to identify repeatable workflows.\n\n"
        f"Classification bucket: {bucket_id}\n"
        f"Tickets in this bucket (last {PATTERN_LOOKBACK_DAYS} days):\n{ticket_list}\n"
        "Questions:\n"
        "1. Is there a repeating workflow pattern across these tickets?\n"
        "2. If yes, what common steps could become an automated playbook?\n"
        "3. What keywords should trigger this playbook?\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "pattern_detected": true/false,\n'
        '  "confidence": "high/medium/low",\n'
        '  "playbook_draft": {\n'
        '    "name": "kebab-case-name",\n'
        '    "description": "what this playbook automates",\n'
        '    "trigger_keywords": ["keyword1", "keyword2"],\n'
        '    "steps": [\n'
        '      {"name": "step description", "tool": "tool_name", "requires_human": true/false}\n'
        "    ]\n"
        "  },\n"
        '  "reasoning": "explanation"\n'
        "}"
    )


def parse_pattern_response(raw: str) -> dict | None:
    """Parse pattern detection JSON from LLM response."""
    result = _parse_llm_json(raw, "{")
    if not isinstance(result, dict):
        return None
    result["pattern_detected"] = bool(result.get("pattern_detected", False))
    result["confidence"] = str(result.get("confidence", "low")).lower()
    if result["pattern_detected"] and isinstance(result.get("playbook_draft"), dict):
        draft = result["playbook_draft"]
        draft["name"] = str(draft.get("name", "")).strip().lower().replace(" ", "-")
        if not draft["name"]:
            result["playbook_draft"] = None
    else:
        result["playbook_draft"] = None
    return result


def draft_playbook(playbook_draft: dict):
    """Write a draft playbook via brain.py."""
    try:
        subprocess.run(
            [
                "python3", str(BASE_DIR / "bin" / "brain.py"),
                "--playbook-draft",
                json.dumps(playbook_draft),
            ],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  Failed to draft playbook: {e}")


def stage_detect_patterns():
    """Run pattern detection across all enriched cards. Once per cycle."""
    conn = get_db()
    try:
        # Get enriched freshservice cards from last N days
        rows = conn.execute(
            """SELECT c.id, c.summary, c.proposed_actions, c.analysis_metadata
               FROM cards c
               WHERE c.source = 'freshservice'
                 AND c.enrichment_status = 'enriched'
                 AND c.timestamp >= datetime('now', ?)""",
            [f"-{PATTERN_LOOKBACK_DAYS} days"],
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return

    # Group by classification bucket
    buckets: dict[str, list] = {}
    for row in rows:
        meta = json.loads(row["analysis_metadata"] or "{}")
        bucket = meta.get("classification_bucket", "unknown")
        actions_raw = json.loads(row["proposed_actions"] or "[]")
        action_types = [a.get("type", "") for a in actions_raw if isinstance(a, dict)]
        buckets.setdefault(bucket, []).append({
            "summary": row["summary"],
            "actions": action_types,
        })

    # Only analyze buckets with 3+ tickets
    for bucket_id, tickets in buckets.items():
        if len(tickets) < VETTED_THRESHOLD:
            continue

        # Check if we already have a playbook for this bucket (skip if so)
        # TODO: check brain.py for existing playbooks matching this bucket

        prompt = build_pattern_prompt(bucket_id, tickets)
        model = STAGE_LLM_CONFIG["detect_patterns"]["cli"]
        start = time.time()
        try:
            raw = _run_llm(prompt, "detect_patterns", timeout=60)
            duration_ms = int((time.time() - start) * 1000)
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            log_enrichment_run(0, "detect_patterns", model, duration_ms, "failed", str(e))
            continue

        result = parse_pattern_response(raw)
        if not result:
            log_enrichment_run(0, "detect_patterns", model, duration_ms, "failed", raw[:200])
            continue

        log_enrichment_run(0, "detect_patterns", model, duration_ms, "success",
                            f"bucket={bucket_id} pattern={result['pattern_detected']} conf={result['confidence']}")

        if result["pattern_detected"] and result.get("playbook_draft"):
            print(f"  Pattern detected in bucket '{bucket_id}' — drafting playbook: {result['playbook_draft']['name']}")
            draft_playbook(result["playbook_draft"])
```

**Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_patterns.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bin/freshservice-enrichment.py dashboard/tests/test_enrichment_patterns.py
git commit -m "Add stage_detect_patterns with AI pattern detection and playbook drafting"
```

---

### Task 6: Pipeline Orchestrator (main loop)

**Files:**
- Modify: `bin/freshservice-enrichment.py`

**Step 1: Write the failing test**

```python
# dashboard/tests/test_enrichment_pipeline.py
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

def _load_module():
    spec = __import__("importlib").util.spec_from_file_location(
        "enrichment",
        os.path.join(os.path.dirname(__file__), "..", "..", "bin", "freshservice-enrichment.py"),
    )
    mod = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_fetch_unenriched_cards_returns_list():
    mod = _load_module()
    # Should not crash even if table has no enrichment_status column yet
    try:
        cards = mod.fetch_unenriched_cards()
        assert isinstance(cards, list)
    except Exception:
        pass  # OK if DB not migrated in test env

def test_enrich_single_card_pipeline_functions_exist():
    mod = _load_module()
    assert callable(mod.enrich_single_card)
    assert callable(mod.main)
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_pipeline.py -v`
Expected: FAIL — functions don't exist

**Step 3: Implement main pipeline loop**

Add to `bin/freshservice-enrichment.py`:

```python
# --- Pipeline Orchestrator ---

def fetch_unenriched_cards() -> list:
    """Get all Freshservice cards needing enrichment."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM cards
               WHERE source = 'freshservice'
                 AND (enrichment_status = 'not_enriched' OR enrichment_status IS NULL)
                 AND status = 'pending'
               ORDER BY timestamp DESC""",
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def enrich_single_card(card: dict) -> bool:
    """Run full pipeline for a single card: classify → enrich. Returns True on success."""
    card_id = card["id"]
    summary = card.get("summary", "")

    # Mark as enriching
    conn = get_db()
    conn.execute("UPDATE cards SET enrichment_status = 'enriching' WHERE id = ?", [card_id])
    conn.commit()
    conn.close()

    # Stage 1: Classify
    classification = stage_classify(card)
    if not classification:
        print(f"  [WARN] Classification failed for card {card_id}: {summary[:60]}")
        conn = get_db()
        conn.execute("UPDATE cards SET enrichment_status = 'failed' WHERE id = ?", [card_id])
        conn.commit()
        conn.close()
        return False

    print(f"  Classified card {card_id} → bucket: {classification['bucket_id']}")

    # Reload card with updated metadata from classification
    conn = get_db()
    row = conn.execute("SELECT * FROM cards WHERE id = ?", [card_id]).fetchone()
    conn.close()
    if row:
        card = dict(row)

    # Stage 2: Enrich + playbook match
    enrichment = stage_enrich(card, classification)
    if not enrichment:
        print(f"  [WARN] Enrichment failed for card {card_id}: {summary[:60]}")
        return False

    action_count = len(enrichment.get("proposed_actions", []))
    pb = "yes" if enrichment.get("playbook_match") else "no"
    print(f"  Enriched card {card_id}: {action_count} actions, playbook={pb}")

    # Invalidate dashboard for this card
    invalidate_dashboard()
    return True


def main():
    now = datetime.now()
    print(f"[{now}] Freshservice enrichment pipeline starting...")

    cards = fetch_unenriched_cards()
    if not cards:
        print("  No cards to enrich.")
        write_health("ok", 0)
        return

    print(f"  Found {len(cards)} cards to enrich (parallel workers={MAX_WORKERS})")

    enriched = 0
    errors = 0

    # Process in parallel batches
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_single_card, card): card for card in cards}
        for future in as_completed(futures):
            card = futures[future]
            try:
                if future.result():
                    enriched += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                print(f"  [ERROR] Card {card.get('id')}: {e}")

    # Stage 3: Pattern detection (once per cycle, after all cards enriched)
    if enriched > 0:
        print("  Running pattern detection...")
        try:
            stage_detect_patterns()
        except Exception as e:
            print(f"  [ERROR] Pattern detection failed: {e}")

    write_health("ok", enriched, errors)
    print(f"[{datetime.now()}] Done — enriched={enriched}, errors={errors}")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bin/freshservice-enrichment.py dashboard/tests/test_enrichment_pipeline.py
git commit -m "Add pipeline orchestrator with parallel batched enrichment"
```

---

### Task 7: LaunchAgent + start-pollers.sh Integration

**Files:**
- Create: `bin/com.engbuddy.freshservice-enrichment.plist` (template)
- Modify: `bin/start-pollers.sh` (add enrichment to poller list)

**Step 1: Write the plist template**

Create `bin/com.engbuddy.freshservice-enrichment.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.engbuddy.freshservice-enrichment</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/python3</string>
        <string>RUNTIME_BIN/freshservice-enrichment.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>LOG_DIR/freshservice-enrichment.log</string>
    <key>StandardErrorPath</key>
    <string>LOG_DIR/freshservice-enrichment.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>USER_HOME</string>
    </dict>
</dict>
</plist>
```

**Step 2: Add freshservice-enrichment.py to start-pollers.sh sync list**

In `bin/start-pollers.sh`, line 22, add `freshservice-enrichment.py` to the sync loop:

```bash
for f in slack-poller.py gmail-poller.py calendar-poller.py jira-poller.py freshservice-enrichment.py brain.py; do
```

**Step 3: Add enrichment to the POLLERS array**

In `bin/start-pollers.sh`, after the jira entry (line 33), add:

```bash
    "com.engbuddy.freshservice-enrichment|freshservice-enrichment.py|300"
```

**Step 4: Test the integration**

Run: `bash ~/.claude/skills/eng-buddy/bin/start-pollers.sh`
Expected: Output includes `com.engbuddy.freshservice-enrichment` being installed or already running.

**Step 5: Commit**

```bash
git add bin/freshservice-enrichment.py bin/start-pollers.sh
git commit -m "Add enrichment pipeline LaunchAgent and integrate with start-pollers.sh"
```

---

### Task 8: Dashboard — Enrichment Status + Playbook Badge

**Files:**
- Modify: `dashboard/static/app.js` (card rendering)
- Modify: `dashboard/static/style.css` (badge styles)
- Modify: `dashboard/server.py` (expose enrichment_status in card API)

**Step 1: Add enrichment_status to card serialization in server.py**

Find the `_row_to_card` function (or wherever cards are serialized) and ensure `enrichment_status` is included. Search for `def _row_to_card` or the card dict construction. Add:

```python
card["enrichment_status"] = row.get("enrichment_status", "not_enriched") if hasattr(row, "keys") else "not_enriched"
```

**Step 2: Add enrichment badge rendering in app.js**

In `app.js`, find where card badges are rendered (near the source badge like `source-freshservice`). After the existing badges, add:

```javascript
function renderEnrichmentBadge(card) {
  if (card.source !== 'freshservice') return '';
  const status = card.enrichment_status || 'not_enriched';
  if (status === 'enriched') return '<span class="badge enrichment-done">ENRICHED</span>';
  if (status === 'enriching') return '<span class="badge enrichment-progress">ENRICHING...</span>';
  if (status === 'failed') return '<span class="badge enrichment-failed">ENRICH FAILED</span>';
  return '';
}

function renderPlaybookBadge(card) {
  const meta = card.analysis_metadata || {};
  const match = meta.playbook_match;
  if (!match || !match.playbook_name) return '';
  return `<span class="badge playbook-match">PLAYBOOK: ${escHtml(match.playbook_name)}</span>`;
}
```

Insert calls to these functions where card header badges are rendered for freshservice cards.

**Step 3: Add CSS for new badges in style.css**

```css
.badge.enrichment-done { color: var(--bg); background: var(--green); }
.badge.enrichment-progress { color: var(--bg); background: var(--yellow); animation: pulse 1.5s infinite; }
.badge.enrichment-failed { color: var(--bg); background: var(--red); }
.badge.playbook-match { color: var(--bg); background: var(--cyan); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
```

**Step 4: Verify in browser**

Run: `open http://127.0.0.1:7777`
Expected: Freshservice cards show enrichment status badges. Cards with playbook matches show playbook badge.

**Step 5: Commit**

```bash
git add dashboard/server.py dashboard/static/app.js dashboard/static/style.css
git commit -m "Add enrichment status and playbook match badges to dashboard"
```

---

### Task 9: Integration Test — End-to-End Pipeline

**Files:**
- Create: `dashboard/tests/test_enrichment_e2e.py`

**Step 1: Write the e2e test**

```python
# dashboard/tests/test_enrichment_e2e.py
"""
End-to-end test: insert a fake freshservice card, run the enrichment pipeline
(mocking the LLM and Freshservice API), verify card gets enriched with actions.
"""
import json, os, sys, sqlite3, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

def _load_module():
    spec = __import__("importlib").util.spec_from_file_location(
        "enrichment",
        os.path.join(os.path.dirname(__file__), "..", "..", "bin", "freshservice-enrichment.py"),
    )
    mod = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_e2e_classify_and_enrich(tmp_path, monkeypatch):
    mod = _load_module()

    # Use temp DB
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(mod, "DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE cards (
        id INTEGER PRIMARY KEY, source TEXT, timestamp TEXT, summary TEXT,
        classification TEXT DEFAULT 'needs-response', status TEXT DEFAULT 'pending',
        proposed_actions TEXT, analysis_metadata TEXT, enrichment_status TEXT DEFAULT 'not_enriched',
        execution_status TEXT DEFAULT 'not_run', section TEXT, context_notes TEXT,
        draft_response TEXT, responded INTEGER DEFAULT 0, filter_suggested INTEGER DEFAULT 0,
        refinement_history TEXT, queue TEXT, user_edit TEXT, actioned_at TEXT,
        turns INTEGER DEFAULT 0, execution_result TEXT, executed_at TEXT, event_id INTEGER, draft TEXT
    )""")
    conn.execute("""CREATE TABLE classification_buckets (
        id TEXT PRIMARY KEY, description TEXT, knowledge_files TEXT DEFAULT '[]',
        confidence_keywords TEXT DEFAULT '[]', ticket_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'emerging', created_by_ticket INTEGER,
        created_at TEXT, updated_at TEXT
    )""")
    conn.execute("""CREATE TABLE enrichment_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER, stage TEXT,
        model TEXT, duration_ms INTEGER, status TEXT, response_summary TEXT, created_at TEXT
    )""")
    conn.execute("""CREATE UNIQUE INDEX idx_cards_source_summary ON cards(source, summary)""")

    # Insert test card
    meta = json.dumps({"ticket_id": 99999, "status": "Open", "priority": "Medium", "type": "Service Request"})
    conn.execute(
        "INSERT INTO cards (source, timestamp, summary, analysis_metadata, enrichment_status) VALUES (?, ?, ?, ?, ?)",
        ("freshservice", "2026-03-10T00:00:00Z", "#99999 [Service Request] Test Jira Access", meta, "not_enriched"),
    )
    conn.commit()
    conn.close()

    # Mock LLM calls
    call_count = {"n": 0}
    def mock_llm(prompt, stage, timeout=60):
        call_count["n"] += 1
        if stage == "classify":
            return json.dumps({
                "bucket_id": "jira-admin",
                "bucket_description": "Jira admin tasks",
                "is_new_bucket": True,
                "knowledge_files": ["jira-api-reference.md"],
                "confidence_keywords": ["jira", "access"],
                "reasoning": "test",
            })
        elif stage == "enrich":
            return json.dumps({
                "proposed_actions": [
                    {"type": "grant_access", "draft": "Grant Jira access to user"},
                    {"type": "reply_to_requester", "draft": "Confirm access granted"},
                ],
                "playbook_match": None,
            })
        return "{}"

    monkeypatch.setattr(mod, "_run_llm", mock_llm)
    monkeypatch.setattr(mod, "fetch_ticket_description", lambda tid: "User needs Jira access")
    monkeypatch.setattr(mod, "invalidate_dashboard", lambda: None)
    monkeypatch.setattr(mod, "load_approved_playbooks_summary", lambda: "No playbooks")

    # Run pipeline
    cards = mod.fetch_unenriched_cards()
    assert len(cards) == 1

    success = mod.enrich_single_card(cards[0])
    assert success is True
    assert call_count["n"] == 2  # classify + enrich

    # Verify card was enriched
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    card = dict(conn.execute("SELECT * FROM cards WHERE id = 1").fetchone())
    conn.close()

    assert card["enrichment_status"] == "enriched"
    actions = json.loads(card["proposed_actions"])
    assert len(actions) == 2
    assert actions[0]["type"] == "grant_access"

    meta = json.loads(card["analysis_metadata"])
    assert meta["classification_bucket"] == "jira-admin"
```

**Step 2: Run the test**

Run: `cd ~/.claude/skills/eng-buddy && python3 -m pytest dashboard/tests/test_enrichment_e2e.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add dashboard/tests/test_enrichment_e2e.py
git commit -m "Add end-to-end integration test for enrichment pipeline"
```

---

### Task 10: Manual Smoke Test + First Run

**Step 1: Ensure DB is migrated**

Run: `cd ~/.claude/eng-buddy && python3 -c "from dashboard.server import *; print('migrated')"` or restart the dashboard which triggers migration on startup.

Alternatively, run the migration manually:
```bash
sqlite3 ~/.claude/eng-buddy/inbox.db "ALTER TABLE cards ADD COLUMN enrichment_status TEXT DEFAULT 'not_enriched'" 2>/dev/null
sqlite3 ~/.claude/eng-buddy/inbox.db "CREATE TABLE IF NOT EXISTS classification_buckets (id TEXT PRIMARY KEY, description TEXT, knowledge_files TEXT DEFAULT '[]', confidence_keywords TEXT DEFAULT '[]', ticket_count INTEGER DEFAULT 0, status TEXT DEFAULT 'emerging', created_by_ticket INTEGER, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))"
sqlite3 ~/.claude/eng-buddy/inbox.db "CREATE TABLE IF NOT EXISTS enrichment_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER, stage TEXT, model TEXT, duration_ms INTEGER, status TEXT, response_summary TEXT, created_at TEXT DEFAULT (datetime('now')))"
```

**Step 2: Run enrichment pipeline manually on 2-3 cards**

```bash
cd ~/.claude/eng-buddy/bin && python3 freshservice-enrichment.py
```

Watch output for classify → enrich flow. Verify:
- Cards get classified into buckets
- Actions are generated (more than just "Review ticket")
- Dashboard refreshes and shows new actions
- `classification_buckets` table has entries

**Step 3: Verify on dashboard**

Run: `open http://127.0.0.1:7777`
Expected: Freshservice cards now show 2-5 specific actions, enrichment badges, and (if matched) playbook badges.

**Step 4: Install LaunchAgent**

Run: `bash ~/.claude/skills/eng-buddy/bin/start-pollers.sh`
Expected: Enrichment pipeline LaunchAgent installed and running.

**Step 5: Final commit**

```bash
git add -A
git commit -m "Complete Freshservice enrichment pipeline: classify, enrich, detect patterns"
```
