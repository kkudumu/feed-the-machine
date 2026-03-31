# Smart Response Tracking & Cross-Channel Resolution — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detect when the user responds to messages outside the dashboard, auto-resolve related cross-channel cards by person+topic matching, and allow force-syncing pollers from the UI.

**Architecture:** Three independent features that compose: (1) Gmail poller gains a response sweep that checks threads for user replies, (2) server gains a `/resolve-related` endpoint that fuzzy-matches person+topic across channels, (3) server gains a `/pollers/{id}/sync` endpoint with frontend click-to-sync on poller badges.

**Tech Stack:** Python/FastAPI (server), vanilla JS (frontend), SQLite (inbox.db), Gmail REST API (thread checking), `difflib.SequenceMatcher` (fuzzy matching)

---

## Task 1: Gmail Poller — Response Sweep

**Files:**
- Modify: `bin/gmail-poller.py:257-294` (write_card_to_db), add new function after line 340
- Modify: `bin/gmail-poller.py:488-589` (main, after classification loop)

**Step 1: Add `sweep_responded_cards()` function**

Add after `update_filter_suggestions()` (after line 340) in `bin/gmail-poller.py`:

```python
def sweep_responded_cards(token):
    """
    Check unresolved Gmail cards for user replies in the thread.
    If the user has replied, mark the card as responded.
    """
    conn = db_connect()
    if conn is None:
        return 0

    try:
        rows = conn.execute(
            """SELECT id, summary, proposed_actions, timestamp
               FROM cards
               WHERE source = 'gmail'
                 AND responded = 0
                 AND section IN ('action-needed', 'needs-action', 'needs-response')
                 AND status = 'pending'""",
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return 0

    if not rows:
        conn.close()
        return 0

    resolved_count = 0
    resolved_ids = []

    for row in rows:
        card_id = row[0]
        proposed_actions_raw = row[2] or "[]"
        card_timestamp = row[3] or ""

        try:
            actions = json.loads(proposed_actions_raw)
        except (json.JSONDecodeError, TypeError):
            actions = []

        thread_id = ""
        for action in actions:
            thread_id = action.get("thread_id", "")
            if thread_id:
                break

        if not thread_id:
            continue

        # Fetch thread messages from Gmail API
        try:
            thread_data = gmail_get(f"threads/{thread_id}", {"format": "metadata", "metadataHeaders": ["From"]}, token=token)
        except Exception as exc:
            print(f"[{datetime.now().strftime('%H:%M')}] Thread fetch failed for {thread_id}: {exc}")
            continue

        thread_messages = thread_data.get("messages", [])

        # Check if any message in the thread is from the user (sent after card timestamp)
        user_replied = False
        for msg in thread_messages:
            msg_from = ""
            for h in msg.get("payload", {}).get("headers", []):
                if h["name"].lower() == "from":
                    msg_from = h["value"]
                    break

            _, from_email = parseaddr(msg_from)
            if not from_email:
                continue

            # Check if this is from the user's own email
            if from_email.lower().endswith("@klaviyo.com") or "kioja" in from_email.lower():
                # Verify it was sent after the card was created
                msg_internal = msg.get("internalDate", "0")
                msg_ts = int(msg_internal) / 1000 if msg_internal else 0

                try:
                    card_dt = datetime.fromisoformat(card_timestamp.replace("Z", "+00:00"))
                    card_ts = card_dt.timestamp()
                except (ValueError, TypeError):
                    card_ts = 0

                if msg_ts > card_ts:
                    user_replied = True
                    break

        if user_replied:
            conn.execute(
                """UPDATE cards
                   SET responded = 1, section = 'no-action', classification = 'responded'
                   WHERE id = ?""",
                (card_id,),
            )
            resolved_count += 1
            resolved_ids.append(card_id)

        time.sleep(0.15)  # rate limiting

    if resolved_count:
        conn.commit()
    conn.close()

    return resolved_count, resolved_ids
```

**Step 2: Call sweep from main() and trigger cross-channel resolution**

Add after `invalidate_dashboard_cache("gmail")` at the end of `main()` (line 589):

```python
    # Response sweep: check if user replied to any pending Gmail cards
    token_for_sweep = get_token()
    sweep_result = sweep_responded_cards(token_for_sweep)
    sweep_count, sweep_ids = sweep_result if isinstance(sweep_result, tuple) else (sweep_result, [])
    if sweep_count:
        print(f"[{datetime.now().strftime('%H:%M')}] Response sweep: resolved {sweep_count} card(s)")
        invalidate_dashboard_cache("gmail")
        # Trigger cross-channel resolution for each resolved card
        for cid in sweep_ids:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:7777/api/cards/{cid}/resolve-related",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception as exc:
                print(f"[{datetime.now().strftime('%H:%M')}] Cross-channel resolve failed for card {cid}: {exc}")
```

**Step 3: Commit**

```bash
git add bin/gmail-poller.py
git commit -m "Add Gmail response sweep to detect user replies in threads"
```

---

## Task 2: Slack Poller — Trigger Cross-Channel Resolution

**Files:**
- Modify: `bin/slack-poller.py:653-690` (write_to_inbox_db)

The Slack poller already detects responses and does ON CONFLICT UPDATE (lines 662-671). We just need to trigger cross-channel resolution when a card is updated to `responded = True`.

**Step 1: Add cross-channel resolution call after DB write**

Modify `write_to_inbox_db()` in `bin/slack-poller.py`. After `conn.commit()` (line 685), add:

```python
        # If this item was responded to, trigger cross-channel resolution
        if changed and item.get("responded"):
            # Get the card ID for the just-upserted row
            row = conn.execute(
                "SELECT id FROM cards WHERE source = 'slack' AND summary = ?",
                (f"{item.get('sender') or 'Someone'} via {item.get('channel') or 'Slack'}: "
                 f"{(item.get('text') or item.get('context_notes') or item.get('draft_response') or '(no preview)')[:200]}",),
            ).fetchone()
            if row:
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"http://127.0.0.1:7777/api/cards/{row[0]}/resolve-related",
                        data=b"{}",
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass  # non-fatal, dashboard may not be running
```

Note: Move `conn.close()` (line 686) to after this block.

**Step 2: Commit**

```bash
git add bin/slack-poller.py
git commit -m "Trigger cross-channel resolution when Slack response detected"
```

---

## Task 3: Server — Cross-Channel Resolution Endpoint

**Files:**
- Modify: `dashboard/server.py` — add new endpoint after `dismiss_card` (~line 4260)

**Step 1: Add person+topic matching helpers**

Add these helpers near the top of server.py (after imports, around line 22):

```python
from difflib import SequenceMatcher
```

Then add the helper functions before the endpoint (around line 4260):

```python
def _extract_person_name(card: dict) -> str:
    """Extract person name from card summary and proposed_actions."""
    summary = card.get("summary", "")
    # Gmail format: "Name <email>: Subject"
    email_match = re.match(r"^(.+?)\s*<[^>]+>", summary)
    if email_match:
        return email_match.group(1).strip()
    # Slack format: "Name via #channel: text"
    slack_match = re.match(r"^(.+?)\s+via\s+", summary)
    if slack_match:
        return slack_match.group(1).strip()
    # Try proposed_actions for sender info
    try:
        actions = json.loads(card.get("proposed_actions") or "[]")
        for a in actions:
            sender = a.get("sender", "") or a.get("to_email", "")
            if sender:
                # Extract name from "Name <email>" format
                name_match = re.match(r"^(.+?)\s*<", sender)
                if name_match:
                    return name_match.group(1).strip()
                # If it's just an email, use the local part
                if "@" in sender:
                    return sender.split("@")[0].replace(".", " ").title()
                return sender
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def _extract_topic_words(card: dict) -> set:
    """Extract meaningful topic words from card summary and context_notes."""
    text = f"{card.get('summary', '')} {card.get('context_notes', '')}"
    # Remove common words, emails, timestamps
    text = re.sub(r"<[^>]+>", " ", text)  # remove emails in angle brackets
    text = re.sub(r"\b\d{1,2}:\d{2}\b", " ", text)  # remove times
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)  # remove dates
    words = set(re.findall(r"[a-zA-Z]{3,}", text.lower()))
    # Remove stop words
    stop = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
            "her", "was", "one", "our", "out", "has", "have", "from", "this", "that",
            "with", "they", "been", "said", "each", "which", "their", "will", "way",
            "about", "many", "then", "them", "would", "like", "into", "just", "than",
            "some", "could", "other", "gmail", "slack", "via", "needs", "response",
            "action", "needed", "noise", "pending", "card"}
    return words - stop


def _person_similarity(name_a: str, name_b: str) -> float:
    """Fuzzy match two person names. Returns 0.0-1.0."""
    if not name_a or not name_b:
        return 0.0
    a = name_a.lower().strip()
    b = name_b.lower().strip()
    if a == b:
        return 1.0
    # Check if one name is contained in the other (e.g., "Jeannette" in "Jeannette Vivas")
    if a in b or b in a:
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def _topic_similarity(words_a: set, words_b: set) -> float:
    """Jaccard similarity on word sets. Returns 0.0-1.0."""
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0
```

**Step 2: Add the resolve-related endpoint**

```python
@app.post("/api/cards/{card_id}/resolve-related")
async def resolve_related_cards(card_id: int):
    """Find and auto-resolve cross-channel cards matching person + topic."""
    conn = get_db()
    try:
        source_row = conn.execute("SELECT * FROM cards WHERE id = ?", [card_id]).fetchone()
        if not source_row:
            raise HTTPException(404, "card not found")
        source_card = _row_to_card(source_row)

        # Only process if the source card is actually responded
        if not source_card.get("responded"):
            return {"resolved": 0, "cards": []}

        source_name = _extract_person_name(source_card)
        source_topics = _extract_topic_words(source_card)
        source_source = source_card.get("source", "")

        if not source_name:
            return {"resolved": 0, "cards": [], "reason": "no person name extracted"}

        # Find candidates: pending cards from OTHER sources
        needs_sections = ("needs-action", "action-needed", "needs-response", "needs_response")
        placeholders = ",".join("?" for _ in needs_sections)
        candidates = conn.execute(
            f"""SELECT * FROM cards
                WHERE source != ?
                  AND responded = 0
                  AND section IN ({placeholders})
                  AND status = 'pending'""",
            [source_source, *needs_sections],
        ).fetchall()

        resolved = []
        affected_sources = set()

        for row in candidates:
            candidate = _row_to_card(row)
            cand_name = _extract_person_name(candidate)
            cand_topics = _extract_topic_words(candidate)

            person_score = _person_similarity(source_name, cand_name)
            topic_score = _topic_similarity(source_topics, cand_topics)

            if person_score >= 0.8 and topic_score >= 0.3:
                existing_notes = candidate.get("context_notes", "") or ""
                new_notes = f"{existing_notes}\nAuto-resolved: responded via {source_source}".strip()
                conn.execute(
                    """UPDATE cards
                       SET responded = 1, section = 'no-action', classification = 'responded',
                           context_notes = ?
                       WHERE id = ?""",
                    [new_notes, candidate["id"]],
                )
                resolved.append({
                    "id": candidate["id"],
                    "source": candidate.get("source"),
                    "summary": candidate.get("summary", "")[:100],
                    "person_score": round(person_score, 2),
                    "topic_score": round(topic_score, 2),
                })
                affected_sources.add(candidate.get("source", ""))

        if resolved:
            conn.commit()
            # Emit SSE invalidation for affected sources
            for src in affected_sources:
                _stale_sources.add(src)

    finally:
        conn.close()

    return {"resolved": len(resolved), "cards": resolved}
```

**Step 3: Add `difflib` import at top of server.py**

Add `from difflib import SequenceMatcher` to the imports (line 1, alongside existing imports).

**Step 4: Commit**

```bash
git add dashboard/server.py
git commit -m "Add cross-channel resolution endpoint with person+topic matching"
```

---

## Task 4: Server — Force Sync Endpoint

**Files:**
- Modify: `dashboard/server.py` — add new endpoint and tracking dict

**Step 1: Add `_running_syncs` tracking dict**

Add near the other module-level state (around line 64):

```python
_running_syncs: dict[str, subprocess.Popen] = {}
```

**Step 2: Add the sync endpoint**

Add after the `/api/cache-invalidate` endpoint (after line 4078):

```python
@app.post("/api/pollers/{poller_id}/sync")
async def force_sync_poller(poller_id: str):
    """Trigger an immediate poller sync."""
    poller = None
    for p in POLLER_DEFINITIONS:
        if p["id"] == poller_id:
            poller = p
            break
    if not poller:
        raise HTTPException(404, f"unknown poller: {poller_id}")

    # Check if already running
    existing = _running_syncs.get(poller_id)
    if existing and existing.poll() is None:
        return {"status": "already_syncing", "poller": poller_id}

    # Build the script path
    script_map = {
        "slack": "slack-poller.py",
        "gmail": "gmail-poller.py",
        "calendar": "calendar-poller.py",
        "jira": "jira-poller.py",
    }
    script_name = script_map.get(poller_id)
    if not script_name:
        raise HTTPException(400, f"no script for poller: {poller_id}")

    script_path = ENG_BUDDY_DIR / "bin" / script_name
    if not script_path.exists():
        # Try runtime path
        script_path = RUNTIME_DIR / "bin" / script_name
    if not script_path.exists():
        raise HTTPException(500, f"poller script not found: {script_name}")

    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ENG_BUDDY_DIR),
    )
    _running_syncs[poller_id] = proc

    return {"status": "syncing", "poller": poller_id}
```

**Step 3: Commit**

```bash
git add dashboard/server.py
git commit -m "Add force-sync endpoint for on-demand poller execution"
```

---

## Task 5: Frontend — Click-to-Sync on Poller Badges

**Files:**
- Modify: `dashboard/static/app.js:292-305` (renderPollerTimers)
- Modify: `dashboard/static/app.js:308-332` (refreshPollerTimers, startPollerTimers)

**Step 1: Add data-poller-id attribute and click handler**

Modify `renderPollerTimers()` in `app.js` (line 292-305). Replace the template literal:

```javascript
function renderPollerTimers() {
  const container = document.getElementById('poller-timers');
  if (!container) return;

  if (!pollerState.pollers.length) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = pollerState.pollers.map((poller) => {
    const countdownSeconds = getPollerCountdownSeconds(poller);
    const countdownLabel = countdownSeconds === null ? '--:--' : formatCountdown(countdownSeconds);
    const lastSeen = poller.last_run_at ? timeAgo(poller.last_run_at) : 'never';
    const health = poller.health || 'unknown';
    const isSyncing = pollerState.syncing && pollerState.syncing[poller.id];
    const badgeClass = isSyncing ? 'syncing' : health;
    const title = isSyncing
      ? 'Syncing now... click to force sync'
      : `Last run ${lastSeen}. Next fire in ${countdownLabel}. Click to sync now.`;
    return `
      <span class="poller-badge ${badgeClass}" title="${escHtml(title)}" data-poller-id="${escHtml(poller.id)}" role="button" style="cursor:pointer">
        <span class="poller-name">${escHtml((poller.label || poller.id || 'poller').toUpperCase())}</span>
        <span class="poller-dot">•</span>
        <span class="poller-countdown">${isSyncing ? '' : escHtml(countdownLabel)}</span>
      </span>
    `;
  }).join('');
}
```

**Step 2: Add syncing state to pollerState and click handler**

Add `syncing: {}` to the `pollerState` object (line 22-27):

```javascript
const pollerState = {
  pollers: [],
  refreshInFlight: false,
  countdownTimerId: null,
  refreshTimerId: null,
  syncing: {},
};
```

Add the click handler function and event delegation. Add after `startPollerTimers()` (after line 332):

```javascript
function initPollerClickToSync() {
  const container = document.getElementById('poller-timers');
  if (!container) return;

  container.addEventListener('click', async (e) => {
    const badge = e.target.closest('.poller-badge[data-poller-id]');
    if (!badge) return;

    const pollerId = badge.dataset.pollerId;
    if (pollerState.syncing[pollerId]) return; // already syncing

    pollerState.syncing[pollerId] = true;
    renderPollerTimers();

    try {
      const r = await fetch(`/api/pollers/${encodeURIComponent(pollerId)}/sync`, { method: 'POST' });
      if (!r.ok) throw new Error('sync failed');
    } catch {
      // If the request fails, clear syncing state
      delete pollerState.syncing[pollerId];
      renderPollerTimers();
      return;
    }

    // Set a timeout fallback to clear syncing state after 60s
    setTimeout(() => {
      if (pollerState.syncing[pollerId]) {
        delete pollerState.syncing[pollerId];
        renderPollerTimers();
      }
    }, 60000);
  });
}
```

**Step 3: Clear syncing state on SSE cache-invalidate**

Find the SSE handler that processes `cache-invalidate` events. In `connectSSE()` or wherever the SSE events are handled, add logic to clear syncing state. Find the `cache-invalidate` event listener and add:

```javascript
// Inside the cache-invalidate handler, after existing logic:
const source = JSON.parse(e.data).source;
if (source && pollerState.syncing[source]) {
  delete pollerState.syncing[source];
  refreshPollerTimers();
}
```

**Step 4: Call `initPollerClickToSync()` during initialization**

Find where `startPollerTimers()` is called during page load and add `initPollerClickToSync()` right after it.

**Step 5: Commit**

```bash
git add dashboard/static/app.js
git commit -m "Add click-to-sync on poller badges with spinner feedback"
```

---

## Task 6: CSS — Syncing Spinner Animation

**Files:**
- Modify: `dashboard/static/style.css:96-143` (poller badge styles)

**Step 1: Add syncing styles**

Add after `.poller-countdown` styles (after line 143):

```css
.poller-badge.syncing {
  border-color: var(--accent);
  color: var(--accent);
  animation: pulse 1.5s ease-in-out infinite;
}

.poller-badge.syncing .poller-name {
  color: inherit;
}

.poller-badge.syncing .poller-countdown {
  display: inline-block;
  width: 12px;
  height: 12px;
  min-width: 12px;
  border: 2px solid var(--border-subtle);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

Note: The `@keyframes pulse` already exists at line 145. The `spin` keyframe is new.

**Step 2: Commit**

```bash
git add dashboard/static/style.css
git commit -m "Add syncing spinner CSS for poller badges"
```

---

## Task 7: Integration Test — Manual Verification

**Step 1: Restart dashboard**

```bash
cd ~/.claude/eng-buddy && ./dashboard/start.sh
```

**Step 2: Test click-to-sync**

Open http://localhost:7777, click a poller badge. Verify:
- Badge shows spinner animation
- Spinner clears when poller finishes (SSE event)
- Tab data refreshes

**Step 3: Test Gmail response detection**

Reply to an email that has a pending Gmail card in the dashboard. Force sync Gmail poller (click the badge). Verify:
- Card moves from "NEEDS ACTION" to "NO ACTION" section
- Card shows "responded" classification

**Step 4: Test cross-channel resolution**

Find a person with cards on both Gmail and Slack. Respond to them on one channel, force sync that poller. Verify:
- Original card resolves to no-action
- Related card on the other channel also resolves
- Context notes show "Auto-resolved: responded via {source}"

**Step 5: Final commit**

```bash
git add -A
git commit -m "Smart response tracking with cross-channel resolution and click-to-sync"
```
