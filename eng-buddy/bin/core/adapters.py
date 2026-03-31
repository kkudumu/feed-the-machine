"""Adapter abstraction layer — portable integration architecture.

Suggestion 7 from the brain dump:
"Separate core engine from workplace adapters. Each adapter exposes
standard capability map: read, summarize, draft, comment, create ticket,
change status, fetch context, search docs, run automation, notify human.
Separate company policy from personal workflow. Separate personal style
from product behavior."
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Capability(str, Enum):
    """Standard capabilities that any adapter can expose."""
    READ = "read"
    SUMMARIZE = "summarize"
    DRAFT = "draft"
    COMMENT = "comment"
    CREATE_TICKET = "create_ticket"
    UPDATE_TICKET = "update_ticket"
    CHANGE_STATUS = "change_status"
    FETCH_CONTEXT = "fetch_context"
    SEARCH_DOCS = "search_docs"
    RUN_AUTOMATION = "run_automation"
    NOTIFY_HUMAN = "notify_human"
    SEND_MESSAGE = "send_message"
    CREATE_EVENT = "create_event"
    MANAGE_ACCESS = "manage_access"


@dataclass
class AdapterCapability:
    """A single capability with its implementation details."""
    capability: str
    tool: str = ""          # MCP tool name that implements this
    description: str = ""
    requires_auth: bool = True
    auth_method: str = ""   # "api_key", "oauth2", "session", "token"
    available: bool = True

    def to_dict(self) -> dict:
        return {
            "capability": self.capability,
            "tool": self.tool,
            "description": self.description,
            "requires_auth": self.requires_auth,
            "auth_method": self.auth_method,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AdapterCapability":
        return cls(
            capability=d["capability"],
            tool=d.get("tool", ""),
            description=d.get("description", ""),
            requires_auth=d.get("requires_auth", True),
            auth_method=d.get("auth_method", ""),
            available=d.get("available", True),
        )


@dataclass
class AdapterConfig:
    """Configuration for a workplace adapter."""
    id: str
    name: str
    system: str          # "jira", "freshservice", "slack", "gmail", etc.
    mcp_prefix: str = ""  # "mcp__mcp-atlassian__", "mcp__freshservice-mcp__"
    capabilities: List[AdapterCapability] = field(default_factory=list)
    config: dict = field(default_factory=dict)  # adapter-specific config
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "system": self.system,
            "mcp_prefix": self.mcp_prefix,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "config": self.config,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AdapterConfig":
        caps = [AdapterCapability.from_dict(c) for c in d.get("capabilities", [])]
        return cls(
            id=d["id"],
            name=d["name"],
            system=d["system"],
            mcp_prefix=d.get("mcp_prefix", ""),
            capabilities=caps,
            config=d.get("config", {}),
            enabled=d.get("enabled", True),
        )

    def has_capability(self, cap: str) -> bool:
        return any(c.capability == cap and c.available for c in self.capabilities)

    def get_tool_for(self, cap: str) -> Optional[str]:
        for c in self.capabilities:
            if c.capability == cap and c.available:
                return c.tool
        return None


class BaseAdapter(ABC):
    """Base class for all workplace adapters."""

    def __init__(self, config: AdapterConfig):
        self.config = config

    @abstractmethod
    def get_capability_map(self) -> Dict[str, AdapterCapability]:
        """Return the capability map for this adapter."""
        ...

    @abstractmethod
    def verify_connection(self) -> bool:
        """Test that the adapter can connect to its system."""
        ...

    def supports(self, capability: str) -> bool:
        return self.config.has_capability(capability)


# ---------------------------------------------------------------------------
# Built-in adapter definitions
# ---------------------------------------------------------------------------

def jira_adapter_config() -> AdapterConfig:
    """Pre-configured adapter for Jira via mcp-atlassian."""
    return AdapterConfig(
        id="jira",
        name="Jira (Atlassian)",
        system="jira",
        mcp_prefix="mcp__mcp-atlassian__",
        capabilities=[
            AdapterCapability(Capability.READ.value, "mcp__mcp-atlassian__jira_get_issue", "Read a Jira issue"),
            AdapterCapability(Capability.CREATE_TICKET.value, "mcp__mcp-atlassian__jira_create_issue", "Create a Jira issue"),
            AdapterCapability(Capability.UPDATE_TICKET.value, "mcp__mcp-atlassian__jira_update_issue", "Update a Jira issue"),
            AdapterCapability(Capability.CHANGE_STATUS.value, "mcp__mcp-atlassian__jira_transition_issue", "Transition a Jira issue"),
            AdapterCapability(Capability.COMMENT.value, "mcp__mcp-atlassian__jira_add_comment", "Add a comment to a Jira issue"),
            AdapterCapability(Capability.SEARCH_DOCS.value, "mcp__mcp-atlassian__jira_search", "Search Jira issues"),
            AdapterCapability(Capability.FETCH_CONTEXT.value, "mcp__mcp-atlassian__jira_get_issue", "Fetch issue context"),
        ],
    )


def freshservice_adapter_config() -> AdapterConfig:
    """Pre-configured adapter for Freshservice."""
    return AdapterConfig(
        id="freshservice",
        name="Freshservice",
        system="freshservice",
        mcp_prefix="mcp__freshservice-mcp__",
        capabilities=[
            AdapterCapability(Capability.READ.value, "mcp__freshservice-mcp__get_ticket_by_id", "Read a Freshservice ticket"),
            AdapterCapability(Capability.CREATE_TICKET.value, "mcp__freshservice-mcp__create_ticket", "Create a Freshservice ticket"),
            AdapterCapability(Capability.UPDATE_TICKET.value, "mcp__freshservice-mcp__update_ticket", "Update a Freshservice ticket"),
            AdapterCapability(Capability.COMMENT.value, "mcp__freshservice-mcp__create_ticket_note", "Add note to a ticket"),
            AdapterCapability(Capability.NOTIFY_HUMAN.value, "mcp__freshservice-mcp__send_ticket_reply", "Reply to a ticket requester"),
            AdapterCapability(Capability.SEARCH_DOCS.value, "mcp__freshservice-mcp__filter_tickets", "Search Freshservice tickets"),
            AdapterCapability(Capability.FETCH_CONTEXT.value, "mcp__freshservice-mcp__get_ticket_by_id", "Fetch ticket context"),
        ],
    )


def slack_adapter_config() -> AdapterConfig:
    """Pre-configured adapter for Slack."""
    return AdapterConfig(
        id="slack",
        name="Slack",
        system="slack",
        mcp_prefix="mcp__slack__",
        capabilities=[
            AdapterCapability(Capability.READ.value, "mcp__slack__slack_get_channel_history", "Read channel messages"),
            AdapterCapability(Capability.SEND_MESSAGE.value, "mcp__slack__slack_post_message", "Post a Slack message"),
            AdapterCapability(Capability.COMMENT.value, "mcp__slack__slack_reply_to_thread", "Reply to a Slack thread"),
            AdapterCapability(Capability.NOTIFY_HUMAN.value, "mcp__slack__slack_post_message", "Notify via Slack DM"),
            AdapterCapability(Capability.FETCH_CONTEXT.value, "mcp__slack__slack_get_thread_replies", "Fetch thread context"),
        ],
    )


def gmail_adapter_config() -> AdapterConfig:
    """Pre-configured adapter for Gmail."""
    return AdapterConfig(
        id="gmail",
        name="Gmail",
        system="gmail",
        mcp_prefix="mcp__gmail__",
        capabilities=[
            AdapterCapability(Capability.READ.value, "mcp__gmail__read_email", "Read an email"),
            AdapterCapability(Capability.DRAFT.value, "mcp__gmail__draft_email", "Draft an email"),
            AdapterCapability(Capability.SEND_MESSAGE.value, "mcp__gmail__send_email", "Send an email"),
            AdapterCapability(Capability.SEARCH_DOCS.value, "mcp__gmail__search_emails", "Search emails"),
            AdapterCapability(Capability.FETCH_CONTEXT.value, "mcp__gmail__read_email", "Fetch email context"),
        ],
    )


def calendar_adapter_config() -> AdapterConfig:
    """Pre-configured adapter for Google Calendar."""
    return AdapterConfig(
        id="calendar",
        name="Google Calendar",
        system="google-calendar",
        mcp_prefix="mcp__google-calendar__",
        capabilities=[
            AdapterCapability(Capability.READ.value, "mcp__google-calendar__get-event", "Read a calendar event"),
            AdapterCapability(Capability.CREATE_EVENT.value, "mcp__google-calendar__create-event", "Create a calendar event"),
            AdapterCapability(Capability.SEARCH_DOCS.value, "mcp__google-calendar__search-events", "Search calendar events"),
            AdapterCapability(Capability.FETCH_CONTEXT.value, "mcp__google-calendar__list-events", "List upcoming events"),
        ],
    )


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------

class AdapterRegistry:
    """Registry of all available adapters.

    Provides a single point to discover which capabilities are available
    across all connected systems.
    """

    def __init__(self):
        self.adapters: Dict[str, AdapterConfig] = {}

    def register(self, config: AdapterConfig):
        self.adapters[config.id] = config

    def register_defaults(self):
        """Register all built-in adapters."""
        for factory in (
            jira_adapter_config,
            freshservice_adapter_config,
            slack_adapter_config,
            gmail_adapter_config,
            calendar_adapter_config,
        ):
            self.register(factory())

    def get(self, adapter_id: str) -> Optional[AdapterConfig]:
        return self.adapters.get(adapter_id)

    def find_by_capability(self, capability: str) -> List[AdapterConfig]:
        """Find all adapters that support a given capability."""
        return [a for a in self.adapters.values() if a.has_capability(capability) and a.enabled]

    def get_tool_for(self, capability: str, preferred_system: str = "") -> Optional[str]:
        """Find the MCP tool that implements a capability.

        If preferred_system is specified, prefer that adapter.
        """
        if preferred_system:
            adapter = self.adapters.get(preferred_system)
            if adapter and adapter.has_capability(capability):
                return adapter.get_tool_for(capability)

        for adapter in self.adapters.values():
            if adapter.enabled and adapter.has_capability(capability):
                return adapter.get_tool_for(capability)
        return None

    def get_full_capability_map(self) -> Dict[str, List[dict]]:
        """Return a map of capability -> list of adapters that support it."""
        cap_map: Dict[str, List[dict]] = {}
        for adapter in self.adapters.values():
            if not adapter.enabled:
                continue
            for cap in adapter.capabilities:
                if not cap.available:
                    continue
                cap_map.setdefault(cap.capability, []).append({
                    "adapter": adapter.id,
                    "tool": cap.tool,
                    "auth_method": cap.auth_method,
                })
        return cap_map

    def to_dict(self) -> dict:
        return {
            "adapters": {k: v.to_dict() for k, v in self.adapters.items()},
        }


# ---------------------------------------------------------------------------
# Policy & Preference separation
# ---------------------------------------------------------------------------

@dataclass
class CompanyPolicy:
    """Company-level policies — separate from personal workflow."""
    id: str
    name: str
    rules: List[dict] = field(default_factory=list)
    applies_to: List[str] = field(default_factory=list)  # adapter IDs

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "rules": self.rules,
            "applies_to": self.applies_to,
        }


@dataclass
class PersonalWorkflow:
    """Personal workflow preferences — separate from company policy."""
    id: str
    name: str
    preferences: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "preferences": self.preferences,
        }


@dataclass
class UserProfile:
    """User identity and style — separate from product behavior."""
    user_id: str
    name: str = ""
    email: str = ""
    role: str = ""
    team: str = ""
    company: str = ""
    response_tone: str = "friendly but concise"
    timezone: str = "America/New_York"
    deep_work_hours: str = ""
    communication_preferences: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "team": self.team,
            "company": self.company,
            "response_tone": self.response_tone,
            "timezone": self.timezone,
            "deep_work_hours": self.deep_work_hours,
            "communication_preferences": self.communication_preferences,
        }

    @classmethod
    def from_context_json(cls, ctx: dict) -> "UserProfile":
        """Build a UserProfile from the existing context.json format."""
        prefs = ctx.get("preferences", {})
        return cls(
            user_id=ctx.get("email", ""),
            name="",
            email=ctx.get("email", ""),
            role=ctx.get("role", ""),
            team=ctx.get("team", ""),
            company=ctx.get("company", ""),
            response_tone=prefs.get("response_tone", "friendly but concise"),
            deep_work_hours=prefs.get("deep_work_hours", ""),
        )
