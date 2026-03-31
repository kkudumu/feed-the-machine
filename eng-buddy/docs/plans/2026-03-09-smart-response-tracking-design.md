# Smart Response Tracking & Cross-Channel Resolution

**Date**: 2026-03-09
**Branch**: feature/smart-response-tracking

## Problem

Pollers don't detect when the user responds to messages outside the dashboard. Cards stay in "needs action" even after responding directly in Gmail or Slack. Related cards across channels (e.g., Gmail invite + Slack message from the same person about the same topic) aren't linked — responding on one channel doesn't resolve the other. Additionally, there's no way to force a poller sync from the UI.

## Feature 1: Response Detection in Pollers

### Gmail Poller (`bin/gmail-poller.py`)

Add a **response sweep** after processing new emails each cycle:

1. Query `inbox.db` for Gmail cards with `section IN ('action-needed', 'needs-action')` and `responded = 0`
2. For each card, extract `thread_id` from the `proposed_actions` JSON
3. Use Gmail MCP `search_emails` to fetch thread messages
4. Check if any message in the thread has the user's email in `From` with a timestamp after the card's timestamp
5. If found: UPDATE card → `responded = 1, section = 'no-action', classification = 'responded'`

### Slack Poller (`bin/slack-poller.py`)

The poller already detects responses via `_has_later_self_message()`, but `write_to_inbox_db()` uses `INSERT OR IGNORE` which skips existing cards.

**Change**: Switch to `INSERT ... ON CONFLICT(source, summary) DO UPDATE` for `responded`, `section`, and `classification` fields when the new data shows `responded = True`. Re-polls that detect a new self-reply will update the existing card.

## Feature 2: Cross-Channel Linking

### Server Endpoint: `POST /api/cards/{card_id}/resolve-related`

Called automatically after a poller updates a card to `responded = 1`.

**Flow:**

1. Extract **person name** and **topic keywords** from the responded card's summary, context_notes, and proposed_actions
2. Query `inbox.db` for all pending cards (`responded = 0`, `section IN needs-action variants`) across other sources
3. Score each candidate on two axes:
   - **Person match**: fuzzy match on sender name/email (e.g., "Jeannette Vivas" ↔ "jeannette.vivas@klaviyo.com"). Normalize, compare. Threshold: 0.8
   - **Topic match**: keyword overlap between summaries/context_notes via Jaccard similarity on word tokens. Threshold: 0.3
4. If both thresholds exceeded → auto-resolve: `responded = 1, section = 'no-action', classification = 'responded'`, append to context_notes: "Auto-resolved: responded via {source}"
5. Emit SSE `cache-invalidate` for affected sources

### Poller Integration

After updating a card to `responded`, both pollers HTTP POST to `/api/cards/{card_id}/resolve-related`. Server handles matching logic centrally — pollers stay simple.

### Matching Implementation

- **Person**: extract name from summary (before `<` in email headers, or Slack display name), normalize case, strip whitespace, fuzzy compare (SequenceMatcher or similar)
- **Topic**: extract subject line / keywords from summary and context_notes, tokenize, compute Jaccard similarity on word sets
- Require both person > 0.8 AND topic > 0.3

## Feature 3: Click-to-Sync

### Backend: `POST /api/pollers/{poller_id}/sync`

1. Look up poller by ID from `POLLER_DEFINITIONS`
2. If already syncing (tracked in `_running_syncs` dict), return `{"status": "already_syncing"}`
3. Run the poller script (`bin/{id}-poller.py`) as a background subprocess
4. Return immediately with `{"status": "syncing"}`
5. Poller itself calls `/api/cache-invalidate` on completion — SSE handles UI refresh

### Frontend: Click handler on poller badges

1. Add `click` event on `.poller-badge` elements, extract poller ID from data attribute
2. POST `/api/pollers/{id}/sync`
3. Add CSS class `syncing` to the badge → shows spinner animation replacing countdown
4. On next SSE `cache-invalidate` for that source → remove `syncing` class, refresh timer
5. Timeout fallback: remove `syncing` after 60s if no SSE received

### CSS

`.poller-badge.syncing .poller-countdown` → CSS spinner (rotating border), same badge dimensions.

## Files to Modify

| File | Changes |
|------|---------|
| `bin/gmail-poller.py` | Add response sweep after classification |
| `bin/slack-poller.py` | Change INSERT OR IGNORE → ON CONFLICT DO UPDATE for responded cards |
| `dashboard/server.py` | Add `/api/pollers/{id}/sync` and `/api/cards/{id}/resolve-related` endpoints |
| `dashboard/static/app.js` | Add click-to-sync handler on poller badges, syncing state management |
| `dashboard/static/style.css` (or theme files) | Add `.syncing` spinner animation |

## Data Flow

```
User responds in Gmail/Slack directly
    ↓
Poller runs (scheduled or force-synced)
    ↓
Detects response → UPDATE card (responded=1, section=no-action)
    ↓
POST /api/cards/{id}/resolve-related
    ↓
Server finds cross-channel matches (person + topic)
    ↓
Auto-resolves related cards → SSE cache-invalidate
    ↓
Dashboard refreshes affected tabs
```
