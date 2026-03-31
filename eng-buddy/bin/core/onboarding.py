"""Self-integrating onboarding — guided system discovery and setup.

Suggestion 10 from the brain dump:
"- User says what systems they use
 - System discovers available integration paths (MCP servers, APIs, browser automation)
 - Asks for credentials with explanation of why each permission is needed
 - Installs/configures adapters
 - Verifies capabilities with test calls
 - Caches docs and schemas
 - Generates Integration Knowledge Packs per system
 - Seeds starter playbooks
 - Trust-tiered autonomy (Tier 0: docs only -> Tier 4: destructive with approval)"
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class OnboardingTier(str, Enum):
    """Trust tiers for onboarding — progressive autonomy."""
    TIER_0 = "tier_0"  # Docs only: read documentation, no actions
    TIER_1 = "tier_1"  # Read only: fetch data from systems, no mutations
    TIER_2 = "tier_2"  # Draft mode: create drafts, suggest actions, human confirms
    TIER_3 = "tier_3"  # Auto-safe: auto-execute non-destructive, human for destructive
    TIER_4 = "tier_4"  # Full auto: destructive with approval, everything else auto


TIER_DESCRIPTIONS = {
    OnboardingTier.TIER_0.value: "Documentation only — read docs and schemas, no system access",
    OnboardingTier.TIER_1.value: "Read only — fetch data from connected systems, no mutations",
    OnboardingTier.TIER_2.value: "Draft mode — create drafts and suggestions, human confirms everything",
    OnboardingTier.TIER_3.value: "Auto-safe — auto-execute non-destructive actions, human approval for destructive",
    OnboardingTier.TIER_4.value: "Full autonomy — auto-execute with approval only for destructive/external actions",
}


@dataclass
class IntegrationPath:
    """A discovered way to integrate with a system."""
    system: str          # "jira", "freshservice", etc.
    method: str          # "mcp_server", "api", "browser_automation"
    mcp_server: str = ""  # MCP server name if applicable
    description: str = ""
    requires_credentials: List[str] = field(default_factory=list)
    credential_explanations: dict = field(default_factory=dict)  # cred -> why needed
    available: bool = False
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "system": self.system,
            "method": self.method,
            "mcp_server": self.mcp_server,
            "description": self.description,
            "requires_credentials": self.requires_credentials,
            "credential_explanations": self.credential_explanations,
            "available": self.available,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IntegrationPath":
        return cls(
            system=d["system"],
            method=d["method"],
            mcp_server=d.get("mcp_server", ""),
            description=d.get("description", ""),
            requires_credentials=d.get("requires_credentials", []),
            credential_explanations=d.get("credential_explanations", {}),
            available=d.get("available", False),
            verified=d.get("verified", False),
        )


@dataclass
class IntegrationKnowledgePack:
    """Cached knowledge about a specific system integration."""
    system: str
    adapter_id: str
    capabilities: List[str] = field(default_factory=list)
    schema_summary: dict = field(default_factory=dict)
    common_operations: List[dict] = field(default_factory=list)
    known_limitations: List[str] = field(default_factory=list)
    starter_playbooks: List[str] = field(default_factory=list)  # playbook IDs
    docs_cached_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "system": self.system,
            "adapter_id": self.adapter_id,
            "capabilities": self.capabilities,
            "schema_summary": self.schema_summary,
            "common_operations": self.common_operations,
            "known_limitations": self.known_limitations,
            "starter_playbooks": self.starter_playbooks,
            "docs_cached_at": self.docs_cached_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IntegrationKnowledgePack":
        return cls(
            system=d["system"],
            adapter_id=d["adapter_id"],
            capabilities=d.get("capabilities", []),
            schema_summary=d.get("schema_summary", {}),
            common_operations=d.get("common_operations", []),
            known_limitations=d.get("known_limitations", []),
            starter_playbooks=d.get("starter_playbooks", []),
            docs_cached_at=d.get("docs_cached_at"),
            created_at=d.get("created_at", ""),
        )


# ---------------------------------------------------------------------------
# Known integration paths
# ---------------------------------------------------------------------------

KNOWN_INTEGRATIONS: List[IntegrationPath] = [
    IntegrationPath(
        system="jira",
        method="mcp_server",
        mcp_server="mcp-atlassian",
        description="Jira issue tracking via MCP Atlassian server",
        requires_credentials=["JIRA_URL", "JIRA_USERNAME", "JIRA_API_TOKEN"],
        credential_explanations={
            "JIRA_URL": "Your Jira instance URL (e.g., https://company.atlassian.net)",
            "JIRA_USERNAME": "Your Jira email address for API authentication",
            "JIRA_API_TOKEN": "API token from https://id.atlassian.com/manage-profile/security/api-tokens — needed for reading/creating issues",
        },
    ),
    IntegrationPath(
        system="freshservice",
        method="mcp_server",
        mcp_server="freshservice-mcp",
        description="Freshservice ITSM via MCP server",
        requires_credentials=["FRESHSERVICE_DOMAIN", "FRESHSERVICE_API_KEY"],
        credential_explanations={
            "FRESHSERVICE_DOMAIN": "Your Freshservice domain (e.g., company.freshservice.com)",
            "FRESHSERVICE_API_KEY": "API key from Freshservice Profile Settings — needed for ticket operations",
        },
    ),
    IntegrationPath(
        system="slack",
        method="mcp_server",
        mcp_server="slack",
        description="Slack messaging via MCP server",
        requires_credentials=["SLACK_BOT_TOKEN"],
        credential_explanations={
            "SLACK_BOT_TOKEN": "Slack Bot User OAuth Token (xoxb-...) from your Slack App — needed for reading/posting messages",
        },
    ),
    IntegrationPath(
        system="gmail",
        method="mcp_server",
        mcp_server="gmail",
        description="Gmail email via MCP server",
        requires_credentials=["GMAIL_OAUTH_CREDENTIALS"],
        credential_explanations={
            "GMAIL_OAUTH_CREDENTIALS": "OAuth2 credentials for Gmail API — needed for reading/sending emails",
        },
    ),
    IntegrationPath(
        system="google-calendar",
        method="mcp_server",
        mcp_server="google-calendar",
        description="Google Calendar via MCP server",
        requires_credentials=["GOOGLE_CALENDAR_OAUTH_CREDENTIALS"],
        credential_explanations={
            "GOOGLE_CALENDAR_OAUTH_CREDENTIALS": "OAuth2 credentials for Calendar API — needed for reading/creating events",
        },
    ),
    IntegrationPath(
        system="confluence",
        method="mcp_server",
        mcp_server="mcp-atlassian",
        description="Confluence wiki via MCP Atlassian server",
        requires_credentials=["CONFLUENCE_URL", "CONFLUENCE_USERNAME", "CONFLUENCE_API_TOKEN"],
        credential_explanations={
            "CONFLUENCE_URL": "Your Confluence instance URL",
            "CONFLUENCE_USERNAME": "Your Confluence email address",
            "CONFLUENCE_API_TOKEN": "Same API token as Jira (shared Atlassian auth)",
        },
    ),
    IntegrationPath(
        system="browser",
        method="browser_automation",
        mcp_server="playwright",
        description="Browser automation via Playwright MCP — for systems without APIs",
        requires_credentials=[],
        credential_explanations={},
    ),
]


# ---------------------------------------------------------------------------
# Onboarding Engine
# ---------------------------------------------------------------------------

@dataclass
class OnboardingState:
    """Tracks the state of the onboarding process."""
    current_tier: str = OnboardingTier.TIER_0.value
    systems_declared: List[str] = field(default_factory=list)
    integrations_discovered: List[IntegrationPath] = field(default_factory=list)
    integrations_configured: List[str] = field(default_factory=list)
    integrations_verified: List[str] = field(default_factory=list)
    knowledge_packs: Dict[str, IntegrationKnowledgePack] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "current_tier": self.current_tier,
            "systems_declared": self.systems_declared,
            "integrations_discovered": [i.to_dict() for i in self.integrations_discovered],
            "integrations_configured": self.integrations_configured,
            "integrations_verified": self.integrations_verified,
            "knowledge_packs": {k: v.to_dict() for k, v in self.knowledge_packs.items()},
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class OnboardingEngine:
    """Guides a new user through system setup and integration.

    Flow:
    1. User declares what systems they use
    2. Engine discovers available integration paths
    3. Engine explains what credentials are needed and why
    4. User provides credentials
    5. Engine verifies connections with test calls
    6. Engine generates knowledge packs per system
    7. Engine seeds starter playbooks
    8. User selects trust tier
    """

    def __init__(self):
        self.state = OnboardingState()

    def declare_systems(self, systems: List[str]) -> dict:
        """Step 1: User declares what systems they use.

        Args:
            systems: List of system names (e.g., ["jira", "freshservice", "slack"])

        Returns:
            Dict with discovered integration paths and credential requirements.
        """
        self.state.systems_declared = systems
        discovered = []

        for system in systems:
            system_lower = system.lower()
            matching = [
                IntegrationPath(
                    system=ip.system,
                    method=ip.method,
                    mcp_server=ip.mcp_server,
                    description=ip.description,
                    requires_credentials=list(ip.requires_credentials),
                    credential_explanations=dict(ip.credential_explanations),
                )
                for ip in KNOWN_INTEGRATIONS
                if ip.system == system_lower
            ]
            if matching:
                discovered.extend(matching)
            else:
                # Unknown system — suggest browser automation
                discovered.append(IntegrationPath(
                    system=system_lower,
                    method="browser_automation",
                    mcp_server="playwright",
                    description=f"Browser automation for {system} (no native integration found)",
                ))

        self.state.integrations_discovered = discovered

        return {
            "systems_declared": systems,
            "integrations_found": [d.to_dict() for d in discovered],
            "credentials_needed": {
                d.system: {
                    "credentials": d.requires_credentials,
                    "explanations": d.credential_explanations,
                }
                for d in discovered
                if d.requires_credentials
            },
            "next_step": "Provide credentials for each system to continue setup.",
        }

    def verify_integration(self, system: str) -> dict:
        """Step 5: Verify a system integration works.

        In a real implementation, this would make test API calls.
        For now, it returns the verification structure.
        """
        # Find the integration path
        path = next(
            (ip for ip in self.state.integrations_discovered if ip.system == system),
            None,
        )
        if not path:
            return {"verified": False, "error": f"No integration found for {system}"}

        # In production, this would:
        # - Make a test read call to the system
        # - Verify the response is valid
        # - Cache the available capabilities
        path.verified = True
        if system not in self.state.integrations_verified:
            self.state.integrations_verified.append(system)

        return {
            "system": system,
            "verified": True,
            "method": path.method,
            "next_step": "Generate knowledge pack for this system.",
        }

    def generate_knowledge_pack(self, system: str) -> IntegrationKnowledgePack:
        """Step 6: Generate an Integration Knowledge Pack for a system."""
        from core.adapters import AdapterRegistry

        registry = AdapterRegistry()
        registry.register_defaults()
        adapter = registry.get(system)

        capabilities = []
        if adapter:
            capabilities = [c.capability for c in adapter.capabilities if c.available]

        pack = IntegrationKnowledgePack(
            system=system,
            adapter_id=system,
            capabilities=capabilities,
            docs_cached_at=datetime.now().isoformat(),
        )
        self.state.knowledge_packs[system] = pack
        return pack

    def set_trust_tier(self, tier: str) -> dict:
        """Step 8: User selects their trust tier."""
        if tier not in [t.value for t in OnboardingTier]:
            return {"error": f"Invalid tier: {tier}. Valid: {[t.value for t in OnboardingTier]}"}

        self.state.current_tier = tier
        return {
            "tier": tier,
            "description": TIER_DESCRIPTIONS.get(tier, ""),
            "state": self.state.to_dict(),
        }

    def get_status(self) -> dict:
        """Get the current onboarding status."""
        total = len(self.state.systems_declared)
        configured = len(self.state.integrations_configured)
        verified = len(self.state.integrations_verified)

        return {
            "current_tier": self.state.current_tier,
            "tier_description": TIER_DESCRIPTIONS.get(self.state.current_tier, ""),
            "systems_declared": total,
            "systems_configured": configured,
            "systems_verified": verified,
            "progress_pct": int((verified / total * 100) if total > 0 else 0),
            "knowledge_packs_generated": len(self.state.knowledge_packs),
            "state": self.state.to_dict(),
        }
