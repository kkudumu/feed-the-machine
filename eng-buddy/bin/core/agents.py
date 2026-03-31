"""Multi-agent pipeline — specialized agents for each phase of work.

Suggestion 6 from the brain dump:
"1. Intake/Triage agent - Turns raw events into normalized action objects.
 2. Planner agent - Builds execution plan from action + memory + playbooks.
 3. Policy/Risk agent - Checks permissions, reversibility, approval requirements.
 4. Executor agent - Runs deterministic steps or launches guided Claude execution.
 5. Reflection agent - Compares expected vs actual outcome, extracts lessons.
 6. Knowledge curator agent - Updates runbooks, patterns, and docs from successful runs."
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentRole(str, Enum):
    INTAKE = "intake"
    PLANNER = "planner"
    POLICY = "policy"
    EXECUTOR = "executor"
    REFLECTION = "reflection"
    CURATOR = "curator"


@dataclass
class AgentMessage:
    """A message passed between agents in the pipeline."""
    sender: str
    recipient: str
    payload: dict
    message_type: str = "handoff"  # "handoff", "query", "response", "error"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentResult:
    """The result of an agent processing step."""
    agent: str
    success: bool
    output: dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    next_agent: Optional[str] = None  # which agent should run next
    needs_human: bool = False
    human_prompt: str = ""

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "success": self.success,
            "output": self.output,
            "errors": self.errors,
            "next_agent": self.next_agent,
            "needs_human": self.needs_human,
            "human_prompt": self.human_prompt,
        }


class BaseAgent(ABC):
    """Base class for all agents in the pipeline."""

    role: AgentRole
    name: str

    @abstractmethod
    def process(self, input_data: dict, context: dict) -> AgentResult:
        """Process input and return a result.

        Args:
            input_data: The data to process (varies by agent role).
            context: Shared context including memory, policies, preferences.

        Returns:
            AgentResult with output and next-agent routing.
        """
        ...


class IntakeAgent(BaseAgent):
    """Turns raw events into normalized ActionObjects.

    Responsibilities:
    - Parse raw events from pollers (Slack, Gmail, Jira, Freshservice, Calendar)
    - Classify work type, urgency, risk
    - Extract stakeholders and systems touched
    - Identify missing context
    - Produce a canonical ActionObject
    """
    role = AgentRole.INTAKE
    name = "intake"

    def process(self, input_data: dict, context: dict) -> AgentResult:
        from core.action_model import (
            ActionObject, WorkType, RiskLevel, ApprovalPolicy,
        )

        source = input_data.get("source", "")
        raw = input_data.get("raw_event", {})

        # Build ActionObject from raw event
        action = ActionObject.from_card_row(raw)

        # Classify work type based on content analysis
        action.work_type = self._classify_work_type(action)
        action.risk_level = self._assess_risk(action)
        action.approval_policy = self._determine_approval_policy(action)
        action.systems_touched = self._detect_systems(action)

        return AgentResult(
            agent=self.name,
            success=True,
            output={"action_object": action.to_dict()},
            next_agent=AgentRole.PLANNER.value,
        )

    def _classify_work_type(self, action) -> str:
        from core.action_model import WorkType
        text = (action.title + " " + action.summary).lower()

        type_keywords = {
            WorkType.INCIDENT.value: ["incident", "outage", "down", "broken", "urgent", "p1", "p2"],
            WorkType.REQUEST.value: ["request", "please", "need", "access", "setup", "configure"],
            WorkType.APPROVAL.value: ["approve", "approval", "sign-off", "confirm"],
            WorkType.INVESTIGATION.value: ["investigate", "look into", "why", "root cause", "analyze"],
            WorkType.RUNBOOK.value: ["runbook", "playbook", "procedure", "sop"],
            WorkType.MEETING.value: ["meeting", "standup", "sync", "1:1", "retro"],
            WorkType.AUTOMATION.value: ["automate", "script", "bot", "workflow"],
            WorkType.DOCUMENTATION.value: ["document", "wiki", "readme", "guide"],
        }

        for wtype, keywords in type_keywords.items():
            if any(kw in text for kw in keywords):
                return wtype

        if action.source in ("slack", "gmail"):
            return WorkType.MESSAGE.value

        return WorkType.UNKNOWN.value

    def _assess_risk(self, action) -> str:
        from core.action_model import RiskLevel
        text = (action.title + " " + action.summary).lower()

        if any(w in text for w in ["delete", "remove", "production", "prod", "critical"]):
            return RiskLevel.HIGH.value
        if any(w in text for w in ["change", "modify", "update", "configure"]):
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value

    def _determine_approval_policy(self, action) -> str:
        from core.action_model import ApprovalPolicy, RiskLevel
        if action.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
            return ApprovalPolicy.HUMAN_APPROVAL.value
        if action.source in ("freshservice", "jira"):
            return ApprovalPolicy.AUTO_IF_PLAYBOOK_MATCH.value
        return ApprovalPolicy.HUMAN_APPROVAL.value

    def _detect_systems(self, action) -> list:
        text = (action.title + " " + action.summary + " " + action.raw_body).lower()
        systems = []
        system_keywords = {
            "okta": ["okta", "sso", "saml", "oidc"],
            "jira": ["jira", "itwork", "sprint"],
            "freshservice": ["freshservice", "ticket", "service desk"],
            "slack": ["slack", "channel", "dm"],
            "google": ["google", "gws", "gmail", "workspace"],
            "jamf": ["jamf", "mdm", "mac"],
            "conductorone": ["conductorone", "c1", "access review"],
        }
        for system, keywords in system_keywords.items():
            if any(kw in text for kw in keywords):
                systems.append(system)
        return systems


class PlannerAgent(BaseAgent):
    """Builds execution plan from action + memory + playbooks.

    Responsibilities:
    - Match against known playbooks
    - Build contract-driven plan steps
    - Inject learned context from memory
    - Identify missing tools or capabilities
    """
    role = AgentRole.PLANNER
    name = "planner"

    def process(self, input_data: dict, context: dict) -> AgentResult:
        action_object = input_data.get("action_object", {})

        # This would normally call the existing CardPlanner
        # For now, produce a structured plan skeleton
        plan_skeleton = {
            "action_id": action_object.get("id"),
            "work_type": action_object.get("work_type"),
            "classification": action_object.get("classification"),
            "phases": [],
            "needs_llm_planning": True,
        }

        return AgentResult(
            agent=self.name,
            success=True,
            output={"plan": plan_skeleton},
            next_agent=AgentRole.POLICY.value,
        )


class PolicyAgent(BaseAgent):
    """Checks permissions, reversibility, approval requirements.

    Responsibilities:
    - Evaluate trust tier for the plan
    - Check policy rules from memory
    - Verify permissions for each step
    - Flag destructive or irreversible actions
    - Determine if human approval is needed
    """
    role = AgentRole.POLICY
    name = "policy"

    def process(self, input_data: dict, context: dict) -> AgentResult:
        from core.trust import TrustEvaluator

        plan = input_data.get("plan", {})
        action_object = input_data.get("action_object", {})

        evaluator = TrustEvaluator(
            verified_playbook_ids=context.get("verified_playbook_ids", []),
        )
        decision = evaluator.evaluate(action_object, plan=plan)

        return AgentResult(
            agent=self.name,
            success=True,
            output={
                "trust_decision": decision.to_dict(),
                "plan": plan,
            },
            next_agent=AgentRole.EXECUTOR.value if decision.can_auto_execute else None,
            needs_human=not decision.can_auto_execute,
            human_prompt=decision.reason if not decision.can_auto_execute else "",
        )


class ExecutorAgent(BaseAgent):
    """Runs deterministic steps or launches guided Claude execution.

    Responsibilities:
    - Execute approved plan steps
    - Track step outcomes
    - Handle retries and timeouts
    - Report progress
    """
    role = AgentRole.EXECUTOR
    name = "executor"

    def process(self, input_data: dict, context: dict) -> AgentResult:
        plan = input_data.get("plan", {})
        # Execution would use the existing plan execution infrastructure
        return AgentResult(
            agent=self.name,
            success=True,
            output={"plan": plan, "execution_status": "completed"},
            next_agent=AgentRole.REFLECTION.value,
        )


class ReflectionAgent(BaseAgent):
    """Compares expected vs actual outcome, extracts lessons.

    Responsibilities:
    - Compare plan expectations with actual results
    - Extract success/failure patterns
    - Identify optimization opportunities
    - Propose playbook updates
    """
    role = AgentRole.REFLECTION
    name = "reflection"

    def process(self, input_data: dict, context: dict) -> AgentResult:
        plan = input_data.get("plan", {})
        execution_status = input_data.get("execution_status", "")

        lessons = []
        playbook_updates = []

        # Compare expected vs actual for each step
        for phase in plan.get("phases", []):
            for step in phase.get("steps", []):
                expected = step.get("expected_output", "")
                actual = step.get("output", "")
                if step.get("status") == "failed":
                    lessons.append({
                        "type": "failure",
                        "step": step.get("summary", ""),
                        "error": step.get("output", ""),
                        "suggestion": "Consider adding retry or fallback",
                    })

        return AgentResult(
            agent=self.name,
            success=True,
            output={
                "lessons": lessons,
                "playbook_updates": playbook_updates,
            },
            next_agent=AgentRole.CURATOR.value if lessons else None,
        )


class CuratorAgent(BaseAgent):
    """Updates runbooks, patterns, and docs from successful runs.

    Responsibilities:
    - Update procedural memory with new patterns
    - Promote successful ad-hoc plans to draft playbooks
    - Update semantic memory with new facts
    - File documentation gaps
    """
    role = AgentRole.CURATOR
    name = "curator"

    def process(self, input_data: dict, context: dict) -> AgentResult:
        lessons = input_data.get("lessons", [])
        playbook_updates = input_data.get("playbook_updates", [])

        updates_made = []

        for lesson in lessons:
            updates_made.append({
                "type": "lesson_recorded",
                "detail": lesson,
            })

        return AgentResult(
            agent=self.name,
            success=True,
            output={"updates_made": updates_made},
            next_agent=None,  # end of pipeline
        )


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class AgentPipeline:
    """Orchestrates the multi-agent pipeline.

    Routes messages between agents based on AgentResult.next_agent.
    """

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.agents[AgentRole.INTAKE.value] = IntakeAgent()
        self.agents[AgentRole.PLANNER.value] = PlannerAgent()
        self.agents[AgentRole.POLICY.value] = PolicyAgent()
        self.agents[AgentRole.EXECUTOR.value] = ExecutorAgent()
        self.agents[AgentRole.REFLECTION.value] = ReflectionAgent()
        self.agents[AgentRole.CURATOR.value] = CuratorAgent()

    def register(self, role: str, agent: BaseAgent):
        self.agents[role] = agent

    def run(self, initial_input: dict, context: dict) -> List[AgentResult]:
        """Run the pipeline starting from intake.

        Returns a list of all agent results in execution order.
        Stops when an agent returns needs_human=True or next_agent=None.
        """
        results = []
        current_agent = AgentRole.INTAKE.value
        current_input = initial_input

        visited = set()
        max_steps = 10  # safety limit

        while current_agent and len(results) < max_steps:
            if current_agent in visited:
                break  # prevent cycles
            visited.add(current_agent)

            agent = self.agents.get(current_agent)
            if not agent:
                results.append(AgentResult(
                    agent=current_agent,
                    success=False,
                    errors=[f"Unknown agent: {current_agent}"],
                ))
                break

            result = agent.process(current_input, context)
            results.append(result)

            if not result.success or result.needs_human or not result.next_agent:
                break

            # Pass output as input to next agent
            current_input = result.output
            current_agent = result.next_agent

        return results
