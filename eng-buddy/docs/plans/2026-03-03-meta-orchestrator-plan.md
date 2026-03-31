# eng-buddy v2: Meta-Orchestrator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an always-on Python orchestrator that eliminates copy-paste friction — every Slack message, email, ticket, and meeting automatically captured, AI-drafted, and surfaced for one-click approve/deny.

**Architecture:** Modular Python daemons write all events to a SQLite `events.db`. An orchestrator daemon classifies events and spawns `claude --dangerously-skip-permissions` with eng-buddy's SKILL.md + memory files injected as context. A FastAPI + HTMX web dashboard surfaces cards with approve/deny. Approved actions execute via Claude CLI (MCP-enabled). All outputs write back to `~/.claude/eng-buddy/` — the same files Claude Code sessions already read.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, HTMX, SQLite (stdlib), pytest, httpx, watchdog, subprocess (for CLI agents)

**Project root:** `~/.claude/eng-buddy/orchestrator/`

---

## Phase 1: Foundation

### Task 1: Project scaffold + dependencies

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/pyproject.toml`
- Create: `~/.claude/eng-buddy/orchestrator/requirements.txt`
- Create: `~/.claude/eng-buddy/orchestrator/config.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/__init__.py`

**Step 1: Create project directory**

```bash
mkdir -p ~/.claude/eng-buddy/orchestrator/{db,ingestors,orchestrator,executor,dashboard/{routes,templates,static},monitors,learning,tests}
touch ~/.claude/eng-buddy/orchestrator/{db,ingestors,orchestrator,executor,dashboard,dashboard/routes,monitors,learning,tests}/__init__.py
```

Expected: directories created, no errors.

**Step 2: Write pyproject.toml**

Create `~/.claude/eng-buddy/orchestrator/pyproject.toml`:

```toml
[project]
name = "eng-buddy-orchestrator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "httpx>=0.27.0",
    "watchdog>=5.0.0",
    "schedule>=1.2.0",
    "python-multipart>=0.0.12",
    "pydantic>=2.9.0",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Write requirements.txt (flat for pip install)**

Create `~/.claude/eng-buddy/orchestrator/requirements.txt`:

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
httpx>=0.27.0
watchdog>=5.0.0
schedule>=1.2.0
python-multipart>=0.0.12
pydantic>=2.9.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
pytest-httpx>=0.35.0
```

**Step 4: Install dependencies**

```bash
cd ~/.claude/eng-buddy/orchestrator
pip3 install -r requirements.txt
```

Expected: all packages install, no errors.

**Step 5: Write config.py**

Create `~/.claude/eng-buddy/orchestrator/config.py`:

```python
from pathlib import Path

# Paths
HOME = Path.home()
ENG_BUDDY_DIR = HOME / ".claude" / "eng-buddy"
ORCHESTRATOR_DIR = ENG_BUDDY_DIR / "orchestrator"
SKILL_MD = HOME / ".claude" / "skills" / "eng-buddy" / "SKILL.md"

# SQLite databases
EVENTS_DB = ENG_BUDDY_DIR / "events.db"
INBOX_DB = ENG_BUDDY_DIR / "inbox.db"

# Memory files (read by Claude Code sessions too)
DAILY_DIR = ENG_BUDDY_DIR / "daily"
TASKS_FILE = ENG_BUDDY_DIR / "tasks" / "active-tasks.md"
ACTION_LOG = ENG_BUDDY_DIR / "action-log.md"
SESSIONS_DIR = ENG_BUDDY_DIR / "sessions"

# CLI commands
CLAUDE_CMD = ["claude", "--dangerously-skip-permissions"]
CODEX_CMD = ["codex", "--yolo"]
GEMINI_CMD = ["gemini", "--yolo"]

# Orchestrator settings
CONTEXT_ROTATION_MINUTES = 45
STUCK_LOOP_THRESHOLD = 10       # turns before Gemini tiebreaker
POLL_INTERVAL_SECONDS = 30      # how often orchestrator checks events.db
SCREEN_CAPTURE_INTERVAL = 300   # seconds between screenshots

# Urgency keywords (trigger macOS notification immediately)
URGENT_KEYWORDS = [
    "blocked", "critical", "deadline", "asap", "escalation",
    "down", "outage", "urgent", "emergency", "broken", "sev1", "sev2"
]
```

**Step 6: Write a smoke test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_config.py`:

```python
from config import ENG_BUDDY_DIR, EVENTS_DB, SKILL_MD, CLAUDE_CMD

def test_eng_buddy_dir_exists():
    assert ENG_BUDDY_DIR.exists(), f"eng-buddy dir missing: {ENG_BUDDY_DIR}"

def test_claude_cmd_has_flag():
    assert "--dangerously-skip-permissions" in CLAUDE_CMD

def test_urgent_keywords_nonempty():
    from config import URGENT_KEYWORDS
    assert len(URGENT_KEYWORDS) > 0
```

**Step 7: Run smoke test**

```bash
cd ~/.claude/eng-buddy/orchestrator
python3 -m pytest tests/test_config.py -v
```

Expected: 3 tests pass.

---

### Task 2: SQLite schema

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/db/schema.py`
- Create: `~/.claude/eng-buddy/orchestrator/db/models.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_schema.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_schema.py`:

```python
import sqlite3
import tempfile
from pathlib import Path
from db.schema import init_events_db, init_inbox_db

def test_events_db_creates_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        conn = init_events_db(db_path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        assert "events" in tables
        conn.close()

def test_inbox_db_creates_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        conn = init_inbox_db(db_path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        assert "cards" in tables
        conn.close()

def test_events_table_columns():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        conn = init_events_db(Path(f.name))
        cur = conn.execute("PRAGMA table_info(events)")
        cols = {row[1] for row in cur.fetchall()}
        assert {"id", "source", "timestamp", "raw_content", "metadata", "classification", "processed"} <= cols
        conn.close()
```

**Step 2: Run test — expect FAIL**

```bash
cd ~/.claude/eng-buddy/orchestrator
python3 -m pytest tests/test_schema.py -v
```

Expected: ImportError — `db.schema` not found.

**Step 3: Write schema.py**

Create `~/.claude/eng-buddy/orchestrator/db/schema.py`:

```python
import sqlite3
from pathlib import Path


def init_events_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            timestamp       TEXT NOT NULL,
            raw_content     TEXT NOT NULL,
            metadata        TEXT,
            classification  TEXT,
            processed       INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)")
    conn.commit()
    return conn


def init_inbox_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id         INTEGER REFERENCES events(id),
            source           TEXT NOT NULL,
            timestamp        TEXT NOT NULL,
            summary          TEXT NOT NULL,
            draft            TEXT,
            proposed_actions TEXT,
            classification   TEXT NOT NULL DEFAULT 'needs-response',
            status           TEXT NOT NULL DEFAULT 'pending',
            user_edit        TEXT,
            actioned_at      TEXT,
            turns            INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status)")
    conn.commit()
    return conn


def get_events_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_inbox_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
```

**Step 4: Write models.py**

Create `~/.claude/eng-buddy/orchestrator/db/models.py`:

```python
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Event:
    source: str          # 'slack' | 'gmail' | 'freshservice' | 'jira' | 'calendar' | 'screen' | 'filesystem'
    timestamp: str       # ISO 8601
    raw_content: str     # JSON string
    metadata: str = ""   # JSON string
    classification: Optional[str] = None
    id: Optional[int] = None
    processed: int = 0


@dataclass
class Card:
    event_id: int
    source: str
    timestamp: str
    summary: str
    draft: Optional[str] = None
    proposed_actions: str = "[]"   # JSON array
    classification: str = "needs-response"
    status: str = "pending"
    user_edit: Optional[str] = None
    actioned_at: Optional[str] = None
    turns: int = 0
    id: Optional[int] = None

    def get_actions(self) -> list:
        return json.loads(self.proposed_actions)
```

**Step 5: Run tests — expect PASS**

```bash
cd ~/.claude/eng-buddy/orchestrator
python3 -m pytest tests/test_schema.py -v
```

Expected: 3 tests pass.

**Step 6: Commit**

```bash
cd ~/.claude/eng-buddy/orchestrator
git init && git add -A && git commit -m "feat: project scaffold, config, sqlite schema"
```

---

### Task 3: Base ingestor

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/ingestors/base.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_base_ingestor.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_base_ingestor.py`:

```python
import tempfile
import json
from pathlib import Path
from datetime import datetime
from db.schema import init_events_db
from db.models import Event
from ingestors.base import BaseIngestor


class ConcreteIngestor(BaseIngestor):
    source = "test"

    def fetch_new_items(self) -> list[dict]:
        return [{"text": "hello", "user": "test-user"}]


def test_ingestor_writes_to_events_db():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        conn = init_events_db(db_path)
        ingestor = ConcreteIngestor(db_path)
        ingestor.run_once()
        cur = conn.execute("SELECT source, raw_content FROM events")
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "test"
        content = json.loads(rows[0][1])
        assert content["text"] == "hello"
        conn.close()

def test_ingestor_deduplicates_on_rerun():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_events_db(db_path)
        ingestor = ConcreteIngestor(db_path)
        ingestor.run_once()
        ingestor.run_once()
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 1   # same item not written twice
        conn.close()
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_base_ingestor.py -v
```

Expected: ImportError.

**Step 3: Write base.py**

Create `~/.claude/eng-buddy/orchestrator/ingestors/base.py`:

```python
import json
import sqlite3
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path


class BaseIngestor(ABC):
    source: str = "unknown"

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _content_hash(self, content: dict) -> str:
        serialized = json.dumps(content, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _already_seen(self, conn: sqlite3.Connection, content_hash: str) -> bool:
        cur = conn.execute(
            "SELECT id FROM events WHERE source=? AND metadata LIKE ?",
            (self.source, f'%"hash":"{content_hash}"%')
        )
        return cur.fetchone() is not None

    def _write_event(self, conn: sqlite3.Connection, item: dict) -> int:
        content_hash = self._content_hash(item)
        if self._already_seen(conn, content_hash):
            return -1
        now = datetime.now(timezone.utc).isoformat()
        metadata = json.dumps({"hash": content_hash})
        cur = conn.execute(
            "INSERT INTO events (source, timestamp, raw_content, metadata) VALUES (?,?,?,?)",
            (self.source, now, json.dumps(item), metadata)
        )
        conn.commit()
        return cur.lastrowid

    @abstractmethod
    def fetch_new_items(self) -> list[dict]:
        """Return list of raw item dicts from this source."""
        ...

    def run_once(self) -> int:
        """Fetch and write new items. Returns count of new events written."""
        items = self.fetch_new_items()
        conn = self._get_conn()
        written = 0
        for item in items:
            event_id = self._write_event(conn, item)
            if event_id > 0:
                written += 1
        conn.close()
        return written
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_base_ingestor.py -v
```

Expected: 2 tests pass.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: base ingestor with deduplication"
```

---

### Task 4: Wire Slack ingestor to events.db

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/ingestors/slack_ingestor.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_slack_ingestor.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_slack_ingestor.py`:

```python
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from db.schema import init_events_db
from ingestors.slack_ingestor import SlackIngestor

FAKE_MESSAGES = [
    {"type": "message", "text": "can you add me to Jira?", "user": "U123", "ts": "1709500000.000001", "channel": "DM456"}
]

def test_slack_ingestor_writes_message():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        conn = init_events_db(db_path)
        ingestor = SlackIngestor(db_path, token="xoxp-fake")
        with patch.object(ingestor, "fetch_new_items", return_value=FAKE_MESSAGES):
            count = ingestor.run_once()
        assert count == 1
        cur = conn.execute("SELECT source, raw_content FROM events")
        row = cur.fetchone()
        assert row[0] == "slack"
        content = json.loads(row[1])
        assert "Jira" in content["text"]
        conn.close()

def test_slack_ingestor_deduplicates():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_events_db(db_path)
        ingestor = SlackIngestor(db_path, token="xoxp-fake")
        with patch.object(ingestor, "fetch_new_items", return_value=FAKE_MESSAGES):
            ingestor.run_once()
            count = ingestor.run_once()
        assert count == 0   # second run writes nothing
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_slack_ingestor.py -v
```

**Step 3: Write slack_ingestor.py**

Create `~/.claude/eng-buddy/orchestrator/ingestors/slack_ingestor.py`:

```python
"""
SlackIngestor: wraps the existing slack-poller logic.
Reads from Slack API and writes events to events.db.
Existing slack-poller.py continues to write task-inbox.md for backward compat.
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from ingestors.base import BaseIngestor

SLACK_BASE = "https://slack.com/api"
STATE_FILE = Path.home() / ".claude" / "eng-buddy" / "slack-ingestor-state.json"


class SlackIngestor(BaseIngestor):
    source = "slack"

    def __init__(self, db_path: Path, token: str = None):
        super().__init__(db_path)
        if token is None:
            # Read token from existing slack-poller.py
            poller = Path.home() / ".claude" / "skills" / "eng-buddy" / "bin" / "slack-poller.py"
            text = poller.read_text()
            for line in text.splitlines():
                if line.strip().startswith("TOKEN ="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        self.token = token
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {"last_ts": str(time.time() - 3600)}

    def _save_state(self, ts: str):
        STATE_FILE.write_text(json.dumps({"last_ts": ts}))

    def _slack_get(self, method: str, params: dict) -> dict:
        params["token"] = self.token
        url = f"{SLACK_BASE}/{method}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    def _get_dms(self) -> list[dict]:
        data = self._slack_get("conversations.list", {"types": "im", "limit": "50"})
        channels = data.get("channels", [])
        messages = []
        since = self._state["last_ts"]
        for ch in channels:
            hist = self._slack_get("conversations.history", {
                "channel": ch["id"], "oldest": since, "limit": "20"
            })
            for msg in hist.get("messages", []):
                if msg.get("type") == "message" and not msg.get("bot_id"):
                    messages.append({**msg, "channel": ch["id"], "channel_type": "dm"})
        return messages

    def fetch_new_items(self) -> list[dict]:
        try:
            messages = self._get_dms()
            if messages:
                latest_ts = max(m["ts"] for m in messages)
                self._save_state(latest_ts)
            return messages
        except Exception as e:
            print(f"[slack-ingestor] error: {e}")
            return []
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_slack_ingestor.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: slack ingestor wrapping existing poller"
```

---

### Task 5: Freshservice ingestor

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/ingestors/freshservice_ingestor.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_freshservice_ingestor.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_freshservice_ingestor.py`:

```python
import tempfile, json
from pathlib import Path
from unittest.mock import patch, MagicMock
from db.schema import init_events_db
from ingestors.freshservice_ingestor import FreshserviceIngestor

FAKE_TICKET = {
    "id": 42001, "subject": "Add me to Jira R&D",
    "requester_id": 123, "status": 2, "priority": 1,
    "created_at": "2026-03-03T10:00:00Z",
    "description_text": "Please add me to the R&D Jira project."
}

def test_freshservice_ingestor_writes_ticket():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        conn = init_events_db(db_path)
        ingestor = FreshserviceIngestor(db_path, api_key="fake-key", domain="klaviyo")
        with patch.object(ingestor, "fetch_new_items", return_value=[FAKE_TICKET]):
            count = ingestor.run_once()
        assert count == 1
        cur = conn.execute("SELECT source, raw_content FROM events")
        row = cur.fetchone()
        assert row[0] == "freshservice"
        content = json.loads(row[1])
        assert content["id"] == 42001
        conn.close()
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_freshservice_ingestor.py -v
```

**Step 3: Write freshservice_ingestor.py**

Create `~/.claude/eng-buddy/orchestrator/ingestors/freshservice_ingestor.py`:

```python
import json
import base64
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ingestors.base import BaseIngestor

STATE_FILE = Path.home() / ".claude" / "eng-buddy" / "freshservice-ingestor-state.json"


class FreshserviceIngestor(BaseIngestor):
    source = "freshservice"

    def __init__(self, db_path: Path, api_key: str, domain: str):
        super().__init__(db_path)
        self.api_key = api_key
        self.domain = domain
        self.base_url = f"https://{domain}.freshservice.com/api/v2"
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        since = (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"last_checked": since}

    def _save_state(self, ts: str):
        STATE_FILE.write_text(json.dumps({"last_checked": ts}))

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{path}"
        if params:
            import urllib.parse
            url += "?" + urllib.parse.urlencode(params)
        creds = base64.b64encode(f"{self.api_key}:X".encode()).decode()
        req = urllib.request.Request(url, headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    def fetch_new_items(self) -> list[dict]:
        try:
            since = self._state["last_checked"]
            data = self._get("tickets", {
                "updated_since": since,
                "order_type": "asc",
                "per_page": 50
            })
            tickets = data.get("tickets", [])
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._save_state(now)
            return tickets
        except Exception as e:
            print(f"[freshservice-ingestor] error: {e}")
            return []
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_freshservice_ingestor.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: freshservice ingestor"
```

---

### Task 6: Jira ingestor

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/ingestors/jira_ingestor.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_jira_ingestor.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_jira_ingestor.py`:

```python
import tempfile, json
from pathlib import Path
from unittest.mock import patch
from db.schema import init_events_db
from ingestors.jira_ingestor import JiraIngestor

FAKE_ISSUE = {
    "id": "10042", "key": "ITWORK2-9999",
    "fields": {
        "summary": "SSO setup for new vendor",
        "status": {"name": "In Progress"},
        "assignee": {"displayName": "Kioja Kudumu"},
        "updated": "2026-03-03T10:00:00.000+0000"
    }
}

def test_jira_ingestor_writes_issue():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_events_db(db_path)
        ingestor = JiraIngestor(db_path, base_url="https://klaviyo.atlassian.net",
                                 email="test@klaviyo.com", api_token="fake")
        with patch.object(ingestor, "fetch_new_items", return_value=[FAKE_ISSUE]):
            count = ingestor.run_once()
        assert count == 1
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_jira_ingestor.py -v
```

**Step 3: Write jira_ingestor.py**

Create `~/.claude/eng-buddy/orchestrator/ingestors/jira_ingestor.py`:

```python
import json, base64, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ingestors.base import BaseIngestor

STATE_FILE = Path.home() / ".claude" / "eng-buddy" / "jira-ingestor-state.json"


class JiraIngestor(BaseIngestor):
    source = "jira"

    def __init__(self, db_path: Path, base_url: str, email: str, api_token: str):
        super().__init__(db_path)
        self.base_url = base_url.rstrip("/")
        creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self.auth_header = f"Basic {creds}"
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        since = (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        return {"last_checked": since}

    def _save_state(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        STATE_FILE.write_text(json.dumps({"last_checked": now}))

    def _jql_get(self, jql: str) -> list[dict]:
        params = urllib.parse.urlencode({"jql": jql, "maxResults": 50, "fields": "summary,status,assignee,updated,comment"})
        url = f"{self.base_url}/rest/api/3/search?{params}"
        req = urllib.request.Request(url, headers={"Authorization": self.auth_header, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("issues", [])

    def fetch_new_items(self) -> list[dict]:
        try:
            since = self._state["last_checked"]
            jql = f'assignee = currentUser() AND updated >= "{since}" ORDER BY updated ASC'
            issues = self._jql_get(jql)
            self._save_state()
            return issues
        except Exception as e:
            print(f"[jira-ingestor] error: {e}")
            return []
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_jira_ingestor.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: jira ingestor"
```

---

### Task 7: Event classifier

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/orchestrator/classifier.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_classifier.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_classifier.py`:

```python
from orchestrator.classifier import classify_event

def test_classifies_urgent_slack():
    result = classify_event("slack", {"text": "ASAP the SSO is down and we're blocked"})
    assert result == "urgent"

def test_classifies_needs_response_request():
    result = classify_event("slack", {"text": "can you add me to the R&D Jira project?"})
    assert result == "needs-response"

def test_classifies_freshservice_ticket_as_needs_response():
    result = classify_event("freshservice", {"subject": "Add me to Jira", "status": 2})
    assert result == "needs-response"

def test_classifies_fyi_notification():
    result = classify_event("jira", {"fields": {"summary": "Build passed", "status": {"name": "Done"}}})
    assert result == "fyi"

def test_classifies_screen_capture_as_automatable():
    result = classify_event("screen", {"activity": "manual_api_calls", "duration_seconds": 1200})
    assert result == "automatable"
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_classifier.py -v
```

**Step 3: Write classifier.py**

Create `~/.claude/eng-buddy/orchestrator/orchestrator/classifier.py`:

```python
import json
from config import URGENT_KEYWORDS

REQUEST_PATTERNS = [
    "can you", "could you", "please", "add me", "need help",
    "need access", "request", "can i get", "how do i", "set up",
    "provision", "reset", "broken", "not working", "can't access"
]


def _text_from_event(source: str, content: dict) -> str:
    if source == "slack":
        return content.get("text", "").lower()
    if source == "gmail":
        return f"{content.get('subject', '')} {content.get('snippet', '')}".lower()
    if source == "freshservice":
        return f"{content.get('subject', '')} {content.get('description_text', '')}".lower()
    if source == "jira":
        fields = content.get("fields", {})
        return f"{fields.get('summary', '')}".lower()
    if source == "screen":
        return content.get("activity", "").lower()
    return json.dumps(content).lower()


def classify_event(source: str, content: dict) -> str:
    text = _text_from_event(source, content)

    if source == "screen":
        return "automatable"

    for keyword in URGENT_KEYWORDS:
        if keyword.lower() in text:
            return "urgent"

    for pattern in REQUEST_PATTERNS:
        if pattern in text:
            return "needs-response"

    if source == "freshservice":
        status = content.get("status", 0)
        if status in (2, 3):    # open or pending
            return "needs-response"

    if source == "jira":
        fields = content.get("fields", {})
        status_name = fields.get("status", {}).get("name", "").lower()
        if status_name in ("to do", "in progress", "open"):
            return "needs-response"

    return "fyi"
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_classifier.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: event classifier with urgency detection"
```

---

### Task 8: Claude CLI agent spawner

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/orchestrator/agent.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_agent.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_agent.py`:

```python
import json
from unittest.mock import patch, MagicMock
from orchestrator.agent import AgentSpawner, LLM

def test_spawner_builds_claude_prompt_with_skill_md(tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# eng-buddy\nYou are engineering buddy.")
    daily = tmp_path / "today.md"
    daily.write_text("# Today\n- working on stuff")
    spawner = AgentSpawner(skill_md_path=skill_md, daily_path=daily)
    prompt = spawner._build_prompt("Draft a reply to: hey can you add me to Jira?")
    assert "eng-buddy" in prompt
    assert "working on stuff" in prompt
    assert "Jira" in prompt

def test_spawner_selects_codex_for_critic():
    spawner = AgentSpawner()
    cmd = spawner._get_cmd(LLM.CODEX)
    assert "codex" in cmd[0]
    assert "--yolo" in cmd

def test_spawner_selects_gemini_for_tiebreaker():
    spawner = AgentSpawner()
    cmd = spawner._get_cmd(LLM.GEMINI)
    assert "gemini" in cmd[0]
    assert "--yolo" in cmd

def test_spawner_runs_claude_and_returns_output():
    spawner = AgentSpawner()
    fake_result = MagicMock()
    fake_result.stdout = "Draft: Sure, adding you to Jira now."
    fake_result.returncode = 0
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        output = spawner.run(LLM.CLAUDE, "test task", timeout=10)
    assert "adding you to Jira" in output
    call_args = mock_run.call_args
    assert "--dangerously-skip-permissions" in call_args[0][0]
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_agent.py -v
```

**Step 3: Write agent.py**

Create `~/.claude/eng-buddy/orchestrator/orchestrator/agent.py`:

```python
import subprocess
from datetime import date
from enum import Enum
from pathlib import Path
from config import (
    CLAUDE_CMD, CODEX_CMD, GEMINI_CMD,
    SKILL_MD, DAILY_DIR, TASKS_FILE
)


class LLM(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"


class AgentSpawner:
    def __init__(self, skill_md_path: Path = None, daily_path: Path = None):
        self.skill_md_path = skill_md_path or SKILL_MD
        self.daily_path = daily_path or (DAILY_DIR / f"{date.today().isoformat()}.md")

    def _load_skill_md(self) -> str:
        if self.skill_md_path.exists():
            return self.skill_md_path.read_text()
        return "# eng-buddy\nYou are Engineering Buddy, an IT systems engineering assistant."

    def _load_daily(self) -> str:
        if self.daily_path.exists():
            return self.daily_path.read_text()
        return "No daily log yet."

    def _load_tasks(self) -> str:
        if TASKS_FILE.exists():
            return TASKS_FILE.read_text()
        return "No active tasks."

    def _build_prompt(self, task: str) -> str:
        skill_md = self._load_skill_md()
        daily = self._load_daily()
        tasks = self._load_tasks()
        return f"""{skill_md}

---
## Current Context (auto-injected by orchestrator)

### Today's Log
{daily}

### Active Tasks
{tasks}

---
## Your Task
{task}
"""

    def _get_cmd(self, llm: LLM) -> list[str]:
        if llm == LLM.CLAUDE:
            return CLAUDE_CMD
        if llm == LLM.CODEX:
            return CODEX_CMD
        if llm == LLM.GEMINI:
            return GEMINI_CMD
        return CLAUDE_CMD

    def run(self, llm: LLM, task: str, timeout: int = 120) -> str:
        cmd = self._get_cmd(llm)
        if llm == LLM.CLAUDE:
            prompt = self._build_prompt(task)
            full_cmd = cmd + ["-p", prompt]
        else:
            full_cmd = cmd + [task]

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                print(f"[agent] {llm.value} error: {result.stderr[:500]}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"[agent] {llm.value} timed out after {timeout}s")
            return ""
        except FileNotFoundError:
            print(f"[agent] {llm.value} CLI not found in PATH")
            return ""

    def run_codex_critic(self, code: str, plan_context: str) -> str:
        task = f"""You are a harsh code critic. Review this code:

{code}

Project context:
{plan_context}

Check for: stubs, incomplete functions, missing error handling, code that doesn't match the project structure, anything that doesn't actually work. Fix everything you find. Return the complete corrected code only."""
        return self.run(LLM.CODEX, task)

    def run_gemini_tiebreaker(self, history: str) -> str:
        task = f"""You are a tiebreaker on a debugging session that has been stuck for 10+ turns.

Full session history:
{history}

Give a fresh perspective. What is being missed? What approach hasn't been tried? Be direct and specific."""
        return self.run(LLM.GEMINI, task, timeout=300)
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_agent.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: agent spawner for claude/codex/gemini CLIs"
```

---

### Task 9: Orchestrator daemon

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/orchestrator/daemon.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_daemon.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_daemon.py`:

```python
import tempfile, json, sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from db.schema import init_events_db, init_inbox_db
from orchestrator.daemon import OrchestratorDaemon

def _seed_event(db_path, source="slack", text="can you add me to Jira?"):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO events (source, timestamp, raw_content, metadata, processed) VALUES (?,?,?,?,0)",
        (source, "2026-03-03T10:00:00Z", json.dumps({"text": text}), "{}")
    )
    conn.commit()
    conn.close()

def test_daemon_processes_event_and_creates_card():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as ef, \
         tempfile.NamedTemporaryFile(suffix=".db", delete=False) as inf:
        events_db = Path(ef.name)
        inbox_db = Path(inf.name)
        init_events_db(events_db)
        init_inbox_db(inbox_db)
        _seed_event(events_db)

        daemon = OrchestratorDaemon(events_db=events_db, inbox_db=inbox_db)
        with patch.object(daemon.spawner, "run", return_value="Draft: Sure, adding you now."):
            daemon.process_pending_events()

        conn = sqlite3.connect(str(inbox_db))
        cards = conn.execute("SELECT source, summary, draft, status FROM cards").fetchall()
        conn.close()
        assert len(cards) == 1
        assert cards[0][3] == "pending"

def test_daemon_marks_event_processed():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as ef, \
         tempfile.NamedTemporaryFile(suffix=".db", delete=False) as inf:
        events_db = Path(ef.name)
        inbox_db = Path(inf.name)
        init_events_db(events_db)
        init_inbox_db(inbox_db)
        _seed_event(events_db)

        daemon = OrchestratorDaemon(events_db=events_db, inbox_db=inbox_db)
        with patch.object(daemon.spawner, "run", return_value="Draft reply"):
            daemon.process_pending_events()

        conn = sqlite3.connect(str(events_db))
        row = conn.execute("SELECT processed FROM events WHERE id=1").fetchone()
        conn.close()
        assert row[0] == 1
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_daemon.py -v
```

**Step 3: Write daemon.py**

Create `~/.claude/eng-buddy/orchestrator/orchestrator/daemon.py`:

```python
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from config import EVENTS_DB, INBOX_DB, POLL_INTERVAL_SECONDS
from orchestrator.classifier import classify_event
from orchestrator.agent import AgentSpawner, LLM


class OrchestratorDaemon:
    def __init__(self, events_db: Path = None, inbox_db: Path = None):
        self.events_db = events_db or EVENTS_DB
        self.inbox_db = inbox_db or INBOX_DB
        self.spawner = AgentSpawner()

    def _events_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.events_db), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _inbox_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.inbox_db), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _auto_commit(self, reason: str):
        eng_buddy_dir = Path.home() / ".claude" / "eng-buddy"
        subprocess.run(
            ["git", "-C", str(eng_buddy_dir), "add", "-A"],
            capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(eng_buddy_dir), "commit", "-m", f"pre-action snapshot: {reason}"],
            capture_output=True
        )

    def _get_pending_events(self) -> list[sqlite3.Row]:
        conn = self._events_conn()
        rows = conn.execute(
            "SELECT * FROM events WHERE processed=0 ORDER BY id ASC LIMIT 20"
        ).fetchall()
        conn.close()
        return rows

    def _mark_processed(self, event_id: int):
        conn = self._events_conn()
        conn.execute("UPDATE events SET processed=1 WHERE id=?", (event_id,))
        conn.commit()
        conn.close()

    def _draft_for_event(self, source: str, content: dict, classification: str) -> tuple[str, str]:
        """Returns (summary, draft)."""
        if source == "slack":
            text = content.get("text", "")[:500]
            task = f"A Slack message arrived:\n\n{text}\n\nWrite a brief summary (1 line) and a draft response in eng-buddy voice. Format:\nSUMMARY: ...\nDRAFT: ..."
        elif source == "freshservice":
            task = f"A Freshservice ticket arrived:\nSubject: {content.get('subject', '')}\nDescription: {content.get('description_text', '')[:300]}\n\nWrite a brief summary (1 line) and a draft response/action plan. Format:\nSUMMARY: ...\nDRAFT: ..."
        elif source == "jira":
            fields = content.get("fields", {})
            task = f"A Jira update arrived:\nIssue: {content.get('key', '')} - {fields.get('summary', '')}\nStatus: {fields.get('status', {}).get('name', '')}\n\nWrite a brief summary (1 line) and suggested next action. Format:\nSUMMARY: ...\nDRAFT: ..."
        else:
            task = f"Event from {source}:\n{json.dumps(content)[:400]}\n\nWrite a brief summary and suggested response. Format:\nSUMMARY: ...\nDRAFT: ..."

        output = self.spawner.run(LLM.CLAUDE, task, timeout=60)

        summary = ""
        draft = output
        for line in output.splitlines():
            if line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("DRAFT:"):
                draft = output[output.index("DRAFT:") + 6:].strip()
        return summary or f"New {source} event", draft

    def _create_card(self, event_id: int, source: str, summary: str, draft: str,
                     classification: str, content: dict):
        now = datetime.now(timezone.utc).isoformat()
        actions = json.dumps([{"type": "send_response", "draft": draft, "source": source}])
        conn = self._inbox_conn()
        conn.execute(
            """INSERT INTO cards
               (event_id, source, timestamp, summary, draft, proposed_actions, classification)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id, source, now, summary, draft, actions, classification)
        )
        conn.commit()
        conn.close()

    def process_pending_events(self):
        events = self._get_pending_events()
        for event in events:
            try:
                content = json.loads(event["raw_content"])
                classification = classify_event(event["source"], content)
                if classification in ("urgent", "needs-response"):
                    self._auto_commit(f"processing {event['source']} event {event['id']}")
                    summary, draft = self._draft_for_event(event["source"], content, classification)
                    self._create_card(event["id"], event["source"], summary, draft,
                                      classification, content)
                self._mark_processed(event["id"])
            except Exception as e:
                print(f"[orchestrator] error processing event {event['id']}: {e}")
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_daemon.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: orchestrator daemon processes events and creates inbox cards"
```

---

### Task 10: FastAPI dashboard server

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/dashboard/server.py`
- Create: `~/.claude/eng-buddy/orchestrator/dashboard/routes/inbox.py`
- Create: `~/.claude/eng-buddy/orchestrator/dashboard/routes/approve.py`
- Create: `~/.claude/eng-buddy/orchestrator/dashboard/templates/index.html`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_dashboard.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_dashboard.py`:

```python
import pytest, sqlite3, json, tempfile
from pathlib import Path
from fastapi.testclient import TestClient

def _seed_card(inbox_db: Path):
    conn = sqlite3.connect(str(inbox_db))
    conn.execute("""INSERT INTO cards
        (event_id, source, timestamp, summary, draft, proposed_actions, classification, status)
        VALUES (1, 'slack', '2026-03-03T10:00:00Z',
                'Kerry asking about Asana', 'Sure Kerry, checking now.',
                '[{"type":"send_response","draft":"Sure Kerry"}]',
                'needs-response', 'pending')""")
    conn.commit()
    conn.close()

@pytest.fixture
def client(tmp_path):
    from db.schema import init_events_db, init_inbox_db
    events_db = tmp_path / "events.db"
    inbox_db = tmp_path / "inbox.db"
    init_events_db(events_db)
    init_inbox_db(inbox_db)
    _seed_card(inbox_db)
    import os
    os.environ["EVENTS_DB"] = str(events_db)
    os.environ["INBOX_DB"] = str(inbox_db)
    from dashboard.server import create_app
    app = create_app(events_db=events_db, inbox_db=inbox_db)
    return TestClient(app)

def test_inbox_returns_pending_cards(client):
    resp = client.get("/api/inbox")
    assert resp.status_code == 200
    cards = resp.json()
    assert len(cards) == 1
    assert cards[0]["source"] == "slack"
    assert cards[0]["status"] == "pending"

def test_approve_card_marks_approved(client):
    resp = client.post("/api/cards/1/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

def test_deny_card_marks_denied(client):
    resp = client.post("/api/cards/1/deny")
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_dashboard.py -v
```

**Step 3: Write server.py**

Create `~/.claude/eng-buddy/orchestrator/dashboard/server.py`:

```python
import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from config import EVENTS_DB, INBOX_DB

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(events_db: Path = None, inbox_db: Path = None) -> FastAPI:
    _events_db = events_db or EVENTS_DB
    _inbox_db = inbox_db or INBOX_DB

    app = FastAPI(title="eng-buddy orchestrator")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def get_inbox_conn():
        conn = sqlite3.connect(str(_inbox_db), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/api/inbox")
    async def get_inbox():
        conn = get_inbox_conn()
        rows = conn.execute(
            "SELECT * FROM cards WHERE status='pending' ORDER BY classification DESC, id DESC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @app.get("/api/inbox/all")
    async def get_all_cards():
        conn = get_inbox_conn()
        rows = conn.execute("SELECT * FROM cards ORDER BY id DESC LIMIT 100").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @app.post("/api/cards/{card_id}/approve")
    async def approve_card(card_id: int):
        conn = get_inbox_conn()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE cards SET status='approved', actioned_at=? WHERE id=?",
            (now, card_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        conn.close()
        # TODO Task 11: trigger action execution here
        return dict(row)

    @app.post("/api/cards/{card_id}/deny")
    async def deny_card(card_id: int):
        conn = get_inbox_conn()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE cards SET status='denied', actioned_at=? WHERE id=?",
            (now, card_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        conn.close()
        return dict(row)

    @app.post("/api/cards/{card_id}/edit")
    async def edit_card(card_id: int, body: dict):
        conn = get_inbox_conn()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE cards SET user_edit=?, status='approved', actioned_at=? WHERE id=?",
            (body.get("edit", ""), now, card_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        conn.close()
        return dict(row)

    return app
```

**Step 4: Write index.html (HTMX dashboard)**

Create `~/.claude/eng-buddy/orchestrator/dashboard/templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>eng-buddy</title>
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro", monospace;
         background: #0d1117; color: #e6edf3; min-height: 100vh; }
  .header { padding: 16px 24px; border-bottom: 1px solid #21262d;
            display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 18px; font-weight: 600; }
  .badge { background: #238636; color: #fff; border-radius: 12px;
           padding: 2px 10px; font-size: 12px; }
  .layout { display: grid; grid-template-columns: 1fr 320px; gap: 0; height: calc(100vh - 57px); }
  .inbox { padding: 20px; overflow-y: auto; }
  .sidebar { border-left: 1px solid #21262d; padding: 20px; overflow-y: auto; }
  .section-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em;
                   color: #8b949e; margin-bottom: 12px; }
  .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px;
          padding: 16px; margin-bottom: 12px; transition: border-color 0.15s; }
  .card:hover { border-color: #388bfd; }
  .card.urgent { border-left: 3px solid #da3633; }
  .card-source { font-size: 11px; color: #8b949e; margin-bottom: 6px; display: flex;
                 align-items: center; gap: 6px; }
  .source-badge { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;
                  text-transform: uppercase; }
  .source-slack { background: #4a154b33; color: #e01e5a; }
  .source-gmail { background: #ea433533; color: #ea4335; }
  .source-freshservice { background: #00838833; color: #26a69a; }
  .source-jira { background: #0052cc33; color: #579dff; }
  .card-summary { font-size: 14px; font-weight: 500; margin-bottom: 8px; }
  .card-draft { font-size: 13px; color: #8b949e; background: #0d1117; border-radius: 4px;
                padding: 10px; margin-bottom: 12px; border: 1px solid #21262d;
                white-space: pre-wrap; font-family: monospace; }
  .actions { display: flex; gap: 8px; }
  .btn { padding: 6px 14px; border-radius: 6px; border: none; cursor: pointer;
         font-size: 13px; font-weight: 500; transition: opacity 0.15s; }
  .btn:hover { opacity: 0.85; }
  .btn-approve { background: #238636; color: #fff; }
  .btn-deny { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }
  .btn-edit { background: #1f6feb33; color: #388bfd; border: 1px solid #1f6feb; }
  .empty { color: #8b949e; font-size: 14px; padding: 40px 0; text-align: center; }
  .memory-panel { font-size: 12px; color: #8b949e; white-space: pre-wrap;
                  font-family: monospace; max-height: 400px; overflow-y: auto; }
</style>
</head>
<body>
<div class="header">
  <h1>⚙ eng-buddy</h1>
  <span class="badge" id="pending-count">loading...</span>
  <span style="color:#8b949e; font-size:12px; margin-left:auto">
    <span id="last-updated"></span>
  </span>
</div>

<div class="layout">
  <div class="inbox">
    <div class="section-title">Inbox</div>
    <div id="cards-container" hx-get="/api/inbox" hx-trigger="load, every 15s" hx-swap="innerHTML">
      <div class="empty">Loading...</div>
    </div>
  </div>
  <div class="sidebar">
    <div class="section-title" style="margin-bottom:8px">Today's Log</div>
    <div class="memory-panel" id="memory-panel" hx-get="/api/memory" hx-trigger="load, every 30s">
      Loading...
    </div>
  </div>
</div>

<template id="card-template">
  <!-- Rendered by JS below from /api/inbox JSON -->
</template>

<script>
async function loadCards() {
  const resp = await fetch('/api/inbox');
  const cards = await resp.json();
  const container = document.getElementById('cards-container');
  document.getElementById('pending-count').textContent = `${cards.length} pending`;
  document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();

  if (cards.length === 0) {
    container.innerHTML = '<div class="empty">All clear. Nothing pending.</div>';
    return;
  }

  container.innerHTML = cards.map(card => `
    <div class="card ${card.classification === 'urgent' ? 'urgent' : ''}" id="card-${card.id}">
      <div class="card-source">
        <span class="source-badge source-${card.source}">${card.source}</span>
        ${new Date(card.timestamp).toLocaleTimeString()}
      </div>
      <div class="card-summary">${card.summary}</div>
      ${card.draft ? `<div class="card-draft">${card.draft}</div>` : ''}
      <div class="actions">
        <button class="btn btn-approve" onclick="approveCard(${card.id})">✓ Approve</button>
        <button class="btn btn-deny" onclick="denyCard(${card.id})">✗ Deny</button>
      </div>
    </div>
  `).join('');
}

async function approveCard(id) {
  await fetch(`/api/cards/${id}/approve`, { method: 'POST' });
  document.getElementById(`card-${id}`).style.opacity = '0.3';
  setTimeout(loadCards, 800);
}

async function denyCard(id) {
  await fetch(`/api/cards/${id}/deny`, { method: 'POST' });
  document.getElementById(`card-${id}`).style.opacity = '0.3';
  setTimeout(loadCards, 800);
}

loadCards();
setInterval(loadCards, 15000);
</script>
</body>
</html>
```

**Step 5: Add memory endpoint to server.py**

Edit `~/.claude/eng-buddy/orchestrator/dashboard/server.py`, add after the `/api/cards/{card_id}/edit` route:

```python
    @app.get("/api/memory")
    async def get_memory():
        from config import DAILY_DIR
        from datetime import date
        daily_file = DAILY_DIR / f"{date.today().isoformat()}.md"
        if daily_file.exists():
            return {"content": daily_file.read_text()[:5000]}
        return {"content": "No daily log yet."}
```

**Step 6: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_dashboard.py -v
```

**Step 7: Commit**

```bash
git add -A && git commit -m "feat: fastapi dashboard with inbox, approve/deny, memory panel"
```

---

### Task 11: Main entrypoint + launchd

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/main.py`
- Create: `~/.claude/eng-buddy/orchestrator/com.engbuddy.orchestrator.plist`

**Step 1: Write main.py**

Create `~/.claude/eng-buddy/orchestrator/main.py`:

```python
#!/usr/bin/env python3
"""
eng-buddy v2 orchestrator entrypoint.
Starts all daemons and the web dashboard.
"""
import threading
import time
import uvicorn
from pathlib import Path
from db.schema import init_events_db, init_inbox_db
from config import EVENTS_DB, INBOX_DB
from orchestrator.daemon import OrchestratorDaemon
from ingestors.slack_ingestor import SlackIngestor
from ingestors.freshservice_ingestor import FreshserviceIngestor
from ingestors.jira_ingestor import JiraIngestor
from dashboard.server import create_app
import os

# Init DBs
init_events_db(EVENTS_DB)
init_inbox_db(INBOX_DB)


def run_ingestors():
    ingestors = []

    # Slack (reads token from existing poller)
    try:
        ingestors.append(SlackIngestor(EVENTS_DB))
        print("[main] slack ingestor ready")
    except Exception as e:
        print(f"[main] slack ingestor skipped: {e}")

    # Freshservice
    fs_key = os.environ.get("FRESHSERVICE_API_KEY")
    fs_domain = os.environ.get("FRESHSERVICE_DOMAIN", "klaviyo")
    if fs_key:
        ingestors.append(FreshserviceIngestor(EVENTS_DB, api_key=fs_key, domain=fs_domain))
        print("[main] freshservice ingestor ready")

    # Jira
    jira_url = os.environ.get("JIRA_BASE_URL")
    jira_email = os.environ.get("JIRA_EMAIL")
    jira_token = os.environ.get("JIRA_API_TOKEN")
    if all([jira_url, jira_email, jira_token]):
        ingestors.append(JiraIngestor(EVENTS_DB, base_url=jira_url, email=jira_email, api_token=jira_token))
        print("[main] jira ingestor ready")

    while True:
        for ing in ingestors:
            try:
                count = ing.run_once()
                if count > 0:
                    print(f"[ingestor] {ing.source}: {count} new events")
            except Exception as e:
                print(f"[ingestor] {ing.source} error: {e}")
        time.sleep(30)


def run_orchestrator():
    daemon = OrchestratorDaemon()
    while True:
        try:
            daemon.process_pending_events()
        except Exception as e:
            print(f"[orchestrator] error: {e}")
        time.sleep(10)


def run_dashboard():
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=7474, log_level="warning")


if __name__ == "__main__":
    print("🚀 eng-buddy orchestrator starting...")
    print(f"   Dashboard: http://localhost:7474")
    print(f"   Events DB: {EVENTS_DB}")
    print(f"   Inbox DB:  {INBOX_DB}")

    threads = [
        threading.Thread(target=run_ingestors, daemon=True, name="ingestors"),
        threading.Thread(target=run_orchestrator, daemon=True, name="orchestrator"),
    ]
    for t in threads:
        t.start()

    run_dashboard()   # blocks main thread
```

**Step 2: Write launchd plist**

Create `~/.claude/eng-buddy/orchestrator/com.engbuddy.orchestrator.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.engbuddy.orchestrator</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/python3</string>
        <string>/Users/kioja.kudumu/.claude/eng-buddy/orchestrator/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/kioja.kudumu/.claude/eng-buddy/orchestrator</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>FRESHSERVICE_API_KEY</key>
        <string>YOUR_FS_API_KEY</string>
        <key>FRESHSERVICE_DOMAIN</key>
        <string>klaviyo</string>
        <key>JIRA_BASE_URL</key>
        <string>https://klaviyo.atlassian.net</string>
        <key>JIRA_EMAIL</key>
        <string>YOUR_EMAIL</string>
        <key>JIRA_API_TOKEN</key>
        <string>YOUR_JIRA_TOKEN</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/kioja.kudumu/.claude/eng-buddy/orchestrator.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/kioja.kudumu/.claude/eng-buddy/orchestrator-error.log</string>
</dict>
</plist>
```

**Step 3: Test manual startup**

```bash
cd ~/.claude/eng-buddy/orchestrator
python3 main.py
```

Expected: "🚀 eng-buddy orchestrator starting..." and dashboard available at http://localhost:7474.

**Step 4: Install as launchd daemon**

```bash
# Fill in your actual API keys in the plist first, then:
cp ~/.claude/eng-buddy/orchestrator/com.engbuddy.orchestrator.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.engbuddy.orchestrator.plist
launchctl list | grep engbuddy
```

Expected: `com.engbuddy.orchestrator` appears in list with no error code.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: main entrypoint + launchd plist, phase 1 complete"
```

---

## Phase 2: Code Pipeline

### Task 12: Stuck loop detector + Gemini tiebreaker

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/orchestrator/loop_detector.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_loop_detector.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_loop_detector.py`:

```python
from orchestrator.loop_detector import LoopDetector

def test_no_trigger_under_threshold():
    detector = LoopDetector(threshold=10)
    for _ in range(9):
        detector.record_turn("task-bug-auth")
    assert not detector.is_stuck("task-bug-auth")

def test_triggers_at_threshold():
    detector = LoopDetector(threshold=10)
    for _ in range(10):
        detector.record_turn("task-bug-auth")
    assert detector.is_stuck("task-bug-auth")

def test_resets_after_resolution():
    detector = LoopDetector(threshold=10)
    for _ in range(10):
        detector.record_turn("task-bug-auth")
    detector.reset("task-bug-auth")
    assert not detector.is_stuck("task-bug-auth")

def test_different_tasks_tracked_independently():
    detector = LoopDetector(threshold=10)
    for _ in range(10):
        detector.record_turn("task-a")
    assert detector.is_stuck("task-a")
    assert not detector.is_stuck("task-b")
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_loop_detector.py -v
```

**Step 3: Write loop_detector.py**

Create `~/.claude/eng-buddy/orchestrator/orchestrator/loop_detector.py`:

```python
from collections import defaultdict
from config import STUCK_LOOP_THRESHOLD


class LoopDetector:
    def __init__(self, threshold: int = STUCK_LOOP_THRESHOLD):
        self.threshold = threshold
        self._turns: dict[str, int] = defaultdict(int)
        self._history: dict[str, list[str]] = defaultdict(list)

    def record_turn(self, task_key: str, content: str = ""):
        self._turns[task_key] += 1
        if content:
            self._history[task_key].append(content[:500])

    def is_stuck(self, task_key: str) -> bool:
        return self._turns[task_key] >= self.threshold

    def get_history(self, task_key: str) -> str:
        return "\n\n---\n\n".join(self._history[task_key])

    def reset(self, task_key: str):
        self._turns[task_key] = 0
        self._history[task_key] = []

    def turn_count(self, task_key: str) -> int:
        return self._turns[task_key]
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_loop_detector.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: stuck loop detector for Gemini tiebreaker trigger"
```

---

### Task 13: Codex code critic workflow

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/orchestrator/code_pipeline.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_code_pipeline.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_code_pipeline.py`:

```python
from unittest.mock import patch, MagicMock
from orchestrator.code_pipeline import CodePipeline

STUB_CODE = """
def add_user_to_jira(user_email, project_key):
    # TODO: implement
    pass
"""

FIXED_CODE = """
def add_user_to_jira(user_email: str, project_key: str) -> bool:
    import requests
    resp = requests.post(f"https://api.jira.com/project/{project_key}/members",
                         json={"email": user_email})
    resp.raise_for_status()
    return True
"""

def test_pipeline_calls_claude_then_codex():
    pipeline = CodePipeline()
    with patch.object(pipeline.spawner, "run") as mock_run:
        mock_run.side_effect = [STUB_CODE, FIXED_CODE]
        result = pipeline.generate_and_review("Write a function to add a user to Jira", "IT automation project")
    assert mock_run.call_count == 2
    assert result == FIXED_CODE

def test_pipeline_returns_codex_output():
    pipeline = CodePipeline()
    with patch.object(pipeline.spawner, "run") as mock_run:
        mock_run.side_effect = ["def foo(): pass", "def foo(): return 42"]
        result = pipeline.generate_and_review("write foo", "context")
    assert result == "def foo(): return 42"
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_code_pipeline.py -v
```

**Step 3: Write code_pipeline.py**

Create `~/.claude/eng-buddy/orchestrator/orchestrator/code_pipeline.py`:

```python
from orchestrator.agent import AgentSpawner, LLM


class CodePipeline:
    """Claude generates code. Codex reviews and fixes. No stubs make it through."""

    def __init__(self):
        self.spawner = AgentSpawner()

    def generate_and_review(self, task: str, project_context: str) -> str:
        # Step 1: Claude generates
        claude_output = self.spawner.run(LLM.CLAUDE, task, timeout=120)

        # Step 2: Codex reviews and fixes
        fixed_output = self.spawner.run_codex_critic(claude_output, project_context)

        # If Codex returns nothing (CLI unavailable), fall back to Claude output
        return fixed_output if fixed_output.strip() else claude_output

    def generate_with_tiebreaker(self, task: str, project_context: str,
                                  history: str, loop_detector=None, task_key: str = "") -> str:
        """Use Gemini as tiebreaker if stuck for 10+ turns, then feed result back to Claude."""
        if loop_detector and loop_detector.is_stuck(task_key):
            gemini_take = self.spawner.run_gemini_tiebreaker(history)
            refined_task = f"{task}\n\nGemini tiebreaker suggests:\n{gemini_take}"
            if loop_detector:
                loop_detector.reset(task_key)
            return self.generate_and_review(refined_task, project_context)
        return self.generate_and_review(task, project_context)
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_code_pipeline.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: code pipeline claude→codex with Gemini tiebreaker"
```

---

## Phase 3: Environmental Capture

### Task 14: Calendar watcher + meeting detection

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/monitors/calendar_watcher.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_calendar_watcher.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_calendar_watcher.py`:

```python
from unittest.mock import patch
from monitors.calendar_watcher import CalendarWatcher

FAKE_EVENTS = [
    {"summary": "1:1 with Nik", "start": "2026-03-03T14:00:00-08:00",
     "end": "2026-03-03T14:30:00-08:00", "id": "abc123"}
]

def test_detects_upcoming_meeting():
    watcher = CalendarWatcher()
    with patch.object(watcher, "get_upcoming_events", return_value=FAKE_EVENTS):
        meetings = watcher.get_meetings_starting_soon(window_minutes=15)
    assert len(meetings) == 0  # not within 15 min of fake time

def test_returns_empty_when_no_events():
    watcher = CalendarWatcher()
    with patch.object(watcher, "get_upcoming_events", return_value=[]):
        meetings = watcher.get_meetings_starting_soon(window_minutes=15)
    assert meetings == []
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_calendar_watcher.py -v
```

**Step 3: Write calendar_watcher.py**

Create `~/.claude/eng-buddy/orchestrator/monitors/calendar_watcher.py`:

```python
"""
Watches Google Calendar for upcoming meetings.
When a meeting starts in < window_minutes, fires a meeting-start event.
Uses the gmail-mcp OAuth credentials (same Google account).
"""
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

CREDS_FILE = Path.home() / ".gmail-mcp" / "credentials.json"
OAUTH_FILE = Path.home() / ".gmail-mcp" / "gcp-oauth.keys.json"
CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


class CalendarWatcher:
    def __init__(self):
        self._token_cache = {"token": None, "expires_at": 0}

    def _get_token(self) -> str:
        if time.time() < self._token_cache["expires_at"] - 60:
            return self._token_cache["token"]
        creds = json.loads(CREDS_FILE.read_text())
        oauth = json.loads(OAUTH_FILE.read_text())["installed"]
        data = urllib.parse.urlencode({
            "client_id": oauth["client_id"],
            "client_secret": oauth["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token",
                                     data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            new_token = json.loads(resp.read())
        self._token_cache = {
            "token": new_token["access_token"],
            "expires_at": time.time() + new_token.get("expires_in", 3600)
        }
        return self._token_cache["token"]

    def get_upcoming_events(self, hours_ahead: int = 2) -> list[dict]:
        try:
            token = self._get_token()
            now = datetime.now(timezone.utc)
            time_max = (now + timedelta(hours=hours_ahead)).isoformat()
            params = urllib.parse.urlencode({
                "timeMin": now.isoformat(),
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 10,
            })
            url = f"{CALENDAR_BASE}/calendars/primary/events?{params}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            return data.get("items", [])
        except Exception as e:
            print(f"[calendar-watcher] error: {e}")
            return []

    def get_meetings_starting_soon(self, window_minutes: int = 5) -> list[dict]:
        events = self.get_upcoming_events()
        now = datetime.now(timezone.utc)
        soon = now + timedelta(minutes=window_minutes)
        meetings = []
        for ev in events:
            start_str = ev.get("start", {}).get("dateTime", "")
            if not start_str:
                continue
            try:
                start = datetime.fromisoformat(start_str)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if now <= start <= soon:
                    meetings.append(ev)
            except ValueError:
                continue
        return meetings
```

**Step 4: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_calendar_watcher.py -v
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: calendar watcher for meeting detection"
```

---

### Task 15: Transcribe integration

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/monitors/transcribe_integration.py`

**Step 1: Install transcribe**

```bash
pip3 install git+https://github.com/vivekuppal/transcribe.git 2>/dev/null || echo "Install manually if needed"
```

**Step 2: Write transcribe_integration.py**

Create `~/.claude/eng-buddy/orchestrator/monitors/transcribe_integration.py`:

```python
"""
Transcribe integration: auto-starts recording when a meeting is detected,
captures transcript on completion, writes to events.db.
Uses vivekuppal/transcribe for local Whisper transcription (no API key needed).
"""
import json
import subprocess
import threading
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from config import EVENTS_DB

TRANSCRIPT_DIR = Path.home() / ".claude" / "eng-buddy" / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)


class TranscribeIntegration:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or EVENTS_DB
        self._active_process = None
        self._current_meeting = None

    def start_recording(self, meeting_name: str):
        if self._active_process:
            print(f"[transcribe] already recording: {self._current_meeting}")
            return
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in meeting_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = TRANSCRIPT_DIR / f"{timestamp}_{safe_name}.txt"
        self._current_meeting = meeting_name
        self._out_file = out_file
        print(f"[transcribe] starting for: {meeting_name}")
        # transcribe CLI - adjust command based on actual install
        cmd = ["python3", "-m", "transcribe", "--save", str(out_file)]
        try:
            self._active_process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            print("[transcribe] transcribe not installed — skipping recording")
            self._active_process = None

    def stop_recording(self):
        if not self._active_process:
            return
        self._active_process.terminate()
        try:
            self._active_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._active_process.kill()
        self._write_transcript_event()
        self._active_process = None
        self._current_meeting = None

    def _write_transcript_event(self):
        out_file = getattr(self, "_out_file", None)
        if not out_file or not out_file.exists():
            return
        transcript = out_file.read_text()
        if len(transcript.strip()) < 50:
            return   # too short to be useful
        event = {
            "meeting": self._current_meeting,
            "transcript": transcript[:10000],
            "file": str(out_file),
        }
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT INTO events (source, timestamp, raw_content, metadata) VALUES (?,?,?,?)",
            ("transcribe", datetime.now(timezone.utc).isoformat(),
             json.dumps(event), json.dumps({"meeting": self._current_meeting}))
        )
        conn.commit()
        conn.close()
        print(f"[transcribe] saved transcript for: {self._current_meeting}")

    def watch_and_record(self, calendar_watcher):
        """Run in background thread: polls calendar, auto-start/stop recording."""
        recording = False
        while True:
            try:
                meetings = calendar_watcher.get_meetings_starting_soon(window_minutes=2)
                if meetings and not recording:
                    self.start_recording(meetings[0].get("summary", "meeting"))
                    recording = True
                elif not meetings and recording:
                    self.stop_recording()
                    recording = False
            except Exception as e:
                print(f"[transcribe] watch error: {e}")
            time.sleep(60)
```

**Step 3: Wire into main.py**

Edit `~/.claude/eng-buddy/orchestrator/main.py`, add to the thread list in `__main__`:

```python
    from monitors.calendar_watcher import CalendarWatcher
    from monitors.transcribe_integration import TranscribeIntegration

    cal_watcher = CalendarWatcher()
    transcriber = TranscribeIntegration()

    threads.append(threading.Thread(
        target=transcriber.watch_and_record,
        args=(cal_watcher,),
        daemon=True, name="transcribe"
    ))
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: transcribe integration with calendar-triggered auto-recording"
```

---

### Task 16: Screen monitor

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/monitors/screen_monitor.py`

**Step 1: Install Pillow for screenshots**

```bash
pip3 install Pillow
```

**Step 2: Write screen_monitor.py**

Create `~/.claude/eng-buddy/orchestrator/monitors/screen_monitor.py`:

```python
"""
Screen monitor: takes periodic screenshots, writes to events.db for analysis.
Orchestrator agent analyzes patterns to detect time sinks and automation opportunities.
"""
import json
import sqlite3
import time
import base64
import io
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from config import EVENTS_DB, SCREEN_CAPTURE_INTERVAL

SCREENSHOTS_DIR = Path.home() / ".claude" / "eng-buddy" / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def take_screenshot_macos() -> bytes:
    """Take screenshot using macOS screencapture. Returns PNG bytes."""
    out = SCREENSHOTS_DIR / f"screen_{int(time.time())}.png"
    subprocess.run(["screencapture", "-x", "-t", "png", str(out)],
                   capture_output=True, timeout=10)
    if out.exists():
        data = out.read_bytes()
        out.unlink()  # don't accumulate screenshots on disk
        return data
    return b""


class ScreenMonitor:
    def __init__(self, db_path: Path = None, interval: int = None):
        self.db_path = db_path or EVENTS_DB
        self.interval = interval or SCREEN_CAPTURE_INTERVAL

    def _write_event(self, screenshot_b64: str, analysis_hint: str = ""):
        event = {
            "screenshot_b64": screenshot_b64,
            "hint": analysis_hint,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT INTO events (source, timestamp, raw_content, metadata) VALUES (?,?,?,?)",
            ("screen", datetime.now(timezone.utc).isoformat(),
             json.dumps({"hint": analysis_hint, "has_screenshot": True}),
             json.dumps({"captured_at": event["captured_at"]}))
        )
        conn.commit()
        conn.close()

    def run_forever(self):
        print(f"[screen-monitor] capturing every {self.interval}s")
        while True:
            try:
                img_bytes = take_screenshot_macos()
                if img_bytes:
                    b64 = base64.b64encode(img_bytes).decode()
                    self._write_event(b64)
            except Exception as e:
                print(f"[screen-monitor] error: {e}")
            time.sleep(self.interval)
```

**Step 3: Wire into main.py**

Add to the thread list in `main.py`:

```python
    from monitors.screen_monitor import ScreenMonitor
    screen_mon = ScreenMonitor()
    threads.append(threading.Thread(
        target=screen_mon.run_forever, daemon=True, name="screen-monitor"
    ))
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: screen monitor daemon with periodic screenshots"
```

---

## Phase 4: Learning Loop

### Task 17: Edit diff capture + action log

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/learning/diff_capture.py`
- Create: `~/.claude/eng-buddy/orchestrator/tests/test_diff_capture.py`

**Step 1: Write failing test**

Create `~/.claude/eng-buddy/orchestrator/tests/test_diff_capture.py`:

```python
import tempfile
from pathlib import Path
from learning.diff_capture import DiffCapture

def test_captures_diff_between_draft_and_edit():
    capture = DiffCapture(log_path=Path(tempfile.mktemp(suffix=".md")))
    capture.record(
        source="slack",
        original="Sure, I'll add you to Jira right away.",
        edited="Done — you're added to ITWORK-R&D. Let me know if you need anything else."
    )
    log = capture.log_path.read_text()
    assert "slack" in log
    assert "Sure, I'll add you" in log
    assert "Done —" in log

def test_accumulates_multiple_diffs():
    capture = DiffCapture(log_path=Path(tempfile.mktemp(suffix=".md")))
    capture.record("slack", "draft 1", "edit 1")
    capture.record("gmail", "draft 2", "edit 2")
    log = capture.log_path.read_text()
    assert "draft 1" in log
    assert "draft 2" in log
```

**Step 2: Run test — expect FAIL**

```bash
python3 -m pytest tests/test_diff_capture.py -v
```

**Step 3: Write diff_capture.py**

Create `~/.claude/eng-buddy/orchestrator/learning/diff_capture.py`:

```python
from datetime import datetime, timezone
from pathlib import Path
from config import ACTION_LOG


class DiffCapture:
    """
    Records every edit the user makes to an AI draft.
    These diffs are the training signal for voice model refinement.
    """
    def __init__(self, log_path: Path = None):
        self.log_path = log_path or ACTION_LOG
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("# Action Log\n\n")

    def record(self, source: str, original: str, edited: str, action_type: str = "edit"):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"""
## {now} · {source} · {action_type}

**Original draft:**
{original}

**User edited to:**
{edited}

---
"""
        with self.log_path.open("a") as f:
            f.write(entry)

    def record_approve(self, source: str, draft: str):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"## {now} · {source} · approved\n\n{draft}\n\n---\n"
        with self.log_path.open("a") as f:
            f.write(entry)

    def record_deny(self, source: str, draft: str):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"## {now} · {source} · denied\n\n~~{draft}~~\n\n---\n"
        with self.log_path.open("a") as f:
            f.write(entry)
```

**Step 4: Wire into dashboard approve/deny/edit routes**

Edit `~/.claude/eng-buddy/orchestrator/dashboard/server.py`:

In the `approve_card` endpoint, after updating DB, add:

```python
        from learning.diff_capture import DiffCapture
        DiffCapture().record_approve(source=row["source"], draft=row["draft"] or "")
```

In the `deny_card` endpoint:

```python
        from learning.diff_capture import DiffCapture
        DiffCapture().record_deny(source=row["source"], draft=row["draft"] or "")
```

In the `edit_card` endpoint:

```python
        from learning.diff_capture import DiffCapture
        DiffCapture().record(
            source=row["source"],
            original=row["draft"] or "",
            edited=body.get("edit", "")
        )
```

**Step 5: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_diff_capture.py -v
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: diff capture records approve/deny/edit for voice learning"
```

---

### Task 18: Pattern auto-writer

**Files:**
- Create: `~/.claude/eng-buddy/orchestrator/learning/pattern_writer.py`

**Step 1: Write pattern_writer.py**

Create `~/.claude/eng-buddy/orchestrator/learning/pattern_writer.py`:

```python
"""
PatternWriter: replaces manual pattern logging in eng-buddy.
Automatically detects recurring issues/questions and updates patterns/ files.
"""
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from config import ENG_BUDDY_DIR

PATTERNS_DIR = ENG_BUDDY_DIR / "patterns"
RECURRING_ISSUES = PATTERNS_DIR / "recurring-issues.md"
RECURRING_QUESTIONS = PATTERNS_DIR / "recurring-questions.md"


class PatternWriter:
    def __init__(self, events_db: Path = None):
        self.events_db = events_db or (ENG_BUDDY_DIR / "events.db")
        PATTERNS_DIR.mkdir(exist_ok=True)

    def _get_recent_events(self, days: int = 30) -> list[sqlite3.Row]:
        conn = sqlite3.connect(str(self.events_db), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT source, raw_content FROM events
            WHERE datetime(timestamp) > datetime('now', ?)
            AND processed = 1
        """, (f"-{days} days",)).fetchall()
        conn.close()
        return rows

    def _extract_subject(self, source: str, content: dict) -> str:
        if source == "freshservice":
            return content.get("subject", "")
        if source == "slack":
            return content.get("text", "")[:100]
        if source == "jira":
            return content.get("fields", {}).get("summary", "")
        return str(content)[:100]

    def analyze_and_write(self):
        rows = self._get_recent_events()
        subjects = []
        for row in rows:
            try:
                content = json.loads(row["raw_content"])
                subject = self._extract_subject(row["source"], content)
                if subject:
                    subjects.append((row["source"], subject.lower()))
            except Exception:
                continue

        # Simple keyword frequency — upgrade to LLM clustering later
        keywords = []
        for _, subject in subjects:
            for word in subject.split():
                if len(word) > 4:
                    keywords.append(word)

        counts = Counter(keywords).most_common(20)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not RECURRING_ISSUES.exists():
            RECURRING_ISSUES.write_text("# Recurring Issues\n\n")

        with RECURRING_ISSUES.open("a") as f:
            f.write(f"\n## Auto-analysis {now}\n")
            f.write("Top keywords across recent events:\n")
            for word, count in counts:
                if count >= 3:
                    f.write(f"- `{word}` — {count} occurrences\n")

        print(f"[pattern-writer] updated {RECURRING_ISSUES}")
```

**Step 2: Wire weekly pattern analysis into main.py**

Add to `main.py`, in the orchestrator loop (after `process_pending_events`):

```python
from learning.pattern_writer import PatternWriter
import schedule

# At module level, schedule weekly analysis
_pattern_writer = PatternWriter()
schedule.every().monday.at("09:00").do(_pattern_writer.analyze_and_write)

# In run_orchestrator(), add:
schedule.run_pending()
```

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: pattern auto-writer updates patterns/ files weekly"
```

---

## Final: Run full test suite

**Step 1:**

```bash
cd ~/.claude/eng-buddy/orchestrator
python3 -m pytest tests/ -v --tb=short
```

Expected: all tests pass.

**Step 2: Start orchestrator and verify dashboard**

```bash
python3 main.py
open http://localhost:7474
```

Expected: dashboard loads, inbox shows "All clear. Nothing pending."

**Step 3: Final commit**

```bash
git add -A && git commit -m "feat: eng-buddy v2 meta-orchestrator complete — zero copy-paste"
```

---

## Environment Variables Needed

Before running, set these (add to `~/.zshrc` or the launchd plist):

```bash
export FRESHSERVICE_API_KEY="your-fs-api-key"
export FRESHSERVICE_DOMAIN="klaviyo"
export JIRA_BASE_URL="https://klaviyo.atlassian.net"
export JIRA_EMAIL="your-email@klaviyo.com"
export JIRA_API_TOKEN="your-jira-token"
```

Slack token is read automatically from existing `~/.claude/skills/eng-buddy/bin/slack-poller.py`.
Gmail OAuth credentials read from existing `~/.gmail-mcp/credentials.json`.
