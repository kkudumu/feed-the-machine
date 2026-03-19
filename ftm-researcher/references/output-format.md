# Output Format Specification

## Structured JSON Artifact

This is the primary output for skill-to-skill consumption (ftm-brainstorm, ftm-executor, etc.).

### Schema

```json
{
  "query": "original research question",
  "mode": "quick | standard | deep",
  "timestamp": "ISO-8601",
  "waves_completed": 1,
  "agents_dispatched": 7,
  "council_used": true,
  "duration_ms": 12345,

  "findings": [
    {
      "id": "f-001",
      "claim": "one-sentence factual claim",
      "evidence": "2-3 sentence supporting detail",
      "source_url": "https://...",
      "source_type": "primary | peer_reviewed | official_docs | code_repo | qa_site | news | blog | forum | codebase",
      "confidence": 0.85,
      "credibility_score": 0.78,
      "trust_level": "high | moderate | low | verify",
      "agent_role": "web_surveyor | academic_scout | github_miner | competitive_analyst | stack_overflow_digger | codebase_analyst | historical_investigator",
      "wave": 1,
      "corroborated": true,
      "circular_sourcing": false
    }
  ],

  "disagreement_map": {
    "consensus": [
      {
        "claim": "...",
        "supporting_agents": ["web_surveyor", "github_miner", "academic_scout"],
        "source_count": 5,
        "source_diversity": 3,
        "council_verdict": "agreed",
        "confidence": 0.92
      }
    ],
    "contested": [
      {
        "claim_a": "...",
        "claim_b": "...",
        "agents_for_a": ["web_surveyor"],
        "agents_for_b": ["competitive_analyst"],
        "council_verdict": "contested",
        "provider_positions": {
          "claude": "a",
          "codex": "b",
          "gemini": "a"
        },
        "rank_winner": "a",
        "judge_rationale": "..."
      }
    ],
    "unique_insights": [
      {
        "claim": "...",
        "agent_role": "historical_investigator",
        "confidence": 0.6,
        "note": "Single source — may be high-value insight or hallucination"
      }
    ],
    "refuted": [
      {
        "claim": "...",
        "rejection_reason": "Council unanimously rejected — evidence traces to a single unreliable blog post",
        "original_agent": "web_surveyor"
      }
    ]
  },

  "metadata": {
    "sources_total": 34,
    "sources_high_trust": 12,
    "sources_moderate_trust": 15,
    "sources_low_trust": 7,
    "circular_sourcing_detected": 2,
    "agent_performance": {
      "web_surveyor": {"findings": 6, "avg_credibility": 0.65},
      "academic_scout": {"findings": 4, "avg_credibility": 0.88}
    }
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|---|---|---|---|
| query | string | yes | The original research question |
| mode | enum | yes | quick, standard, or deep |
| timestamp | ISO-8601 | yes | When the research completed |
| waves_completed | integer | yes | 1 for quick/standard, 1-2 for deep |
| agents_dispatched | integer | yes | Total agents spawned across all waves |
| council_used | boolean | yes | Whether ftm-council was invoked |
| duration_ms | integer | yes | Total execution time |
| findings | array | yes | All individual findings |
| disagreement_map | object | standard/deep | The 4-tier reconciled output |
| metadata | object | yes | Aggregate statistics |

### Finding ID Convention

Finding IDs follow the pattern `f-NNN` where NNN is a zero-padded sequential number. IDs are stable within a session — if the user drills down on finding #3, it remains f-003 even after new findings are added.

---

## Markdown Rendering Template

For user display:

```markdown
# Research: [query]

**Mode:** [mode] | **Agents:** [count] | **Sources:** [total] | **Duration:** [time]

---

## Consensus Findings

[For each consensus claim:]
**[N].** [claim] ([confidence]% confidence)
- *Evidence:* [key evidence summary]
- *Sources:* [source count] across [diversity] types — [top source URL]
- *Agreed by:* [agent list]

---

## Contested — Where Agents Disagreed

[For each contested pair:]
**[N].** [topic of disagreement]

| Position A | Position B |
|---|---|
| [claim_a] | [claim_b] |
| Supported by: [agents_for_a] | Supported by: [agents_for_b] |
| [evidence summary] | [evidence summary] |

*Ranking:* [winner] — [judge rationale summary]
*Council:* [provider positions if available]

---

## Unique Insights — Unverified but Interesting

[For each unique insight:]
- **[claim]** (from [agent_role], [confidence]% confidence)
  - [note about single-source status]

---

## Refuted — What We Ruled Out

[For each refuted claim:]
- ~~[claim]~~ — [rejection_reason]

---

## Source Summary

| Source Type | Count | Avg Credibility |
|---|---|---|
| [type] | [count] | [avg score] |

---

*What's next? You can:*
- *"dig deeper on #N"* — spawn targeted agents on a specific finding
- *"I disagree with #N"* — find counter-evidence
- *"focus on [angle]"* — reshape and re-run with new weights
- *"council #N"* — route a specific claim to ftm-council
- *"compare A vs B"* — spawn comparison agent
- *"done"* — finalize the research session
```

---

## Conversational Iteration Protocol

After presenting results, the skill enters iteration mode. Each user command triggers a specific action:

| User Command | Action | Updates |
|---|---|---|
| "dig deeper on #N" | Spawn 3 targeted agents on finding N's topic | Add new findings, re-render |
| "I think X is wrong because Y" | Spawn counter-evidence agents + update findings | May move claims between tiers |
| "focus on [angle]" | Reshape subtopics, re-dispatch with new weights | Full re-run with angle bias |
| "council #N" | Route specific finding to ftm-council | Update council_verdict for that claim |
| "more on [agent]'s findings" | Re-dispatch that agent with broader query | Add new findings from that domain |
| "compare A vs B" | Spawn comparison agent with both findings as context | Add comparison analysis |
| "done" | Finalize, write blackboard, emit events | Session ends |

Each iteration:
1. Updates the JSON artifact (new findings get new IDs, tiers may change)
2. Re-renders the markdown with changes highlighted
3. Preserves the full conversation history for ftm-pause/resume
