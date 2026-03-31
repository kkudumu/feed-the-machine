"""Tests for all core modules — action model, contracts, playbooks, memory, trust, agents, adapters, self-healing, enterprise, onboarding."""

import json
import os
import sqlite3
import sys
import tempfile

import pytest

# Add parent dirs to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ---------------------------------------------------------------------------
# Action Model
# ---------------------------------------------------------------------------

class TestActionModel:
    def test_create_action_object(self):
        from core.action_model import ActionObject, WorkType, RiskLevel
        a = ActionObject(id=1, source="slack", title="Test", work_type=WorkType.REQUEST.value)
        assert a.id == 1
        assert a.work_type == "request"

    def test_round_trip(self):
        from core.action_model import ActionObject, MissingContext
        a = ActionObject(
            id=42,
            source="freshservice",
            title="SSO Setup for Linear",
            work_type="request",
            missing_context=[MissingContext("app_url", "Need the app login URL", blocking=True)],
            systems_touched=["okta", "freshservice"],
        )
        d = a.to_dict()
        b = ActionObject.from_dict(d)
        assert b.id == 42
        assert b.systems_touched == ["okta", "freshservice"]
        assert len(b.missing_context) == 1
        assert b.missing_context[0].blocking is True

    def test_from_card_row(self):
        from core.action_model import ActionObject
        row = {"id": 10, "source": "gmail", "subject": "Re: access request", "summary": "Need access to Okta"}
        a = ActionObject.from_card_row(row)
        assert a.id == 10
        assert a.title == "Re: access request"

    def test_has_blocking_gaps(self):
        from core.action_model import ActionObject, MissingContext
        a = ActionObject(missing_context=[MissingContext("x", "y", blocking=False)])
        assert a.has_blocking_gaps() is False
        a.missing_context.append(MissingContext("z", "w", blocking=True))
        assert a.has_blocking_gaps() is True

    def test_can_auto_run(self):
        from core.action_model import ActionObject, ApprovalPolicy
        a = ActionObject(approval_policy=ApprovalPolicy.AUTO_RUN.value)
        assert a.can_auto_run() is True
        a.approval_policy = ApprovalPolicy.HUMAN_APPROVAL.value
        assert a.can_auto_run() is False


# ---------------------------------------------------------------------------
# Plan Contracts
# ---------------------------------------------------------------------------

class TestPlanContracts:
    def test_contract_step_round_trip(self):
        from core.plan_contracts import ContractStep, Precondition, RollbackStrategy, ObservabilityHook
        step = ContractStep(
            index=1,
            summary="Create Jira ticket",
            tool="mcp__mcp-atlassian__jira_create_issue",
            preconditions=[Precondition("Jira project exists", check_type="api_check")],
            rollback=RollbackStrategy("Delete the ticket", tool="mcp__mcp-atlassian__jira_delete_issue"),
            observability=[ObservabilityHook("Check ticket created", hook_type="api_check")],
            run_mode="auto",
            determinism="deterministic",
        )
        d = step.to_dict()
        s2 = ContractStep.from_dict(d)
        assert s2.tool == step.tool
        assert len(s2.preconditions) == 1
        assert s2.rollback is not None
        assert s2.rollback.tool == "mcp__mcp-atlassian__jira_delete_issue"

    def test_preconditions_met(self):
        from core.plan_contracts import ContractStep, Precondition
        step = ContractStep(preconditions=[
            Precondition("A", met=True),
            Precondition("B", met=False),
        ])
        assert step.preconditions_met() is False
        step.preconditions[1].met = True
        assert step.preconditions_met() is True

    def test_from_legacy_step(self):
        from core.plan_contracts import ContractStep
        legacy = {"index": 3, "summary": "Do thing", "tool": "some_tool", "risk": "medium"}
        step = ContractStep.from_legacy_step(legacy)
        assert step.index == 3
        assert step.risk == "medium"


# ---------------------------------------------------------------------------
# Playbook Model
# ---------------------------------------------------------------------------

class TestPlaybookModel:
    def test_executable_playbook_round_trip(self):
        from core.playbook_model import (
            ExecutablePlaybook, TriggerCondition, ParamSpec,
            PlaybookStep, TypedToolCall, RollbackInstructions, FailureMode,
        )
        pb = ExecutablePlaybook(
            id="test-pb",
            name="Test Playbook",
            trigger_conditions=[TriggerCondition(keywords=["sso", "setup"])],
            input_schema=[ParamSpec(name="app_name", type="string", required=True)],
            steps=[PlaybookStep(
                id=1, name="Step 1",
                action=TypedToolCall(tool="mcp__jira__create_issue"),
            )],
            rollback=RollbackInstructions("Undo everything", steps=["Delete ticket"]),
            known_failure_modes=[FailureMode(id="f1", description="API timeout")],
        )
        d = pb.to_dict()
        pb2 = ExecutablePlaybook.from_dict(d)
        assert pb2.id == "test-pb"
        assert len(pb2.trigger_conditions) == 1
        assert pb2.input_schema[0].name == "app_name"
        assert pb2.rollback.description == "Undo everything"

    def test_from_legacy(self):
        from core.playbook_model import ExecutablePlaybook
        legacy = {
            "id": "fs-hide-catalog-el",
            "name": "Hide UI Elements",
            "trigger_keywords": ["hide button", "catalog item"],
            "input_params": {
                "item_ids": {"type": "array", "description": "Item IDs", "required": True},
            },
            "steps": [
                {"number": 1, "description": "Navigate", "tool": "playwright_cli", "command": "goto https://example.com", "session": "eng-buddy"},
            ],
            "rollback": {"description": "Revert the change", "steps": ["Step 1", "Step 2"]},
            "known_issues": [{"issue": "SPA bleed", "description": "Style persists", "fix": "Use setInterval"}],
            "confidence": 1.0,
            "version": 3,
            "executions": 1,
            "source": "observed",
        }
        pb = ExecutablePlaybook.from_legacy(legacy)
        assert pb.id == "fs-hide-catalog-el"
        assert len(pb.trigger_conditions) == 1
        assert pb.trigger_conditions[0].keywords == ["hide button", "catalog item"]
        assert len(pb.input_schema) == 1
        assert pb.input_schema[0].name == "item_ids"
        assert pb.rollback.description == "Revert the change"
        assert len(pb.known_failure_modes) == 1


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class TestMemory:
    @pytest.fixture
    def memory_store(self, tmp_path):
        from core.memory import MemoryStore
        db = str(tmp_path / "test_memory.db")
        return MemoryStore(db)

    def test_store_and_get(self, memory_store):
        from core.memory import PreferenceEntry
        pref = PreferenceEntry(key="response_tone", value="friendly", category="communication")
        memory_store.store_preference(pref)
        result = memory_store.get_preference("response_tone")
        assert result is not None
        assert result["value"] == "friendly"

    def test_episodic_append(self, memory_store):
        from core.memory import EpisodicMemory
        m1 = EpisodicMemory(run_id="run-1", outcome="success")
        m2 = EpisodicMemory(run_id="run-2", outcome="failure")
        memory_store.store_episodic(m1)
        memory_store.store_episodic(m2)
        episodes = memory_store.get_recent_episodes()
        assert len(episodes) == 2

    def test_semantic_facts(self, memory_store):
        from core.memory import SemanticFact
        fact = SemanticFact(subject="okta", predicate="supports", value="saml-sso")
        memory_store.store_fact(fact)
        facts = memory_store.get_facts_about("okta")
        assert len(facts) >= 1
        assert facts[0]["value"] == "saml-sso"

    def test_policy_storage(self, memory_store):
        from core.memory import PolicyRule
        rule = PolicyRule(rule_id="no-auto-delete", description="Never auto-delete tickets")
        memory_store.store_policy(rule)
        result = memory_store.get_policy("no-auto-delete")
        assert result is not None
        assert "auto-delete" in result["description"]

    def test_search(self, memory_store):
        from core.memory import SemanticFact
        memory_store.store_fact(SemanticFact("jira", "has_project", "ITWORK2"))
        memory_store.store_fact(SemanticFact("jira", "has_board", "Systems"))
        results = memory_store.search("semantic", "ITWORK2")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Trust
# ---------------------------------------------------------------------------

class TestTrust:
    def test_auto_run_tier(self):
        from core.trust import TrustEvaluator, TrustTier
        evaluator = TrustEvaluator()
        decision = evaluator.evaluate({"approval_policy": TrustTier.AUTO_RUN.value})
        assert decision.can_auto_execute is True

    def test_never_auto_tier(self):
        from core.trust import TrustEvaluator, TrustTier
        evaluator = TrustEvaluator()
        decision = evaluator.evaluate({"approval_policy": TrustTier.NEVER_AUTO.value})
        assert decision.can_auto_execute is False

    def test_playbook_match(self):
        from core.trust import TrustEvaluator, TrustTier
        evaluator = TrustEvaluator(verified_playbook_ids=["fs-hide-catalog-el"])
        decision = evaluator.evaluate(
            {"approval_policy": TrustTier.AUTO_IF_PLAYBOOK.value, "playbook_id": "fs-hide-catalog-el"},
        )
        assert decision.can_auto_execute is True

    def test_read_only_step(self):
        from core.trust import TrustEvaluator
        evaluator = TrustEvaluator()
        decision = evaluator.evaluate_step({"tool": "mcp__mcp-atlassian__jira_get_issue", "risk": "low"})
        assert decision.can_auto_execute is True

    def test_destructive_step(self):
        from core.trust import TrustEvaluator
        evaluator = TrustEvaluator()
        decision = evaluator.evaluate_step({"tool": "mcp__mcp-atlassian__jira_delete_issue", "risk": "high"})
        assert decision.can_auto_execute is False


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class TestAgents:
    def test_intake_agent(self):
        from core.agents import IntakeAgent
        agent = IntakeAgent()
        result = agent.process(
            {"raw_event": {"source": "freshservice", "subject": "SSO Setup for Linear", "summary": "Need SSO configured"}, "source": "freshservice"},
            context={},
        )
        assert result.success is True
        action = result.output["action_object"]
        assert action["work_type"] == "request"
        assert "okta" in action["systems_touched"] or "freshservice" in action["systems_touched"]

    def test_pipeline_runs(self):
        from core.agents import AgentPipeline
        pipeline = AgentPipeline()
        results = pipeline.run(
            {"raw_event": {"source": "slack", "subject": "Hey", "summary": "Quick question"}, "source": "slack"},
            context={"verified_playbook_ids": []},
        )
        assert len(results) >= 1
        assert results[0].agent == "intake"

    def test_pipeline_stops_on_human(self):
        from core.agents import AgentPipeline
        pipeline = AgentPipeline()
        results = pipeline.run(
            {"raw_event": {"source": "freshservice", "subject": "Delete server", "summary": "Please delete the production server"}, "source": "freshservice"},
            context={"verified_playbook_ids": []},
        )
        # Should stop at policy agent requiring human approval
        has_human_stop = any(r.needs_human for r in results)
        assert has_human_stop is True


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class TestAdapters:
    def test_registry(self):
        from core.adapters import AdapterRegistry, Capability
        registry = AdapterRegistry()
        registry.register_defaults()
        assert registry.get("jira") is not None
        assert registry.get("freshservice") is not None
        assert registry.get("slack") is not None

    def test_find_by_capability(self):
        from core.adapters import AdapterRegistry, Capability
        registry = AdapterRegistry()
        registry.register_defaults()
        adapters = registry.find_by_capability(Capability.CREATE_TICKET.value)
        systems = [a.system for a in adapters]
        assert "jira" in systems
        assert "freshservice" in systems

    def test_get_tool_for_capability(self):
        from core.adapters import AdapterRegistry, Capability
        registry = AdapterRegistry()
        registry.register_defaults()
        tool = registry.get_tool_for(Capability.CREATE_TICKET.value, preferred_system="jira")
        assert tool == "mcp__mcp-atlassian__jira_create_issue"

    def test_user_profile_from_context(self):
        from core.adapters import UserProfile
        ctx = {
            "role": "IT Systems Engineer",
            "team": "IT Engineering",
            "company": "Klaviyo",
            "email": "kioja.kudumu@klaviyo.com",
            "preferences": {"response_tone": "friendly but concise"},
        }
        profile = UserProfile.from_context_json(ctx)
        assert profile.role == "IT Systems Engineer"
        assert profile.company == "Klaviyo"
        assert profile.response_tone == "friendly but concise"


# ---------------------------------------------------------------------------
# Self-Healing
# ---------------------------------------------------------------------------

class TestSelfHealing:
    def test_failure_classifier(self):
        from core.self_healing import FailureClassifier, FailureClass
        assert FailureClassifier.classify("401 Unauthorized") == FailureClass.AUTH_FAILURE.value
        assert FailureClassifier.classify("Request timed out after 30s") == FailureClass.TIMEOUT.value
        assert FailureClassifier.classify("429 Too Many Requests") == FailureClass.RATE_LIMIT.value
        assert FailureClassifier.classify("Something weird happened") == FailureClass.UNKNOWN.value

    def test_self_healing_engine(self):
        from core.self_healing import SelfHealingEngine, RecoveryAction
        engine = SelfHealingEngine()
        result = engine.handle_failure(
            step={"index": 1, "summary": "Fetch ticket", "tool": "mcp__freshservice__get_ticket"},
            error_message="401 Unauthorized - Invalid API key",
        )
        assert result["failure_class"] == "auth_failure"
        assert result["recovery_action"] == RecoveryAction.ESCALATE.value

    def test_failure_stats(self):
        from core.self_healing import SelfHealingEngine
        engine = SelfHealingEngine()
        engine.handle_failure({"index": 1, "tool": "tool_a"}, "timeout")
        engine.handle_failure({"index": 2, "tool": "tool_a"}, "timeout again")
        engine.handle_failure({"index": 3, "tool": "tool_b"}, "401 unauthorized")
        stats = engine.get_failure_stats()
        assert stats["total"] == 3
        assert stats["by_tool"]["tool_a"] == 2


# ---------------------------------------------------------------------------
# Enterprise
# ---------------------------------------------------------------------------

class TestEnterprise:
    @pytest.fixture
    def ledger(self, tmp_path):
        from core.enterprise import ExecutionLedger
        return ExecutionLedger(str(tmp_path / "test_ledger.db"))

    def test_ledger_record_and_retrieve(self, ledger):
        from core.enterprise import LedgerEntry
        entry = LedgerEntry(
            event_type="step_complete",
            card_id=42,
            plan_id="plan-1",
            step_index=1,
            tool="mcp__jira__create_issue",
            status="success",
        )
        entry_id = ledger.record(entry)
        assert entry_id > 0

        entries = ledger.get_for_card(42)
        assert len(entries) == 1
        assert entries[0]["tool"] == "mcp__jira__create_issue"

    def test_ledger_stats(self, ledger):
        from core.enterprise import LedgerEntry
        ledger.record(LedgerEntry(event_type="step", status="success"))
        ledger.record(LedgerEntry(event_type="step", status="success"))
        ledger.record(LedgerEntry(event_type="step", status="failure"))
        stats = ledger.get_stats()
        assert stats["total"] == 3
        assert stats["successes"] == 2
        assert stats["failures"] == 1

    def test_shadow_executor(self, ledger):
        from core.enterprise import ShadowExecutor
        executor = ShadowExecutor(ledger)
        plan = {
            "id": "plan-1",
            "phases": [{
                "name": "phase1",
                "steps": [
                    {"index": 1, "tool": "mcp__mcp-atlassian__jira_get_issue", "risk": "low"},
                    {"index": 2, "tool": "mcp__mcp-atlassian__jira_delete_issue", "risk": "high"},
                ],
            }],
        }
        results = executor.simulate_plan(plan, {"id": 1})
        assert len(results) == 2
        assert results[0].would_execute is True   # read-only
        assert results[1].would_execute is False  # destructive

    def test_eval_harness(self):
        from core.enterprise import EvalHarness, EvalCase
        harness = EvalHarness()
        harness.add_case(EvalCase(
            id="test-1",
            name="SSO request classification",
            input_event={"source": "freshservice", "subject": "SSO Setup for Linear", "summary": "Please configure SSO"},
            expected_work_type="request",
        ))
        summary = harness.run_all()
        assert summary["total"] == 1
        assert summary["passed"] == 1


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

class TestOnboarding:
    def test_declare_systems(self):
        from core.onboarding import OnboardingEngine
        engine = OnboardingEngine()
        result = engine.declare_systems(["jira", "freshservice", "slack"])
        assert len(result["integrations_found"]) >= 3
        assert "jira" in result["credentials_needed"]

    def test_set_trust_tier(self):
        from core.onboarding import OnboardingEngine, OnboardingTier
        engine = OnboardingEngine()
        result = engine.set_trust_tier(OnboardingTier.TIER_2.value)
        assert result["tier"] == "tier_2"
        assert "Draft mode" in result["description"]

    def test_invalid_tier(self):
        from core.onboarding import OnboardingEngine
        engine = OnboardingEngine()
        result = engine.set_trust_tier("tier_99")
        assert "error" in result

    def test_onboarding_status(self):
        from core.onboarding import OnboardingEngine
        engine = OnboardingEngine()
        engine.declare_systems(["jira", "slack"])
        status = engine.get_status()
        assert status["systems_declared"] == 2
        assert status["progress_pct"] == 0  # nothing verified yet
