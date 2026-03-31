# Playbook Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a playbook engine to eng-buddy that observes how the user works tickets, distills repeatable processes into executable playbooks, and runs them autonomously with human-in-the-loop approval.

**Architecture:** Extends brain.py with workflow tracing, playbook extraction, and execution orchestration. Playbooks stored as YAML in `~/.claude/eng-buddy/playbooks/`. Tool registry maps available MCPs/scripts to action bindings. Dashboard gets a new "Playbooks" tab for review, approval, and execution monitoring. Hooks expanded to capture conversation signals (instructions, corrections, decisions) alongside tool calls.

**Tech Stack:** Python 3 (brain.py extensions), FastAPI (dashboard), YAML (playbook storage), SQLite (execution state), SSE (live progress), Shell (hook integration)

**Design doc:** `docs/plans/2026-03-09-playbook-engine-design.md`

---

## Task 1: Playbook Directory Structure & Data Model

**Files:**
- Create: `~/.claude/eng-buddy/playbooks/.gitkeep`
- Create: `~/.claude/eng-buddy/playbooks/drafts/.gitkeep`
- Create: `~/.claude/eng-buddy/playbooks/archive/.gitkeep`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/_registry.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/jira.defaults.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/freshservice.defaults.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/slack.defaults.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/gmail.defaults.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/playwright.defaults.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/confluence.defaults.yml`
- Create: `~/.claude/eng-buddy/playbooks/tool-registry/scripts.defaults.yml`

**Step 1: Create directory structure**

```bash
mkdir -p ~/.claude/eng-buddy/playbooks/{drafts,archive,tool-registry}
touch ~/.claude/eng-buddy/playbooks/.gitkeep
touch ~/.claude/eng-buddy/playbooks/drafts/.gitkeep
touch ~/.claude/eng-buddy/playbooks/archive/.gitkeep
```

**Step 2: Create core tool registry**

Write `~/.claude/eng-buddy/playbooks/tool-registry/_registry.yml`:

```yaml
# Tool Registry - Core catalog of available tools
# Each tool entry defines type, MCP prefix, capabilities, auth model, and domains
# Per-tool defaults live in separate {tool}.defaults.yml files

tools:
  jira:
    type: mcp
    prefix: mcp__mcp-atlassian__jira_
    capabilities:
      - create_issue
      - update_issue
      - transition_issue
      - add_comment
      - search
      - get_issue
      - add_worklog
    auth: persistent
    domains: [ticket_management, project_tracking]

  freshservice:
    type: mcp
    prefix: mcp__freshservice-mcp__
    capabilities:
      - create_ticket
      - update_ticket
      - send_ticket_reply
      - filter_tickets
      - create_ticket_note
      - get_ticket_by_id
    auth: persistent
    domains: [ticket_management, service_desk]

  slack:
    type: mcp
    prefix: mcp__slack__
    capabilities:
      - post_message
      - reply_to_thread
      - get_channel_history
      - get_thread_replies
      - list_channels
    auth: persistent
    domains: [communication, notifications]

  gmail:
    type: mcp
    prefix: mcp__gmail__
    capabilities:
      - send_email
      - search_emails
      - draft_email
      - read_email
      - modify_email
    auth: persistent
    domains: [communication, notifications]

  google_calendar:
    type: mcp
    prefix: mcp__google-calendar__
    capabilities:
      - create_event
      - list_events
      - update_event
      - get_freebusy
    auth: persistent
    domains: [scheduling]

  confluence:
    type: mcp
    prefix: mcp__mcp-atlassian__confluence_
    capabilities:
      - create_page
      - update_page
      - search
      - get_page
    auth: persistent
    domains: [documentation]

  playwright:
    type: browser
    prefix: mcp__playwright__
    capabilities:
      - navigate
      - click
      - fill_form
      - screenshot
      - snapshot
      - type
      - select_option
    auth: per_domain
    auth_store: ~/.claude/eng-buddy/auth/sessions.enc
    domains: [web_admin, sso_config, any_web_ui]
    fallback: human_handoff

  local_scripts:
    type: script
    path: ~/.claude/eng-buddy/bin/
    discovery: automatic
    auth: none
    domains: [data_processing, automation, utilities]

  claude:
    type: ai
    capabilities:
      - generate_text
      - analyze_data
      - draft_response
      - extract_fields
    auth: none
    domains: [content_generation, analysis, decision_making]
```

**Step 3: Create Jira defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/jira.defaults.yml`:

```yaml
# Jira tool defaults - merged into playbook steps at execution time
create_issue:
  assignee: "kioja.kudumu@klaviyo.com"
  board_id: 70
  sprint: current  # resolved via API at execution time
  epic: null       # set per-playbook
  labels: []

transition_issue:
  notify: true

add_comment:
  visibility: null  # public by default

field_mappings:
  sprint_field: "customfield_10020"
  story_points: "customfield_10028"
```

**Step 4: Create Freshservice defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/freshservice.defaults.yml`:

```yaml
create_ticket:
  requester: "kioja.kudumu@klaviyo.com"
  workspace: "IT"

send_ticket_reply:
  tone: "professional"

update_ticket:
  notify_requester: true
```

**Step 5: Create Slack defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/slack.defaults.yml`:

```yaml
post_message:
  as_user: true

reply_to_thread:
  as_user: true
```

**Step 6: Create Gmail defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/gmail.defaults.yml`:

```yaml
send_email:
  from: "kioja.kudumu@klaviyo.com"
  signature: true

draft_email:
  from: "kioja.kudumu@klaviyo.com"
```

**Step 7: Create Playwright defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/playwright.defaults.yml`:

```yaml
domains:
  okta_admin:
    base_url: "https://klaviyo.okta.com/admin"
    auth_method: stored_session
  google_admin:
    base_url: "https://admin.google.com"
    auth_method: human_handoff
  conductor_one:
    base_url: "https://app.conductorone.com"
    auth_method: stored_session
```

**Step 8: Create Confluence defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/confluence.defaults.yml`:

```yaml
create_page:
  space: "IT"

update_page:
  notify_watchers: false
```

**Step 9: Create scripts defaults**

Write `~/.claude/eng-buddy/playbooks/tool-registry/scripts.defaults.yml`:

```yaml
# Local scripts auto-discovered from ~/.claude/eng-buddy/bin/
# This file documents known scripts and their conventions

known_scripts:
  brain.py:
    description: "Learning engine - captures and routes knowledge"
    invoke: "python3 ~/.claude/eng-buddy/bin/brain.py"
  gtmsys-filter.py:
    description: "Jira audit log filtering"
    invoke: "python3 ~/.claude/eng-buddy/bin/gtmsys-filter.py"
```

**Step 10: Commit**

```bash
git add -f ~/.claude/eng-buddy/playbooks/
git commit -m "Add playbook directory structure and tool registry"
```

---

## Task 2: Playbook Python Module — Data Model & Registry Loader

**Files:**
- Create: `~/.claude/eng-buddy/bin/playbook_engine/__init__.py`
- Create: `~/.claude/eng-buddy/bin/playbook_engine/models.py`
- Create: `~/.claude/eng-buddy/bin/playbook_engine/registry.py`
- Test: `~/.claude/eng-buddy/bin/playbook_engine/test_models.py`
- Test: `~/.claude/eng-buddy/bin/playbook_engine/test_registry.py`

**Step 1: Write failing test for playbook model**

Write `~/.claude/eng-buddy/bin/playbook_engine/test_models.py`:

```python
import pytest
import yaml
import tempfile
import os
from models import Playbook, PlaybookStep, ActionBinding, ParamSource

def test_playbook_from_yaml():
    raw = {
        "id": "sso-onboarding",
        "name": "SSO Onboarding",
        "version": 1,
        "confidence": "low",
        "trigger_patterns": [
            {"ticket_type": "Service Request", "keywords": ["SSO", "SAML"], "source": ["freshservice"]}
        ],
        "created_from": "session",
        "executions": 0,
        "steps": [
            {
                "id": 1,
                "name": "Create Jira ticket",
                "action": {
                    "tool": "mcp__mcp-atlassian__jira_create_issue",
                    "params": {"project": "ITWORK2", "summary": "[SSO] {{app_name}}"},
                    "param_sources": {"app_name": {"from": "trigger_ticket", "field": "subject", "extract": "app name"}}
                },
                "auth_required": False,
                "human_required": False,
            }
        ],
    }
    pb = Playbook.from_dict(raw)
    assert pb.id == "sso-onboarding"
    assert pb.confidence == "low"
    assert len(pb.steps) == 1
    assert pb.steps[0].action.tool == "mcp__mcp-atlassian__jira_create_issue"
    assert pb.steps[0].action.param_sources["app_name"].field == "subject"

def test_playbook_round_trip_yaml(tmp_path):
    raw = {
        "id": "test-pb",
        "name": "Test Playbook",
        "version": 1,
        "confidence": "medium",
        "trigger_patterns": [],
        "created_from": "dictated",
        "executions": 0,
        "steps": [],
    }
    pb = Playbook.from_dict(raw)
    path = tmp_path / "test-pb.yml"
    pb.save(str(path))
    loaded = Playbook.load(str(path))
    assert loaded.id == pb.id
    assert loaded.version == pb.version

def test_playbook_matches_ticket():
    raw = {
        "id": "sso",
        "name": "SSO",
        "version": 1,
        "confidence": "high",
        "trigger_patterns": [
            {"ticket_type": "Service Request", "keywords": ["SSO", "SAML"], "source": ["freshservice"]}
        ],
        "created_from": "session",
        "executions": 3,
        "steps": [],
    }
    pb = Playbook.from_dict(raw)
    assert pb.matches(ticket_type="Service Request", text="Set up SSO for Linear", source="freshservice")
    assert not pb.matches(ticket_type="Incident", text="Server is down", source="freshservice")
    assert not pb.matches(ticket_type="Service Request", text="New laptop request", source="freshservice")

def test_confidence_progression():
    raw = {
        "id": "t",
        "name": "T",
        "version": 1,
        "confidence": "low",
        "trigger_patterns": [],
        "created_from": "session",
        "executions": 0,
        "steps": [],
    }
    pb = Playbook.from_dict(raw)
    pb.record_execution(success=True)
    assert pb.confidence == "medium"
    assert pb.executions == 1
    pb.record_execution(success=True)
    pb.record_execution(success=True)
    assert pb.confidence == "high"
    assert pb.executions == 3
```

**Step 2: Run test to verify it fails**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'models'`

**Step 3: Write `__init__.py`**

Write `~/.claude/eng-buddy/bin/playbook_engine/__init__.py`:

```python
"""Playbook Engine for eng-buddy — automated ticket execution with human-in-the-loop approval."""
```

**Step 4: Write minimal models implementation**

Write `~/.claude/eng-buddy/bin/playbook_engine/models.py`:

```python
"""Playbook data model — versioned, executable documents with action-bound steps."""

import yaml
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class ParamSource:
    from_: str  # "trigger_ticket", "calculation", "user_input"
    field: Optional[str] = None
    extract: Optional[str] = None
    calculate: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ParamSource":
        return cls(from_=d.get("from", ""), field=d.get("field"), extract=d.get("extract"), calculate=d.get("calculate"))

    def to_dict(self) -> dict:
        d = {"from": self.from_}
        if self.field:
            d["field"] = self.field
        if self.extract:
            d["extract"] = self.extract
        if self.calculate:
            d["calculate"] = self.calculate
        return d


@dataclass
class ActionBinding:
    tool: str
    params: dict = field(default_factory=dict)
    param_sources: dict = field(default_factory=dict)  # key -> ParamSource
    navigate_to: Optional[str] = None
    prefill: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ActionBinding":
        param_sources = {}
        for k, v in d.get("param_sources", {}).items():
            param_sources[k] = ParamSource.from_dict(v)
        return cls(
            tool=d["tool"],
            params=d.get("params", {}),
            param_sources=param_sources,
            navigate_to=d.get("navigate_to"),
            prefill=d.get("prefill", []),
        )

    def to_dict(self) -> dict:
        d = {"tool": self.tool}
        if self.params:
            d["params"] = self.params
        if self.param_sources:
            d["param_sources"] = {k: v.to_dict() for k, v in self.param_sources.items()}
        if self.navigate_to:
            d["navigate_to"] = self.navigate_to
        if self.prefill:
            d["prefill"] = self.prefill
        return d


@dataclass
class PlaybookStep:
    id: int
    name: str
    action: ActionBinding
    auth_required: bool = False
    auth_method: Optional[str] = None  # "stored_session", "human_handoff"
    human_required: bool = False
    optional: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "PlaybookStep":
        return cls(
            id=d["id"],
            name=d["name"],
            action=ActionBinding.from_dict(d["action"]),
            auth_required=d.get("auth_required", False),
            auth_method=d.get("auth_method"),
            human_required=d.get("human_required", False),
            optional=d.get("optional", False),
        )

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "action": self.action.to_dict(),
            "auth_required": self.auth_required,
            "human_required": self.human_required,
        }
        if self.auth_method:
            d["auth_method"] = self.auth_method
        if self.optional:
            d["optional"] = self.optional
        return d


@dataclass
class TriggerPattern:
    ticket_type: Optional[str] = None
    keywords: list = field(default_factory=list)
    source: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "TriggerPattern":
        return cls(ticket_type=d.get("ticket_type"), keywords=d.get("keywords", []), source=d.get("source", []))

    def matches(self, ticket_type: str = "", text: str = "", source: str = "") -> bool:
        if self.ticket_type and self.ticket_type.lower() != ticket_type.lower():
            return False
        if self.source and source.lower() not in [s.lower() for s in self.source]:
            return False
        if self.keywords:
            text_lower = text.lower()
            if not any(kw.lower() in text_lower for kw in self.keywords):
                return False
        return True

    def to_dict(self) -> dict:
        d = {}
        if self.ticket_type:
            d["ticket_type"] = self.ticket_type
        if self.keywords:
            d["keywords"] = self.keywords
        if self.source:
            d["source"] = self.source
        return d


CONFIDENCE_ORDER = ["low", "medium", "high"]


@dataclass
class Playbook:
    id: str
    name: str
    version: int
    confidence: str  # low, medium, high
    trigger_patterns: list  # list of TriggerPattern
    created_from: str  # session, dictated, pattern-detection
    executions: int
    steps: list  # list of PlaybookStep
    last_executed: Optional[str] = None
    last_updated: Optional[str] = None
    update_history: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Playbook":
        triggers = [TriggerPattern.from_dict(t) for t in d.get("trigger_patterns", [])]
        steps = [PlaybookStep.from_dict(s) for s in d.get("steps", [])]
        return cls(
            id=d["id"],
            name=d["name"],
            version=d.get("version", 1),
            confidence=d.get("confidence", "low"),
            trigger_patterns=triggers,
            created_from=d.get("created_from", "session"),
            executions=d.get("executions", 0),
            steps=steps,
            last_executed=d.get("last_executed"),
            last_updated=d.get("last_updated"),
            update_history=d.get("update_history", []),
        )

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "confidence": self.confidence,
            "trigger_patterns": [t.to_dict() for t in self.trigger_patterns],
            "created_from": self.created_from,
            "executions": self.executions,
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.last_executed:
            d["last_executed"] = self.last_executed
        if self.last_updated:
            d["last_updated"] = self.last_updated
        if self.update_history:
            d["update_history"] = self.update_history
        return d

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, path: str) -> "Playbook":
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    def matches(self, ticket_type: str = "", text: str = "", source: str = "") -> bool:
        return any(t.matches(ticket_type, text, source) for t in self.trigger_patterns)

    def record_execution(self, success: bool) -> None:
        self.executions += 1
        if success:
            idx = CONFIDENCE_ORDER.index(self.confidence)
            if self.executions >= 3 and idx < 2:
                self.confidence = "high"
            elif self.executions >= 1 and idx < 1:
                self.confidence = "medium"
        else:
            idx = CONFIDENCE_ORDER.index(self.confidence)
            if idx > 0:
                self.confidence = CONFIDENCE_ORDER[idx - 1]
```

**Step 5: Run tests to verify they pass**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_models.py -v
```
Expected: All 4 tests PASS

**Step 6: Write failing test for registry loader**

Write `~/.claude/eng-buddy/bin/playbook_engine/test_registry.py`:

```python
import pytest
import yaml
import tempfile
import os
from registry import ToolRegistry

def test_load_registry(tmp_path):
    reg_dir = tmp_path / "tool-registry"
    reg_dir.mkdir()

    (reg_dir / "_registry.yml").write_text(yaml.dump({
        "tools": {
            "jira": {
                "type": "mcp",
                "prefix": "mcp__mcp-atlassian__jira_",
                "capabilities": ["create_issue"],
                "auth": "persistent",
                "domains": ["ticket_management"],
            }
        }
    }))

    (reg_dir / "jira.defaults.yml").write_text(yaml.dump({
        "create_issue": {"assignee": "test@test.com", "board_id": 70},
        "field_mappings": {"sprint_field": "customfield_10020"},
    }))

    reg = ToolRegistry(str(reg_dir))
    assert "jira" in reg.tools
    assert reg.tools["jira"]["type"] == "mcp"
    assert reg.get_defaults("jira", "create_issue")["assignee"] == "test@test.com"

def test_get_defaults_missing_tool(tmp_path):
    reg_dir = tmp_path / "tool-registry"
    reg_dir.mkdir()
    (reg_dir / "_registry.yml").write_text(yaml.dump({"tools": {}}))
    reg = ToolRegistry(str(reg_dir))
    assert reg.get_defaults("nonexistent", "action") == {}

def test_merge_params(tmp_path):
    reg_dir = tmp_path / "tool-registry"
    reg_dir.mkdir()
    (reg_dir / "_registry.yml").write_text(yaml.dump({
        "tools": {"jira": {"type": "mcp", "prefix": "p_", "capabilities": [], "auth": "persistent", "domains": []}}
    }))
    (reg_dir / "jira.defaults.yml").write_text(yaml.dump({
        "create_issue": {"assignee": "default@test.com", "board_id": 70},
    }))
    reg = ToolRegistry(str(reg_dir))
    merged = reg.merge_params("jira", "create_issue", {"summary": "Test", "assignee": "override@test.com"})
    assert merged["assignee"] == "override@test.com"  # playbook overrides default
    assert merged["board_id"] == 70  # default fills in
    assert merged["summary"] == "Test"  # playbook-specific preserved

def test_resolve_tool_from_mcp_name(tmp_path):
    reg_dir = tmp_path / "tool-registry"
    reg_dir.mkdir()
    (reg_dir / "_registry.yml").write_text(yaml.dump({
        "tools": {
            "jira": {"type": "mcp", "prefix": "mcp__mcp-atlassian__jira_", "capabilities": [], "auth": "persistent", "domains": []},
            "slack": {"type": "mcp", "prefix": "mcp__slack__", "capabilities": [], "auth": "persistent", "domains": []},
        }
    }))
    reg = ToolRegistry(str(reg_dir))
    assert reg.resolve_tool_name("mcp__mcp-atlassian__jira_create_issue") == ("jira", "create_issue")
    assert reg.resolve_tool_name("mcp__slack__post_message") == ("slack", "post_message")
    assert reg.resolve_tool_name("unknown_tool") == (None, None)
```

**Step 7: Run test to verify it fails**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_registry.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'registry'`

**Step 8: Write registry implementation**

Write `~/.claude/eng-buddy/bin/playbook_engine/registry.py`:

```python
"""Tool Registry — modular catalog of available tools, capabilities, and defaults."""

import yaml
from pathlib import Path
from typing import Optional


class ToolRegistry:
    def __init__(self, registry_dir: str):
        self.registry_dir = Path(registry_dir)
        self.tools: dict = {}
        self._defaults: dict = {}  # tool_name -> {action -> {param: value}}
        self._load()

    def _load(self) -> None:
        reg_path = self.registry_dir / "_registry.yml"
        if reg_path.exists():
            with open(reg_path) as f:
                data = yaml.safe_load(f) or {}
            self.tools = data.get("tools", {})

        # Load per-tool defaults
        for yml in self.registry_dir.glob("*.defaults.yml"):
            tool_name = yml.stem.replace(".defaults", "")
            with open(yml) as f:
                self._defaults[tool_name] = yaml.safe_load(f) or {}

    def get_defaults(self, tool_name: str, action: str) -> dict:
        tool_defaults = self._defaults.get(tool_name, {})
        return dict(tool_defaults.get(action, {}))

    def merge_params(self, tool_name: str, action: str, playbook_params: dict) -> dict:
        defaults = self.get_defaults(tool_name, action)
        defaults.update(playbook_params)
        return defaults

    def get_tool_info(self, tool_name: str) -> Optional[dict]:
        return self.tools.get(tool_name)

    def resolve_tool_name(self, mcp_tool_name: str) -> tuple:
        """Given a full MCP tool name like mcp__slack__post_message, return (tool_name, action)."""
        for name, info in self.tools.items():
            prefix = info.get("prefix", "")
            if prefix and mcp_tool_name.startswith(prefix):
                action = mcp_tool_name[len(prefix):]
                return (name, action)
        return (None, None)

    def get_auth_requirement(self, tool_name: str) -> str:
        info = self.tools.get(tool_name, {})
        return info.get("auth", "none")

    def list_tools_for_domain(self, domain: str) -> list:
        return [
            name for name, info in self.tools.items()
            if domain in info.get("domains", [])
        ]
```

**Step 9: Run tests to verify they pass**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_registry.py -v
```
Expected: All 4 tests PASS

**Step 10: Commit**

```bash
git add -f ~/.claude/eng-buddy/bin/playbook_engine/
git commit -m "Add playbook data model and tool registry loader"
```

---

## Task 3: Expanded Trace Capture — Conversation Signals

**Files:**
- Create: `~/.claude/eng-buddy/bin/playbook_engine/tracer.py`
- Create: `~/.claude/eng-buddy/bin/playbook_engine/test_tracer.py`
- Create: `~/.claude/eng-buddy/traces/active/.gitkeep`

**Step 1: Write failing test for tracer**

Write `~/.claude/eng-buddy/bin/playbook_engine/test_tracer.py`:

```python
import pytest
import json
import tempfile
import os
from tracer import WorkflowTracer, TraceEvent

def test_add_tool_call_event():
    tracer = WorkflowTracer(traces_dir=tempfile.mkdtemp())
    tracer.start_trace("ITWORK2-1234")
    tracer.add_event(TraceEvent(
        type="tool_call",
        tool="mcp__mcp-atlassian__jira_create_issue",
        params={"project": "ITWORK2", "summary": "Test"},
    ))
    trace = tracer.get_trace("ITWORK2-1234")
    assert len(trace["events"]) == 1
    assert trace["events"][0]["type"] == "tool_call"

def test_add_user_instruction_event():
    tracer = WorkflowTracer(traces_dir=tempfile.mkdtemp())
    tracer.start_trace("ITWORK2-1234")
    tracer.add_event(TraceEvent(
        type="user_instruction",
        content="Always set due date to 30 days out",
        applies_to=["jira.create_issue"],
        persist=True,
    ))
    trace = tracer.get_trace("ITWORK2-1234")
    assert trace["events"][0]["type"] == "user_instruction"
    assert trace["events"][0]["persist"] is True

def test_add_user_correction_event():
    tracer = WorkflowTracer(traces_dir=tempfile.mkdtemp())
    tracer.start_trace("ITWORK2-1234")
    tracer.add_event(TraceEvent(
        type="user_correction",
        content="No, assign to next sprint",
        corrects="tool_defaults.jira.create_issue.sprint",
        new_value="next",
    ))
    trace = tracer.get_trace("ITWORK2-1234")
    assert trace["events"][0]["corrects"] == "tool_defaults.jira.create_issue.sprint"

def test_add_manual_action_event():
    tracer = WorkflowTracer(traces_dir=tempfile.mkdtemp())
    tracer.start_trace("ITWORK2-1234")
    tracer.add_event(TraceEvent(
        type="user_manual_action",
        content="I configured SAML in Okta",
        inferred_step="Configure SAML in IdP",
        action_binding="playwright",
        auth_note="needs Okta admin",
    ))
    trace = tracer.get_trace("ITWORK2-1234")
    assert trace["events"][0]["action_binding"] == "playwright"

def test_trace_persists_to_disk():
    traces_dir = tempfile.mkdtemp()
    tracer = WorkflowTracer(traces_dir=traces_dir)
    tracer.start_trace("ITWORK2-5678")
    tracer.add_event(TraceEvent(type="tool_call", tool="test_tool"))
    tracer.flush("ITWORK2-5678")
    path = os.path.join(traces_dir, "active", "ITWORK2-5678.json")
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert len(data["events"]) == 1

def test_similarity_score():
    tracer = WorkflowTracer(traces_dir=tempfile.mkdtemp())
    tracer.start_trace("t1")
    tracer.add_event(TraceEvent(type="tool_call", tool="jira_create"))
    tracer.add_event(TraceEvent(type="tool_call", tool="slack_post"))
    tracer.add_event(TraceEvent(type="tool_call", tool="freshservice_update"))

    tracer.start_trace("t2")
    tracer.add_event(TraceEvent(type="tool_call", tool="jira_create"))
    tracer.add_event(TraceEvent(type="tool_call", tool="slack_post"))
    tracer.add_event(TraceEvent(type="tool_call", tool="freshservice_update"))

    score = tracer.similarity("t1", "t2")
    assert score >= 0.9  # nearly identical tool sequences
```

**Step 2: Run test to verify it fails**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_tracer.py -v
```
Expected: FAIL

**Step 3: Write tracer implementation**

Write `~/.claude/eng-buddy/bin/playbook_engine/tracer.py`:

```python
"""Workflow Tracer — captures tool calls, user instructions, corrections, and manual actions as structured traces."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class TraceEvent:
    type: str  # tool_call, user_instruction, user_correction, user_manual_action, user_decision, question_asked
    # Common
    content: Optional[str] = None
    timestamp: Optional[str] = None
    # tool_call
    tool: Optional[str] = None
    params: Optional[dict] = None
    # user_instruction
    applies_to: Optional[list] = None
    persist: Optional[bool] = None
    # user_correction
    corrects: Optional[str] = None
    new_value: Optional[str] = None
    # user_manual_action
    inferred_step: Optional[str] = None
    action_binding: Optional[str] = None
    auth_note: Optional[str] = None
    # user_decision
    context: Optional[str] = None
    decision: Optional[str] = None
    rationale: Optional[str] = None
    # question_asked
    resolution: Optional[str] = None
    prefill_next_time: Optional[bool] = None
    # inferred
    inferred_intent: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "timestamp": self.timestamp}
        # Include only non-None fields relevant to this event type
        for k, v in asdict(self).items():
            if v is not None and k != "type" and k != "timestamp":
                d[k] = v
        return d


class WorkflowTracer:
    def __init__(self, traces_dir: str):
        self.traces_dir = Path(traces_dir)
        self.active_dir = self.traces_dir / "active"
        self.active_dir.mkdir(parents=True, exist_ok=True)
        self._traces: dict = {}  # trace_id -> {"events": [], "started_at": str}
        self._active_trace_id: Optional[str] = None

    def start_trace(self, trace_id: str) -> None:
        self._active_trace_id = trace_id
        if trace_id not in self._traces:
            self._traces[trace_id] = {
                "trace_id": trace_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "events": [],
            }

    def add_event(self, event: TraceEvent) -> None:
        trace_id = self._active_trace_id
        if not trace_id or trace_id not in self._traces:
            return
        if not event.timestamp:
            event.timestamp = datetime.now(timezone.utc).isoformat()
        self._traces[trace_id]["events"].append(event.to_dict())

    def get_trace(self, trace_id: str) -> Optional[dict]:
        return self._traces.get(trace_id)

    def flush(self, trace_id: str) -> None:
        trace = self._traces.get(trace_id)
        if not trace:
            return
        path = self.active_dir / f"{trace_id}.json"
        with open(path, "w") as f:
            json.dump(trace, f, indent=2)

    def flush_all(self) -> None:
        for trace_id in list(self._traces):
            self.flush(trace_id)

    def load_trace(self, trace_id: str) -> Optional[dict]:
        path = self.active_dir / f"{trace_id}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            self._traces[trace_id] = data
            return data
        return None

    def list_traces(self) -> list:
        return [p.stem for p in self.active_dir.glob("*.json")]

    def get_tool_sequence(self, trace_id: str) -> list:
        trace = self._traces.get(trace_id, {})
        return [e.get("tool", "") for e in trace.get("events", []) if e.get("type") == "tool_call" and e.get("tool")]

    def similarity(self, trace_id_a: str, trace_id_b: str) -> float:
        """Compare two traces by their tool call sequences. Returns 0.0-1.0."""
        seq_a = self.get_tool_sequence(trace_id_a)
        seq_b = self.get_tool_sequence(trace_id_b)
        if not seq_a and not seq_b:
            return 1.0
        if not seq_a or not seq_b:
            return 0.0
        # Simple Jaccard + order similarity
        set_a, set_b = set(seq_a), set(seq_b)
        jaccard = len(set_a & set_b) / len(set_a | set_b) if set_a | set_b else 0.0
        # Order: longest common subsequence ratio
        lcs_len = _lcs_length(seq_a, seq_b)
        order_score = (2 * lcs_len) / (len(seq_a) + len(seq_b)) if (seq_a or seq_b) else 0.0
        return 0.5 * jaccard + 0.5 * order_score


def _lcs_length(a: list, b: list) -> int:
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]
```

**Step 4: Run tests to verify they pass**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_tracer.py -v
```
Expected: All 6 tests PASS

**Step 5: Create active traces directory**

```bash
mkdir -p ~/.claude/eng-buddy/traces/active
touch ~/.claude/eng-buddy/traces/active/.gitkeep
```

**Step 6: Commit**

```bash
git add -f ~/.claude/eng-buddy/bin/playbook_engine/tracer.py \
           ~/.claude/eng-buddy/bin/playbook_engine/test_tracer.py \
           ~/.claude/eng-buddy/traces/
git commit -m "Add workflow tracer for expanded conversation signal capture"
```

---

## Task 4: Playbook Extraction Pipeline

**Files:**
- Create: `~/.claude/eng-buddy/bin/playbook_engine/extractor.py`
- Create: `~/.claude/eng-buddy/bin/playbook_engine/test_extractor.py`

**Step 1: Write failing test for extractor**

Write `~/.claude/eng-buddy/bin/playbook_engine/test_extractor.py`:

```python
import pytest
import tempfile
import yaml
from tracer import WorkflowTracer, TraceEvent
from registry import ToolRegistry
from extractor import PlaybookExtractor
from models import Playbook

def make_registry(tmp_path):
    reg_dir = tmp_path / "tool-registry"
    reg_dir.mkdir()
    (reg_dir / "_registry.yml").write_text(yaml.dump({
        "tools": {
            "jira": {"type": "mcp", "prefix": "mcp__mcp-atlassian__jira_", "capabilities": ["create_issue"], "auth": "persistent", "domains": ["ticket_management"]},
            "slack": {"type": "mcp", "prefix": "mcp__slack__", "capabilities": ["post_message"], "auth": "persistent", "domains": ["communication"]},
            "freshservice": {"type": "mcp", "prefix": "mcp__freshservice-mcp__", "capabilities": ["update_ticket"], "auth": "persistent", "domains": ["service_desk"]},
        }
    }))
    (reg_dir / "jira.defaults.yml").write_text(yaml.dump({"create_issue": {"assignee": "test@test.com"}}))
    return ToolRegistry(str(reg_dir))

def test_extract_playbook_from_trace(tmp_path):
    registry = make_registry(tmp_path)
    tracer = WorkflowTracer(traces_dir=str(tmp_path / "traces"))

    tracer.start_trace("ITWORK2-100")
    tracer.add_event(TraceEvent(type="user_instruction", content="Do SSO onboarding for Linear"))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__mcp-atlassian__jira_create_issue", params={"project": "ITWORK2", "summary": "[SSO] Linear"}))
    tracer.add_event(TraceEvent(type="user_manual_action", content="Configured SAML in Okta", inferred_step="Configure SAML", action_binding="playwright", auth_note="needs Okta admin"))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__slack__post_message", params={"channel": "C123", "text": "SSO configured"}))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__freshservice-mcp__update_ticket", params={"ticket_id": 456, "status": "resolved"}))

    extractor = PlaybookExtractor(registry=registry)
    pb = extractor.extract_from_trace(tracer.get_trace("ITWORK2-100"), name="SSO Onboarding")

    assert pb.id == "sso-onboarding"
    assert pb.confidence == "low"
    assert pb.created_from == "session"
    assert len(pb.steps) == 4  # jira + manual + slack + freshservice
    assert pb.steps[0].action.tool == "mcp__mcp-atlassian__jira_create_issue"
    assert pb.steps[1].human_required is True  # manual action
    assert pb.steps[1].action.tool == "playwright"

def test_extract_identifies_dynamic_params(tmp_path):
    registry = make_registry(tmp_path)
    tracer = WorkflowTracer(traces_dir=str(tmp_path / "traces"))

    tracer.start_trace("t1")
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__mcp-atlassian__jira_create_issue", params={"project": "ITWORK2", "summary": "[SSO] Linear", "assignee": "test@test.com"}))

    extractor = PlaybookExtractor(registry=registry)
    pb = extractor.extract_from_trace(tracer.get_trace("t1"), name="Test")

    # assignee matches default, so should NOT be in playbook params (it comes from defaults)
    # summary is ticket-specific, so should be a param with a source
    step = pb.steps[0]
    assert "assignee" not in step.action.params  # comes from defaults
    assert "summary" in step.action.params or "summary" in step.action.param_sources

def test_extract_captures_user_rules(tmp_path):
    registry = make_registry(tmp_path)
    tracer = WorkflowTracer(traces_dir=str(tmp_path / "traces"))

    tracer.start_trace("t1")
    tracer.add_event(TraceEvent(type="user_rule", content="Always add SSO label", applies_to=["jira.create_issue"], persist=True))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__mcp-atlassian__jira_create_issue", params={"project": "ITWORK2"}))

    extractor = PlaybookExtractor(registry=registry)
    pb = extractor.extract_from_trace(tracer.get_trace("t1"), name="Test")
    assert pb is not None
    # The extractor should note persistent rules for default updates
    assert len(extractor.pending_default_updates) > 0
```

**Step 2: Run test to verify it fails**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_extractor.py -v
```
Expected: FAIL

**Step 3: Write extractor implementation**

Write `~/.claude/eng-buddy/bin/playbook_engine/extractor.py`:

```python
"""Playbook Extractor — converts workflow traces into draft playbooks."""

import re
from typing import Optional
from models import Playbook, PlaybookStep, ActionBinding, ParamSource, TriggerPattern
from registry import ToolRegistry


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class PlaybookExtractor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.pending_default_updates: list = []  # rules that should update tool defaults

    def extract_from_trace(self, trace: dict, name: str) -> Playbook:
        events = trace.get("events", [])
        steps = []
        step_id = 1

        for event in events:
            etype = event.get("type")

            if etype == "tool_call":
                step = self._step_from_tool_call(event, step_id)
                if step:
                    steps.append(step)
                    step_id += 1

            elif etype == "user_manual_action":
                step = self._step_from_manual_action(event, step_id)
                steps.append(step)
                step_id += 1

            elif etype in ("user_instruction", "user_rule"):
                if event.get("persist"):
                    self.pending_default_updates.append({
                        "content": event.get("content", ""),
                        "applies_to": event.get("applies_to", []),
                    })

        # Infer trigger patterns from first user_instruction
        trigger_patterns = []
        for event in events:
            if event.get("type") == "user_instruction" and event.get("content"):
                content = event["content"]
                keywords = self._extract_keywords(content)
                if keywords:
                    trigger_patterns.append(TriggerPattern(keywords=keywords, source=["freshservice", "jira"]))
                break

        return Playbook(
            id=_slugify(name),
            name=name,
            version=1,
            confidence="low",
            trigger_patterns=trigger_patterns,
            created_from="session",
            executions=0,
            steps=steps,
        )

    def _step_from_tool_call(self, event: dict, step_id: int) -> Optional[PlaybookStep]:
        tool_name = event.get("tool", "")
        params = dict(event.get("params", {}))

        resolved_name, action = self.registry.resolve_tool_name(tool_name)
        if resolved_name is None:
            # Unknown tool — still record it
            return PlaybookStep(
                id=step_id,
                name=f"Execute {tool_name}",
                action=ActionBinding(tool=tool_name, params=params),
            )

        # Separate default params from ticket-specific params
        defaults = self.registry.get_defaults(resolved_name, action) if action else {}
        playbook_params = {}
        param_sources = {}

        for k, v in params.items():
            if k in defaults and defaults[k] == v:
                continue  # matches default, don't include in playbook
            playbook_params[k] = v

        auth_req = self.registry.get_auth_requirement(resolved_name)

        return PlaybookStep(
            id=step_id,
            name=f"{action.replace('_', ' ').title() if action else tool_name}",
            action=ActionBinding(
                tool=tool_name,
                params=playbook_params,
                param_sources=param_sources,
            ),
            auth_required=auth_req == "per_domain",
        )

    def _step_from_manual_action(self, event: dict, step_id: int) -> PlaybookStep:
        return PlaybookStep(
            id=step_id,
            name=event.get("inferred_step", event.get("content", "Manual step")),
            action=ActionBinding(
                tool=event.get("action_binding", "human"),
                params={},
            ),
            auth_required=bool(event.get("auth_note")),
            auth_method="human_handoff",
            human_required=True,
        )

    def _extract_keywords(self, text: str) -> list:
        """Extract likely trigger keywords from a user instruction."""
        # Common IT task keywords
        known_keywords = [
            "SSO", "SAML", "SCIM", "OIDC", "onboarding", "offboarding",
            "certificate", "renewal", "provisioning", "deprovisioning",
            "access", "permissions", "MFA", "2FA", "password", "reset",
            "account", "license", "audit", "compliance",
        ]
        found = [kw for kw in known_keywords if kw.lower() in text.lower()]
        return found if found else []

    def extract_from_description(self, name: str, steps_text: list) -> Playbook:
        """Path 2: Create playbook from user-described steps."""
        steps = []
        for i, desc in enumerate(steps_text, 1):
            tool, action = self._infer_tool_for_description(desc)
            steps.append(PlaybookStep(
                id=i,
                name=desc,
                action=ActionBinding(tool=tool, params={}),
                auth_required=self.registry.get_auth_requirement(tool.split("__")[0] if "__" in tool else tool) == "per_domain",
            ))
        return Playbook(
            id=_slugify(name),
            name=name,
            version=1,
            confidence="medium",
            trigger_patterns=[],
            created_from="dictated",
            executions=0,
            steps=steps,
        )

    def _infer_tool_for_description(self, description: str) -> tuple:
        """Given a step description, infer which tool handles it."""
        desc_lower = description.lower()
        tool_hints = {
            "jira": ["jira", "ticket", "issue", "sprint", "epic", "story"],
            "freshservice": ["freshservice", "service request", "service desk"],
            "slack": ["slack", "message", "notify", "dm", "channel"],
            "gmail": ["email", "gmail", "mail", "send email"],
            "confluence": ["confluence", "wiki", "documentation", "page"],
            "playwright": ["browser", "configure", "admin console", "login", "navigate", "okta", "google admin"],
            "google_calendar": ["calendar", "meeting", "schedule", "event"],
        }
        for tool_name, hints in tool_hints.items():
            if any(h in desc_lower for h in hints):
                info = self.registry.get_tool_info(tool_name)
                prefix = info.get("prefix", tool_name) if info else tool_name
                return (prefix, None)
        return ("claude", None)  # default to AI for unknown steps
```

**Step 4: Run tests to verify they pass**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_extractor.py -v
```
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add -f ~/.claude/eng-buddy/bin/playbook_engine/extractor.py \
           ~/.claude/eng-buddy/bin/playbook_engine/test_extractor.py
git commit -m "Add playbook extraction pipeline from workflow traces"
```

---

## Task 5: Playbook Manager — Storage, Matching, and Evolution

**Files:**
- Create: `~/.claude/eng-buddy/bin/playbook_engine/manager.py`
- Create: `~/.claude/eng-buddy/bin/playbook_engine/test_manager.py`

**Step 1: Write failing test for manager**

Write `~/.claude/eng-buddy/bin/playbook_engine/test_manager.py`:

```python
import pytest
import tempfile
import os
from manager import PlaybookManager
from models import Playbook, PlaybookStep, ActionBinding, TriggerPattern

def make_playbook(id="test", name="Test", confidence="high", keywords=None, steps=None):
    return Playbook(
        id=id, name=name, version=1, confidence=confidence,
        trigger_patterns=[TriggerPattern(keywords=keywords or ["SSO"], source=["freshservice"])],
        created_from="session", executions=3,
        steps=steps or [],
    )

def test_save_and_load(tmp_path):
    mgr = PlaybookManager(str(tmp_path))
    pb = make_playbook()
    mgr.save(pb)
    loaded = mgr.get("test")
    assert loaded.id == "test"
    assert loaded.confidence == "high"

def test_list_playbooks(tmp_path):
    mgr = PlaybookManager(str(tmp_path))
    mgr.save(make_playbook(id="a", name="A"))
    mgr.save(make_playbook(id="b", name="B"))
    pbs = mgr.list_playbooks()
    assert len(pbs) == 2
    assert {p.id for p in pbs} == {"a", "b"}

def test_match_ticket(tmp_path):
    mgr = PlaybookManager(str(tmp_path))
    mgr.save(make_playbook(id="sso", keywords=["SSO", "SAML"]))
    mgr.save(make_playbook(id="cert", keywords=["certificate", "renewal"]))
    matches = mgr.match_ticket(ticket_type="Service Request", text="Set up SSO for Linear", source="freshservice")
    assert len(matches) == 1
    assert matches[0].id == "sso"

def test_save_draft(tmp_path):
    mgr = PlaybookManager(str(tmp_path))
    pb = make_playbook(id="draft-test", confidence="low")
    mgr.save_draft(pb)
    drafts = mgr.list_drafts()
    assert len(drafts) == 1
    assert drafts[0].id == "draft-test"

def test_promote_draft(tmp_path):
    mgr = PlaybookManager(str(tmp_path))
    pb = make_playbook(id="promote-test", confidence="low")
    mgr.save_draft(pb)
    mgr.promote_draft("promote-test")
    assert mgr.get("promote-test") is not None
    assert len(mgr.list_drafts()) == 0

def test_archive_version(tmp_path):
    mgr = PlaybookManager(str(tmp_path))
    pb = make_playbook(id="versioned", confidence="high")
    mgr.save(pb)
    pb.version = 2
    pb.update_history.append({"version": 2, "reason": "added step"})
    mgr.save(pb, archive_previous=True)
    loaded = mgr.get("versioned")
    assert loaded.version == 2
    archives = mgr.list_archive("versioned")
    assert len(archives) == 1
```

**Step 2: Run test to verify it fails**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_manager.py -v
```
Expected: FAIL

**Step 3: Write manager implementation**

Write `~/.claude/eng-buddy/bin/playbook_engine/manager.py`:

```python
"""Playbook Manager — storage, matching, promotion, versioning."""

import shutil
from pathlib import Path
from typing import Optional
from models import Playbook


class PlaybookManager:
    def __init__(self, playbooks_dir: str):
        self.base = Path(playbooks_dir)
        self.approved_dir = self.base
        self.drafts_dir = self.base / "drafts"
        self.archive_dir = self.base / "archive"
        for d in [self.approved_dir, self.drafts_dir, self.archive_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def save(self, playbook: Playbook, archive_previous: bool = False) -> str:
        path = self.approved_dir / f"{playbook.id}.yml"
        if archive_previous and path.exists():
            old = Playbook.load(str(path))
            self._archive(old)
        playbook.save(str(path))
        return str(path)

    def save_draft(self, playbook: Playbook) -> str:
        path = self.drafts_dir / f"{playbook.id}.yml"
        playbook.save(str(path))
        return str(path)

    def get(self, playbook_id: str) -> Optional[Playbook]:
        path = self.approved_dir / f"{playbook_id}.yml"
        if path.exists():
            return Playbook.load(str(path))
        return None

    def get_draft(self, playbook_id: str) -> Optional[Playbook]:
        path = self.drafts_dir / f"{playbook_id}.yml"
        if path.exists():
            return Playbook.load(str(path))
        return None

    def list_playbooks(self) -> list:
        return [
            Playbook.load(str(p))
            for p in sorted(self.approved_dir.glob("*.yml"))
            if p.name != "_registry.yml" and not p.name.endswith(".defaults.yml")
        ]

    def list_drafts(self) -> list:
        return [Playbook.load(str(p)) for p in sorted(self.drafts_dir.glob("*.yml"))]

    def match_ticket(self, ticket_type: str = "", text: str = "", source: str = "") -> list:
        matches = []
        for pb in self.list_playbooks():
            if pb.matches(ticket_type=ticket_type, text=text, source=source):
                matches.append(pb)
        return sorted(matches, key=lambda p: p.executions, reverse=True)

    def promote_draft(self, playbook_id: str) -> Optional[Playbook]:
        draft_path = self.drafts_dir / f"{playbook_id}.yml"
        if not draft_path.exists():
            return None
        pb = Playbook.load(str(draft_path))
        self.save(pb)
        draft_path.unlink()
        return pb

    def delete_draft(self, playbook_id: str) -> bool:
        path = self.drafts_dir / f"{playbook_id}.yml"
        if path.exists():
            path.unlink()
            return True
        return False

    def _archive(self, playbook: Playbook) -> None:
        archive_path = self.archive_dir / playbook.id
        archive_path.mkdir(parents=True, exist_ok=True)
        dest = archive_path / f"v{playbook.version}.yml"
        playbook.save(str(dest))

    def list_archive(self, playbook_id: str) -> list:
        archive_path = self.archive_dir / playbook_id
        if not archive_path.exists():
            return []
        return [Playbook.load(str(p)) for p in sorted(archive_path.glob("*.yml"))]
```

**Step 4: Run tests to verify they pass**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_manager.py -v
```
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add -f ~/.claude/eng-buddy/bin/playbook_engine/manager.py \
           ~/.claude/eng-buddy/bin/playbook_engine/test_manager.py
git commit -m "Add playbook manager for storage, matching, and versioning"
```

---

## Task 6: Brain.py Integration — Hook into Existing Learning Engine

**Files:**
- Modify: `~/.claude/eng-buddy/bin/brain.py` (add playbook CLI commands)
- Modify: `~/.claude/skills/eng-buddy/hooks/eng-buddy-learning-capture.sh` (feed tracer)

**Step 1: Read current brain.py CLI argument section**

```bash
grep -n "argparse\|add_argument\|parse_args" ~/.claude/eng-buddy/bin/brain.py
```

Identify the argument parser block to extend.

**Step 2: Add playbook CLI commands to brain.py**

Add these arguments to the existing argparse block in brain.py:

```python
# --- Playbook Engine Commands ---
parser.add_argument("--playbook-trace-event", action="store_true",
    help="Record a trace event (reads JSON from stdin: {trace_id, event})")
parser.add_argument("--playbook-extract", type=str, metavar="TRACE_ID",
    help="Extract a draft playbook from a completed trace")
parser.add_argument("--playbook-extract-name", type=str, default="Untitled",
    help="Name for the extracted playbook (used with --playbook-extract)")
parser.add_argument("--playbook-match", type=str, metavar="TEXT",
    help="Find playbooks matching ticket text")
parser.add_argument("--playbook-match-type", type=str, default="",
    help="Ticket type for matching (used with --playbook-match)")
parser.add_argument("--playbook-match-source", type=str, default="freshservice",
    help="Source system for matching (used with --playbook-match)")
parser.add_argument("--playbook-list", action="store_true",
    help="List all approved playbooks")
parser.add_argument("--playbook-list-drafts", action="store_true",
    help="List all draft playbooks")
parser.add_argument("--playbook-promote", type=str, metavar="PLAYBOOK_ID",
    help="Promote a draft playbook to approved")
```

Add the handler logic in the main block:

```python
import sys
import json

PLAYBOOKS_DIR = os.path.expanduser("~/.claude/eng-buddy/playbooks")
TRACES_DIR = os.path.expanduser("~/.claude/eng-buddy/traces")
REGISTRY_DIR = os.path.join(PLAYBOOKS_DIR, "tool-registry")

# Add to sys.path for playbook_engine imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "playbook_engine"))

if args.playbook_trace_event:
    from playbook_engine.tracer import WorkflowTracer, TraceEvent
    payload = json.load(sys.stdin)
    tracer = WorkflowTracer(traces_dir=TRACES_DIR)
    trace_id = payload["trace_id"]
    tracer.load_trace(trace_id) or tracer.start_trace(trace_id)
    event_data = payload["event"]
    tracer.add_event(TraceEvent(**event_data))
    tracer.flush(trace_id)
    print(json.dumps({"status": "ok", "trace_id": trace_id}))

elif args.playbook_extract:
    from playbook_engine.tracer import WorkflowTracer
    from playbook_engine.registry import ToolRegistry
    from playbook_engine.extractor import PlaybookExtractor
    from playbook_engine.manager import PlaybookManager
    tracer = WorkflowTracer(traces_dir=TRACES_DIR)
    trace = tracer.load_trace(args.playbook_extract)
    if not trace:
        print(json.dumps({"error": f"Trace {args.playbook_extract} not found"}))
        sys.exit(1)
    registry = ToolRegistry(REGISTRY_DIR)
    extractor = PlaybookExtractor(registry=registry)
    pb = extractor.extract_from_trace(trace, name=args.playbook_extract_name)
    manager = PlaybookManager(PLAYBOOKS_DIR)
    path = manager.save_draft(pb)
    print(json.dumps({"status": "ok", "playbook_id": pb.id, "path": path, "steps": len(pb.steps)}))

elif args.playbook_match:
    from playbook_engine.manager import PlaybookManager
    manager = PlaybookManager(PLAYBOOKS_DIR)
    matches = manager.match_ticket(
        ticket_type=args.playbook_match_type,
        text=args.playbook_match,
        source=args.playbook_match_source,
    )
    print(json.dumps({"matches": [{"id": m.id, "name": m.name, "confidence": m.confidence, "executions": m.executions} for m in matches]}))

elif args.playbook_list:
    from playbook_engine.manager import PlaybookManager
    manager = PlaybookManager(PLAYBOOKS_DIR)
    pbs = manager.list_playbooks()
    print(json.dumps({"playbooks": [{"id": p.id, "name": p.name, "confidence": p.confidence, "version": p.version, "executions": p.executions} for p in pbs]}))

elif args.playbook_list_drafts:
    from playbook_engine.manager import PlaybookManager
    manager = PlaybookManager(PLAYBOOKS_DIR)
    drafts = manager.list_drafts()
    print(json.dumps({"drafts": [{"id": d.id, "name": d.name, "confidence": d.confidence, "steps": len(d.steps)} for d in drafts]}))

elif args.playbook_promote:
    from playbook_engine.manager import PlaybookManager
    manager = PlaybookManager(PLAYBOOKS_DIR)
    pb = manager.promote_draft(args.playbook_promote)
    if pb:
        print(json.dumps({"status": "ok", "playbook_id": pb.id}))
    else:
        print(json.dumps({"error": f"Draft {args.playbook_promote} not found"}))
        sys.exit(1)
```

**Step 3: Update learning capture hook to feed tracer**

Add to `eng-buddy-learning-capture.sh`, after the existing `brain.py --capture-post-tool` call:

```bash
# --- Feed Playbook Tracer ---
# If there's an active trace (ticket context), also record in tracer
ACTIVE_TRACE_FILE="$HOME/.claude/eng-buddy/.active-trace-id"
if [ -f "$ACTIVE_TRACE_FILE" ]; then
    TRACE_ID=$(cat "$ACTIVE_TRACE_FILE")
    TOOL_NAME=$(echo "$HOOK_PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
    TOOL_INPUT=$(echo "$HOOK_PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('tool_input',{})))" 2>/dev/null)

    if [ -n "$TOOL_NAME" ]; then
        echo "{\"trace_id\": \"$TRACE_ID\", \"event\": {\"type\": \"tool_call\", \"tool\": \"$TOOL_NAME\", \"params\": $TOOL_INPUT}}" | \
            python3 "$HOME/.claude/eng-buddy/bin/brain.py" --playbook-trace-event 2>/dev/null
    fi
fi
```

**Step 4: Test the CLI integration**

```bash
# Test trace event recording
echo '{"trace_id":"test-123","event":{"type":"tool_call","tool":"mcp__slack__post_message","params":{"channel":"C1"}}}' | \
    python3 ~/.claude/eng-buddy/bin/brain.py --playbook-trace-event

# Test listing (should be empty initially)
python3 ~/.claude/eng-buddy/bin/brain.py --playbook-list
```

Expected: `{"status": "ok", "trace_id": "test-123"}` and `{"playbooks": []}`

**Step 5: Commit**

```bash
git add -f ~/.claude/eng-buddy/bin/brain.py \
           ~/.claude/skills/eng-buddy/hooks/eng-buddy-learning-capture.sh
git commit -m "Integrate playbook engine CLI commands into brain.py and learning hook"
```

---

## Task 7: Dashboard API — Playbook Endpoints

**Files:**
- Modify: `~/.claude/skills/eng-buddy/dashboard/server.py`

**Step 1: Read current server.py endpoint structure**

```bash
grep -n "^@app\.\|^async def " ~/.claude/skills/eng-buddy/dashboard/server.py | head -50
```

Identify where to add new endpoints.

**Step 2: Add playbook API endpoints to server.py**

Add these endpoints after the existing `/api/suggestions` block:

```python
# ========== PLAYBOOK ENGINE ==========

import subprocess

PLAYBOOKS_DIR = os.path.expanduser("~/.claude/eng-buddy/playbooks")
BRAIN_PY = os.path.expanduser("~/.claude/eng-buddy/bin/brain.py")


def _run_brain(args: list, stdin_data: str = None) -> dict:
    """Run brain.py with playbook args and return parsed JSON."""
    cmd = ["python3", BRAIN_PY] + args
    result = subprocess.run(cmd, capture_output=True, text=True, input=stdin_data, timeout=30)
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON from brain.py", "raw": result.stdout}


@app.get("/api/playbooks")
async def list_playbooks():
    """List all approved playbooks."""
    return _run_brain(["--playbook-list"])


@app.get("/api/playbooks/drafts")
async def list_draft_playbooks():
    """List all draft playbooks awaiting review."""
    return _run_brain(["--playbook-list-drafts"])


@app.get("/api/playbooks/{playbook_id}")
async def get_playbook(playbook_id: str):
    """Get a specific playbook with full step details."""
    sys.path.insert(0, os.path.expanduser("~/.claude/eng-buddy/bin"))
    from playbook_engine.manager import PlaybookManager
    mgr = PlaybookManager(PLAYBOOKS_DIR)
    pb = mgr.get(playbook_id) or mgr.get_draft(playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return pb.to_dict()


@app.post("/api/playbooks/{playbook_id}/promote")
async def promote_playbook(playbook_id: str):
    """Promote a draft playbook to approved."""
    return _run_brain(["--playbook-promote", playbook_id])


@app.delete("/api/playbooks/drafts/{playbook_id}")
async def delete_draft_playbook(playbook_id: str):
    """Delete a draft playbook."""
    sys.path.insert(0, os.path.expanduser("~/.claude/eng-buddy/bin"))
    from playbook_engine.manager import PlaybookManager
    mgr = PlaybookManager(PLAYBOOKS_DIR)
    if mgr.delete_draft(playbook_id):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Draft not found")


@app.post("/api/playbooks/match")
async def match_playbook(request: Request):
    """Match a ticket against known playbooks."""
    body = await request.json()
    text = body.get("text", "")
    ticket_type = body.get("ticket_type", "")
    source = body.get("source", "freshservice")
    args = ["--playbook-match", text]
    if ticket_type:
        args += ["--playbook-match-type", ticket_type]
    if source:
        args += ["--playbook-match-source", source]
    return _run_brain(args)


@app.post("/api/playbooks/execute")
async def execute_playbook(request: Request):
    """Dispatch a playbook for execution in user's terminal.

    Body: {"playbook_id": "sso-onboarding", "ticket_context": {...}, "approval": "approve all"}
    """
    body = await request.json()
    playbook_id = body.get("playbook_id")
    ticket_context = body.get("ticket_context", {})
    approval = body.get("approval", "approve all")

    sys.path.insert(0, os.path.expanduser("~/.claude/eng-buddy/bin"))
    from playbook_engine.manager import PlaybookManager
    mgr = PlaybookManager(PLAYBOOKS_DIR)
    pb = mgr.get(playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # Parse approval to determine which steps to execute
    excluded_steps = _parse_approval(approval, len(pb.steps))

    # Build the prompt for Claude Code
    step_list = []
    for step in pb.steps:
        if step.id in excluded_steps:
            step_list.append(f"  {step.id}. [SKIP] {step.name}")
        else:
            tool_label = step.action.tool.split("__")[-1] if "__" in step.action.tool else step.action.tool
            step_list.append(f"  {step.id}. {step.name} -> {tool_label}")

    prompt = f"""Execute playbook: {pb.name} (v{pb.version})
Ticket: {ticket_context.get('title', 'N/A')}

Steps:
{chr(10).join(step_list)}

Approval: {approval}

Use the eng-buddy skill. Execute each non-skipped step using the specified tools.
For human-required steps, open the browser to the right page and wait for user signal.
Report progress after each step."""

    # Launch in user's terminal via osascript
    escaped_prompt = prompt.replace('"', '\\"').replace("'", "'\\''")
    launch_cmd = f"""osascript -e 'tell application "Terminal" to do script "claude --print \"{escaped_prompt}\""'"""

    result = subprocess.run(launch_cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return {"status": "dispatched", "playbook_id": playbook_id, "steps": len(pb.steps), "excluded": list(excluded_steps)}
    return {"error": "Failed to launch terminal", "details": result.stderr}


def _parse_approval(approval: str, total_steps: int) -> set:
    """Parse approval string into set of excluded step IDs."""
    excluded = set()
    approval_lower = approval.lower().strip()

    if approval_lower == "approve all":
        return excluded

    # "approve all but #3, #5"
    import re
    but_match = re.search(r"but\s+(.+)", approval_lower)
    if but_match:
        nums = re.findall(r"#?(\d+)", but_match.group(1))
        excluded = {int(n) for n in nums}

    return excluded
```

**Step 3: Test endpoints manually**

```bash
curl http://127.0.0.1:7777/api/playbooks
curl http://127.0.0.1:7777/api/playbooks/drafts
curl -X POST http://127.0.0.1:7777/api/playbooks/match \
  -H "Content-Type: application/json" \
  -d '{"text": "Set up SSO for Linear", "ticket_type": "Service Request"}'
```

Expected: JSON responses with empty lists (no playbooks yet).

**Step 4: Commit**

```bash
git add -f ~/.claude/skills/eng-buddy/dashboard/server.py
git commit -m "Add playbook dashboard API endpoints for list, match, promote, execute"
```

---

## Task 8: Dashboard UI — Playbooks Tab

**Files:**
- Modify: `~/.claude/skills/eng-buddy/dashboard/static/index.html` (or relevant template)

**Step 1: Read current dashboard UI structure**

```bash
ls ~/.claude/skills/eng-buddy/dashboard/static/
grep -n "tab\|nav\|section" ~/.claude/skills/eng-buddy/dashboard/static/index.html | head -30
```

Identify the tab/navigation pattern to follow.

**Step 2: Add Playbooks tab to navigation**

Add a new tab entry following the existing pattern. The exact HTML/JS depends on the current dashboard structure, but the tab should contain three sections:

1. **Pending Review** — Cards for draft playbooks
2. **Ready to Execute** — Cards for matched tickets with approval input
3. **Active Executions** — Progress cards for running playbooks

**Step 3: Implement Pending Review section**

```javascript
// Fetch and render draft playbooks
async function loadDraftPlaybooks() {
    const resp = await fetch('/api/playbooks/drafts');
    const data = await resp.json();
    const container = document.getElementById('playbook-drafts');
    container.innerHTML = '';

    for (const draft of data.drafts || []) {
        const pbResp = await fetch(`/api/playbooks/${draft.id}`);
        const pb = await pbResp.json();
        container.innerHTML += renderPlaybookCard(pb, 'draft');
    }
}

function renderPlaybookCard(pb, state) {
    const stateColors = {draft: 'amber', approved: 'green', suggested: 'blue', executing: 'purple', error: 'red'};
    const color = stateColors[state] || 'gray';
    const steps = pb.steps.map((s, i) =>
        `<div class="step">${s.id}. ${s.name} <span class="tool-badge">${s.action.tool.split('__').pop()}</span>
         ${s.human_required ? '<span class="badge human">human</span>' : ''}
         ${s.auth_required ? '<span class="badge auth">auth</span>' : ''}</div>`
    ).join('');

    return `
    <div class="playbook-card ${color}">
        <div class="card-header">
            <h3>${pb.name}</h3>
            <span class="confidence-badge ${pb.confidence}">${pb.confidence}</span>
            <span class="version">v${pb.version}</span>
        </div>
        <div class="steps-list">${steps}</div>
        <div class="card-actions">
            ${state === 'draft' ? `
                <button onclick="promotePlaybook('${pb.id}')">Approve</button>
                <button onclick="deleteDraft('${pb.id}')">Reject</button>
            ` : ''}
            ${state === 'suggested' ? `
                <input type="text" placeholder="approve all" id="approval-${pb.id}" value="approve all">
                <button onclick="executePlaybook('${pb.id}')">Execute</button>
            ` : ''}
        </div>
    </div>`;
}
```

**Step 4: Implement approval input and execution dispatch**

```javascript
async function executePlaybook(playbookId) {
    const approval = document.getElementById(`approval-${playbookId}`).value;
    const ticketContext = window._currentTicketContext || {};
    const resp = await fetch('/api/playbooks/execute', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({playbook_id: playbookId, ticket_context: ticketContext, approval: approval}),
    });
    const data = await resp.json();
    if (data.status === 'dispatched') {
        showNotification(`Playbook dispatched to terminal (${data.steps} steps)`);
        loadActiveExecutions();
    } else {
        showNotification(`Error: ${data.error}`, 'error');
    }
}

async function promotePlaybook(playbookId) {
    await fetch(`/api/playbooks/${playbookId}/promote`, {method: 'POST'});
    loadDraftPlaybooks();
    loadApprovedPlaybooks();
}

async function deleteDraft(playbookId) {
    await fetch(`/api/playbooks/drafts/${playbookId}`, {method: 'DELETE'});
    loadDraftPlaybooks();
}
```

**Step 5: Implement approved playbooks list**

```javascript
async function loadApprovedPlaybooks() {
    const resp = await fetch('/api/playbooks');
    const data = await resp.json();
    const container = document.getElementById('playbook-approved');
    container.innerHTML = '';
    for (const pb of data.playbooks || []) {
        container.innerHTML += `
        <div class="playbook-row">
            <span class="pb-name">${pb.name}</span>
            <span class="confidence-badge ${pb.confidence}">${pb.confidence}</span>
            <span class="executions">${pb.executions} runs</span>
            <span class="version">v${pb.version}</span>
        </div>`;
    }
}
```

**Step 6: Add CSS for playbook cards**

Follow the existing dashboard CSS patterns but add:

```css
.playbook-card { border-left: 4px solid; padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }
.playbook-card.amber { border-color: #f59e0b; background: #fffbeb; }
.playbook-card.green { border-color: #10b981; background: #ecfdf5; }
.playbook-card.blue { border-color: #3b82f6; background: #eff6ff; }
.playbook-card.purple { border-color: #8b5cf6; background: #f5f3ff; }
.playbook-card.red { border-color: #ef4444; background: #fef2f2; }
.confidence-badge { padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
.confidence-badge.high { background: #10b981; color: white; }
.confidence-badge.medium { background: #f59e0b; color: white; }
.confidence-badge.low { background: #6b7280; color: white; }
.tool-badge { background: #e5e7eb; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; }
.badge.human { background: #fbbf24; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; }
.badge.auth { background: #f87171; color: white; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; }
```

**Step 7: Commit**

```bash
git add -f ~/.claude/skills/eng-buddy/dashboard/static/
git commit -m "Add playbook tab to dashboard with draft review and execution dispatch"
```

---

## Task 9: SKILL.md — Playbook Instructions for eng-buddy

**Files:**
- Modify: `~/.claude/skills/eng-buddy/SKILL.md`

**Step 1: Read the relevant section of SKILL.md**

```bash
grep -n "memory\|learning\|pattern\|runbook\|playbook" ~/.claude/skills/eng-buddy/SKILL.md
```

Identify where to add playbook documentation.

**Step 2: Add playbook engine section to SKILL.md**

Add after the memory system section:

```markdown
### Playbook Engine

eng-buddy can learn, store, and execute repeatable workflows called **playbooks**.

#### How Playbooks Work

**Observation**: As you work tickets, eng-buddy captures a full trace — tool calls, your instructions, corrections, manual actions, decisions, and questions. This happens continuously via hooks.

**Extraction**: When a ticket is completed or a pattern is detected, eng-buddy drafts a playbook with action-bound steps. Each step specifies which tool to use, what parameters to pass, and whether human involvement is needed.

**Approval**: Draft playbooks appear on the dashboard (Playbooks tab) for your review. You can edit steps, approve, or reject.

**Execution**: When a new ticket matches an approved playbook, the dashboard shows a "Ready to Execute" card with the pre-filled step list. Type your approval command and eng-buddy dispatches a Claude Code session in your terminal to execute it.

#### Approval Commands

- `approve all` — execute every step
- `approve all but #3, #5` — skip specific steps
- `approve all but ask me before sending slack messages` — conditional pauses
- `approve #1-#4, hold on #5 until I finish the manual config` — partial execution

#### Creating Playbooks

Three paths:

1. **Watch and Learn**: Work a ticket normally. eng-buddy drafts a playbook from your session.
2. **Describe**: Say "Create a playbook for [task]. Steps: [1, 2, 3]." eng-buddy expands with tool bindings.
3. **Pattern Detection**: eng-buddy analyzes traces and proposes playbooks for repeated workflows.

#### Managing Playbooks

- Dashboard Playbooks tab: review drafts, monitor executions, manage approved playbooks
- CLI: `python3 ~/.claude/eng-buddy/bin/brain.py --playbook-list`
- Session: "Run [playbook name] for [ticket]" to invoke manually

#### Setting Active Trace

When working a specific ticket, write the ticket ID to the active trace file:

```bash
echo "ITWORK2-1234" > ~/.claude/eng-buddy/.active-trace-id
```

eng-buddy hooks will automatically record tool calls against this trace. Clear it when done:

```bash
rm ~/.claude/eng-buddy/.active-trace-id
```

#### Tool Registry

Playbook steps bind to tools via the registry at `~/.claude/eng-buddy/playbooks/tool-registry/`. Each tool has:

- Type (MCP, browser, script, AI)
- Auth requirements (persistent, per-domain, human handoff)
- Per-action defaults (assignee, board, sprint, etc.)

Defaults are modular — one `.defaults.yml` file per tool, auto-discovered.
```

**Step 3: Commit**

```bash
git add -f ~/.claude/skills/eng-buddy/SKILL.md
git commit -m "Document playbook engine in SKILL.md"
```

---

## Task 10: Integration Test — End-to-End Playbook Flow

**Files:**
- Create: `~/.claude/eng-buddy/bin/playbook_engine/test_integration.py`

**Step 1: Write end-to-end integration test**

Write `~/.claude/eng-buddy/bin/playbook_engine/test_integration.py`:

```python
"""End-to-end test: trace capture → extraction → storage → matching → execution dispatch."""

import pytest
import yaml
import tempfile
import json
from tracer import WorkflowTracer, TraceEvent
from registry import ToolRegistry
from extractor import PlaybookExtractor
from manager import PlaybookManager
from models import Playbook

@pytest.fixture
def env(tmp_path):
    """Set up a complete playbook environment."""
    playbooks_dir = tmp_path / "playbooks"
    playbooks_dir.mkdir()
    (playbooks_dir / "drafts").mkdir()
    (playbooks_dir / "archive").mkdir()

    reg_dir = playbooks_dir / "tool-registry"
    reg_dir.mkdir()
    (reg_dir / "_registry.yml").write_text(yaml.dump({
        "tools": {
            "jira": {"type": "mcp", "prefix": "mcp__mcp-atlassian__jira_", "capabilities": ["create_issue", "transition_issue"], "auth": "persistent", "domains": ["ticket_management"]},
            "slack": {"type": "mcp", "prefix": "mcp__slack__", "capabilities": ["post_message"], "auth": "persistent", "domains": ["communication"]},
            "freshservice": {"type": "mcp", "prefix": "mcp__freshservice-mcp__", "capabilities": ["update_ticket"], "auth": "persistent", "domains": ["service_desk"]},
            "playwright": {"type": "browser", "prefix": "mcp__playwright__", "capabilities": ["navigate"], "auth": "per_domain", "domains": ["web_admin"]},
        }
    }))
    (reg_dir / "jira.defaults.yml").write_text(yaml.dump({
        "create_issue": {"assignee": "kioja@test.com", "board_id": 70},
    }))

    traces_dir = tmp_path / "traces"
    return {
        "playbooks_dir": str(playbooks_dir),
        "traces_dir": str(traces_dir),
        "registry_dir": str(reg_dir),
    }

def test_full_flow(env):
    """Simulate: work SSO ticket → extract playbook → match new ticket → dispatch."""

    # 1. Capture a workflow trace
    tracer = WorkflowTracer(traces_dir=env["traces_dir"])
    tracer.start_trace("ITWORK2-100")

    tracer.add_event(TraceEvent(type="user_instruction", content="Do SSO onboarding for Linear"))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__mcp-atlassian__jira_create_issue",
        params={"project": "ITWORK2", "summary": "[SSO] Linear", "assignee": "kioja@test.com", "board_id": 70}))
    tracer.add_event(TraceEvent(type="user_manual_action", content="Configured SAML in Okta",
        inferred_step="Configure SAML in IdP", action_binding="playwright", auth_note="Okta admin"))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__slack__post_message",
        params={"channel": "C123", "text": "SSO ready for Linear"}))
    tracer.add_event(TraceEvent(type="tool_call", tool="mcp__freshservice-mcp__update_ticket",
        params={"ticket_id": 456, "status": 5}))
    tracer.flush("ITWORK2-100")

    # 2. Extract a playbook
    registry = ToolRegistry(env["registry_dir"])
    extractor = PlaybookExtractor(registry=registry)
    trace = tracer.get_trace("ITWORK2-100")
    pb = extractor.extract_from_trace(trace, name="SSO Onboarding")

    assert pb.id == "sso-onboarding"
    assert pb.confidence == "low"
    assert len(pb.steps) == 4
    assert pb.steps[1].human_required is True  # manual SAML config

    # 3. Save as draft, review, promote
    manager = PlaybookManager(env["playbooks_dir"])
    manager.save_draft(pb)
    assert len(manager.list_drafts()) == 1

    manager.promote_draft("sso-onboarding")
    assert len(manager.list_drafts()) == 0
    assert len(manager.list_playbooks()) == 1

    # 4. Match against a new ticket
    matches = manager.match_ticket(
        ticket_type="Service Request",
        text="Please set up SSO for Notion",
        source="freshservice",
    )
    assert len(matches) == 1
    assert matches[0].id == "sso-onboarding"

    # 5. Record execution and check confidence progression
    promoted = manager.get("sso-onboarding")
    promoted.record_execution(success=True)
    assert promoted.confidence == "medium"
    assert promoted.executions == 1
    manager.save(promoted)

    # Verify persistence
    reloaded = manager.get("sso-onboarding")
    assert reloaded.confidence == "medium"
    assert reloaded.executions == 1

def test_no_match_returns_empty(env):
    manager = PlaybookManager(env["playbooks_dir"])
    matches = manager.match_ticket(text="New laptop request", source="freshservice")
    assert matches == []

def test_dictated_playbook_flow(env):
    """Path 2: User describes steps, engine creates playbook."""
    registry = ToolRegistry(env["registry_dir"])
    extractor = PlaybookExtractor(registry=registry)

    pb = extractor.extract_from_description(
        name="Employee Offboarding",
        steps_text=[
            "Disable user account in Okta",
            "Remove from all Slack channels",
            "Archive Jira tickets",
            "Send confirmation email to manager",
        ],
    )

    assert pb.id == "employee-offboarding"
    assert pb.confidence == "medium"  # dictated starts at medium
    assert len(pb.steps) == 4
    assert pb.created_from == "dictated"

    manager = PlaybookManager(env["playbooks_dir"])
    manager.save(pb)
    loaded = manager.get("employee-offboarding")
    assert loaded is not None
```

**Step 2: Run integration tests**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest test_integration.py -v
```
Expected: All 3 tests PASS

**Step 3: Run full test suite**

```bash
cd ~/.claude/eng-buddy/bin/playbook_engine && python3 -m pytest -v
```
Expected: All tests PASS across all test files

**Step 4: Commit**

```bash
git add -f ~/.claude/eng-buddy/bin/playbook_engine/test_integration.py
git commit -m "Add end-to-end integration tests for playbook engine"
```

---

## Summary

| Task | Component | Files | Tests |
|------|-----------|-------|-------|
| 1 | Directory structure & tool registry YAML | 11 new | — |
| 2 | Data model & registry loader (Python) | 4 new | 8 tests |
| 3 | Workflow tracer | 2 new | 6 tests |
| 4 | Playbook extraction pipeline | 2 new | 3 tests |
| 5 | Playbook manager (storage/matching/versioning) | 2 new | 6 tests |
| 6 | Brain.py integration (CLI + hook) | 2 modified | manual |
| 7 | Dashboard API endpoints | 1 modified | manual |
| 8 | Dashboard UI (Playbooks tab) | 1 modified | — |
| 9 | SKILL.md documentation | 1 modified | — |
| 10 | Integration tests | 1 new | 3 tests |

**Total: ~26 files, ~26 automated tests, 10 commits**
