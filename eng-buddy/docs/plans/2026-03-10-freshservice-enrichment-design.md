# Freshservice Enrichment Pipeline — Design

**Date**: 2026-03-10
**Status**: Approved
**Problem**: Freshservice cards on the dashboard only show a single generic "Review Freshservice ticket" action. No classification, no contextual actions, no playbook matching.

## Goal

A fully agentic enrichment pipeline that:
- Classifies every Freshservice ticket using AI (no static rules)
- Generates 2-5 contextual next-step actions per ticket
- Matches tickets against approved playbooks
- Auto-drafts new playbooks when it detects repeating patterns
- Evolves its own classification schema over time
- Requires human approval only for new playbooks and schema changes

## Architecture

### Pipeline Overview

```
freshservice-poller.py           (existing, unchanged — fast, dumb)
        ↓ writes raw cards to inbox.db
freshservice-enrichment.py       (NEW — 3-stage AI pipeline)
        ├── stage_classify()     → AI classifies ticket, builds/evolves schema
        ├── stage_enrich()       → AI generates actions + matches playbooks (parallel 5x)
        └── stage_detect_patterns() → AI detects repeating patterns, drafts playbooks
```

### Trigger & Scheduling

- LaunchAgent: `com.engbuddy.freshservice-enrichment`
- Interval: every 5 minutes, offset ~2.5 min from poller
- Picks up cards where `enrichment_status = 'not_enriched'`
- After each card is enriched, hits `/api/cache-invalidate` → dashboard refreshes progressively

### LLM Abstraction

All AI calls go through a single function with per-stage model routing:

```python
STAGE_LLM_CONFIG = {
    "classify":         {"cli": "claude", "args": ["-p", "--model", "haiku"]},
    "enrich":           {"cli": "claude", "args": ["-p", "--model", "sonnet"]},
    "detect_patterns":  {"cli": "claude", "args": ["-p", "--model", "sonnet"]},
}

def _run_llm(prompt: str, stage: str) -> str:
    config = STAGE_LLM_CONFIG.get(stage, {"cli": "claude", "args": ["-p"]})
    result = subprocess.run(
        [config["cli"]] + config["args"],
        input=prompt, capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()
```

Ships with Claude for all stages. Config is swappable to `codex --yolo`, `gemini --yolo`, etc. per stage without code changes.

## Stage Details

### Stage 1: stage_classify(card)

**Purpose**: Classify ticket into a bucket. Build and evolve the classification schema using AI.

**Flow**:
1. Load current schema from `classification_buckets` table
2. Check if ticket matches a vetted bucket's AI-generated keywords (fast-path, no AI call)
3. If no fast-path match → call AI with ticket summary + metadata + current schema
4. AI returns: bucket ID, bucket description, relevant knowledge files, confidence keywords
5. If bucket is new → insert into schema as "emerging"
6. If bucket exists → increment ticket count; if count >= 3 → promote to "vetted"
7. Write classification to card's `analysis_metadata`

**Fast-path**: Once a bucket has 3+ tickets (vetted), the AI will have generated confidence keywords. Tickets matching those keywords skip the AI call. This is not a static rule — it's an AI-generated rule that evolves as more tickets are classified.

**Schema evolution**: If AI proposes splitting/merging buckets, the change is written as a draft proposal (visible on dashboard) requiring human approval.

**Prompt shape**:
```
You are classifying an IT support ticket for an IT systems engineer.

Ticket: #{id} [{type}] {subject}
Priority: {priority} | Status: {status} | Created: {date}
Requester: {requester_id} | Group: {group_id}

Current classification schema:
{json_schema}

Tasks:
1. Classify this ticket into an existing bucket, or propose a new one.
2. List which knowledge files from the engineer's knowledge base would help resolve this.
3. Provide 3-5 confidence keywords that future similar tickets would contain.

Return JSON:
{
  "bucket_id": "kebab-case-name",
  "bucket_description": "what this category covers",
  "is_new_bucket": true/false,
  "knowledge_files": ["sso-scim-process.md", "infrastructure.md"],
  "confidence_keywords": ["okta", "scim", "sso"],
  "reasoning": "one sentence"
}
```

### Stage 2: stage_enrich(card) — Parallel Batched

**Purpose**: Generate contextual actions and match playbooks. This is the expensive stage.

**Flow**:
1. Fetch full ticket description from Freshservice API (`GET /api/v2/tickets/{id}?include=conversations`)
2. Load knowledge files identified by stage_classify
3. Load list of approved playbooks (name + description + step summaries)
4. Call AI with: ticket details + knowledge excerpts + playbooks
5. AI returns: 2-5 proposed actions + optional playbook match with applicable steps
6. Write `proposed_actions` + enrichment metadata to card in DB
7. Set `enrichment_status = 'enriched'`
8. Hit `/api/cache-invalidate` → dashboard updates this card

**Parallel execution**: `ThreadPoolExecutor(max_workers=5)` — 5 tickets enriching concurrently. ~15 seconds per batch of 5.

**Prompt shape**:
```
You are an IT systems engineering assistant triaging a Freshservice ticket.

Ticket: #{id} [{type}] {subject}
Description: {description}
Priority: {priority} | Status: {status} | Created: {date}
Classification: {bucket_id} — {bucket_description}

Relevant knowledge:
{knowledge_file_excerpts}

Approved playbooks:
{playbook_summaries}

Tasks:
1. Generate 2-5 specific, actionable next steps for this ticket.
2. If any approved playbook matches, identify which one and which steps apply.

Return JSON:
{
  "proposed_actions": [
    {"type": "action_type", "draft": "specific action description"}
  ],
  "playbook_match": {
    "playbook_id": "id or null",
    "playbook_name": "name or null",
    "applicable_steps": [1, 2, 4],
    "reasoning": "why this playbook matches"
  } | null
}

Action types can be: reply_to_requester, escalate, create_jira_ticket,
follow_playbook, investigate, close_ticket, request_info, grant_access,
check_integration, review_config, or any other relevant type.
Be specific — not "investigate the issue" but "check Okta SCIM provisioning logs for failed sync events".
```

### Stage 3: stage_detect_patterns() — Once Per Cycle

**Purpose**: Look across all recently enriched tickets, detect repeating workflows, auto-draft playbooks.

**Flow**:
1. Query all enriched Freshservice cards from last 30 days
2. Group by classification bucket
3. For each bucket with 3+ tickets: send to AI with the tickets' enriched actions
4. AI determines if there's a repeating workflow worth codifying
5. If yes → draft a playbook via `brain.py --playbook-draft` with steps derived from the common actions
6. Playbook appears on dashboard Playbooks tab as "draft" for human approval
7. Write pattern metadata to `enrichment_runs` for observability

**Runs once per enrichment cycle**, not per card. Only processes buckets that have gained new tickets since last pattern check.

**Prompt shape**:
```
You are analyzing IT support ticket patterns to identify repeatable workflows.

Bucket: {bucket_id} — {bucket_description}
Tickets in this bucket (last 30 days):
{list of ticket summaries + their enriched actions}

Questions:
1. Is there a repeating workflow pattern across these tickets?
2. If yes, what are the common steps that could become a playbook?
3. What should trigger this playbook (keywords, ticket type, etc.)?

Return JSON:
{
  "pattern_detected": true/false,
  "confidence": "high/medium/low",
  "playbook_draft": {
    "name": "playbook-name",
    "description": "what this playbook automates",
    "trigger_keywords": ["keyword1", "keyword2"],
    "steps": [
      {"name": "step description", "tool": "tool_name", "requires_human": true/false}
    ]
  } | null,
  "reasoning": "explanation"
}
```

## DB Schema Changes

### New column on `cards`:
```sql
ALTER TABLE cards ADD COLUMN enrichment_status TEXT DEFAULT 'not_enriched';
-- values: not_enriched, enriching, enriched, failed
```

### New table — classification schema (AI-built):
```sql
CREATE TABLE IF NOT EXISTS classification_buckets (
    id TEXT PRIMARY KEY,
    description TEXT,
    knowledge_files TEXT,          -- JSON array
    confidence_keywords TEXT,      -- JSON array (AI-generated)
    ticket_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'emerging', -- emerging | vetted
    created_by_ticket INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### New table — enrichment observability:
```sql
CREATE TABLE IF NOT EXISTS enrichment_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER,
    stage TEXT,                    -- classify | enrich | detect_patterns
    model TEXT,                    -- which LLM was used
    prompt_tokens INTEGER,
    duration_ms INTEGER,
    status TEXT,                   -- success | failed
    response_summary TEXT,         -- truncated response for debugging
    created_at TEXT DEFAULT (datetime('now'))
);
```

## Dashboard Integration

### Card rendering changes:
- Enriched cards show 2-5 actions instead of generic "Review ticket"
- If playbook matched: show badge `PLAYBOOK: {name}` on the card
- Enrichment status indicator per card: spinner (enriching), checkmark (enriched), warning (failed)

### Playbooks tab:
- Auto-drafted playbooks appear with "DRAFT" badge
- Approval/reject/edit controls (existing functionality)
- Show which tickets triggered the draft

### Schema management (future, low priority):
- View classification buckets and their stats
- Approve/reject schema change proposals (bucket splits/merges)

## File Structure

```
bin/
  freshservice-poller.py              (existing, unchanged)
  freshservice-enrichment.py          (NEW — pipeline script)
  com.engbuddy.freshservice-enrichment.plist  (NEW — LaunchAgent)
```

## Performance Characteristics

| Scenario | AI Calls | Time |
|----------|----------|------|
| First run (78 tickets, cold) | 78 classify + 78 enrich + 1 detect = 157 | ~3-4 min (5x parallel enrich) |
| Steady state (2-3 new tickets) | 2-3 classify + 2-3 enrich + 1 detect = 6-7 | ~15-20 sec |
| Mature (vetted buckets, most tickets fast-path) | 0-1 classify + 2-3 enrich + 1 detect = 3-5 | ~10-15 sec |

## Approval Gates

| Action | Automatic | Requires Approval |
|--------|-----------|-------------------|
| Classify ticket | Yes | No |
| Generate actions | Yes | No |
| Match existing playbook | Yes | No |
| Promote bucket to "vetted" | Yes (at 3+ tickets) | No |
| Draft new playbook | Yes (auto-draft) | Yes (dashboard approval) |
| Split/merge classification buckets | Proposed by AI | Yes (dashboard approval) |
| Change LLM per stage | N/A | Manual config change |
