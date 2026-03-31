#!/usr/bin/env python3
"""
eng-buddy Slack Poller
Fetches recent Slack messages directly via the Slack API, writes to inbox.db,
and appends to today's daily log without background model calls.
"""

import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, date, timezone
from pathlib import Path
from poller_runtime import single_instance

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
STATE_FILE = BASE_DIR / "slack-poller-state.json"
DB_PATH = BASE_DIR / "inbox.db"
SETTINGS_FILE = BASE_DIR / "dashboard-settings.json"
WATCHED_THREADS_FILE = BASE_DIR / "watched-threads.json"
LOOKBACK_DAYS = 3
EXCLUDED_CHANNELS = {"critical-broadcast"}
BROADCAST_MARKERS = {"<!here>", "<!channel>", "<!everyone>", "@here", "@channel", "@everyone"}
DASHBOARD_INVALIDATE_URL = "http://127.0.0.1:7777/api/cache-invalidate"


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def invalidate_dashboard_cache(source="slack"):
    payload = json.dumps({"source": source}).encode("utf-8")
    request = urllib.request.Request(
        DASHBOARD_INVALIDATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2):
            return
    except (urllib.error.URLError, TimeoutError, OSError):
        return


# ---------------------------------------------------------------------------
# Daily log helpers (REMOVED — data already flows to inbox.db; daily log
# dumping was causing 8000+ line bloat in daily files)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def macos_notifications_enabled():
    if not SETTINGS_FILE.exists():
        return False
    try:
        settings = json.loads(SETTINGS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return bool(settings.get("macos_notifications", False))


def notify(title, message):
    if not macos_notifications_enabled():
        return
    safe_title = str(title).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    safe_message = str(message).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    banner_script = f'display notification "{safe_message}" with title "{safe_title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", banner_script])

    alert_script = (
        f'display alert "{safe_title}" message "{safe_message}" '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.Popen(["osascript", "-e", alert_script])


# ---------------------------------------------------------------------------
# inbox.db writer
# ---------------------------------------------------------------------------

def _clean_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_timestamp(raw_value):
    value = _clean_text(raw_value)
    if not value:
        return ""

    try:
        if re.fullmatch(r"\d+(\.\d+)?", value):
            return datetime.fromtimestamp(float(value), timezone.utc).isoformat()

        normalized = value.replace(" ", "T") if "T" not in value and " " in value else value
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return ""


def normalize_slack_item(item):
    if not isinstance(item, dict):
        return None

    normalized = {
        "sender": _clean_text(item.get("sender") or item.get("from") or item.get("author") or item.get("user")),
        "channel": _clean_text(item.get("channel") or item.get("channel_name") or item.get("conversation") or item.get("room")),
        "channel_id": _clean_text(item.get("channel_id") or item.get("conversation_id")),
        "text": _clean_text(item.get("text") or item.get("message") or item.get("body") or item.get("summary"))[:400],
        "thread_ts": _clean_text(item.get("thread_ts") or item.get("thread") or item.get("parent_ts")),
        "timestamp": _normalize_timestamp(item.get("timestamp") or item.get("ts") or item.get("message_ts")),
        "section": _clean_text(item.get("section") or "no-action").lower(),
        "classification": _clean_text(item.get("classification") or item.get("label") or "fyi").lower(),
        "draft_response": _clean_text(item.get("draft_response") or item.get("draft") or item.get("reply_draft")) or None,
        "context_notes": _clean_text(item.get("context_notes") or item.get("context") or item.get("notes")) or None,
    }

    responded = item.get("responded")
    if isinstance(responded, str):
        normalized["responded"] = responded.strip().lower() in {"1", "true", "yes", "y"}
    elif responded is None:
        normalized["responded"] = normalized["classification"] == "responded"
    else:
        normalized["responded"] = bool(responded)

    if not any([
        normalized["sender"],
        normalized["channel"],
        normalized["channel_id"],
        normalized["thread_ts"],
        normalized["text"],
    ]):
        return None

    return normalized


def _load_slack_token_config():
    for candidate in [Path.home() / ".claude.json", Path.home() / ".claude" / "settings.json"]:
        if not candidate.exists():
            continue
        try:
            config = json.loads(candidate.read_text())
        except Exception:
            continue

        servers = config.get("mcpServers") or config.get("mcp_servers") or {}
        slack = servers.get("slack") or {}
        env = slack.get("env") or {}
        token = env.get("SLACK_BOT_TOKEN", "").strip()
        team_id = env.get("SLACK_TEAM_ID", "").strip()
        if token and team_id:
            return token, team_id
    return "", ""


def _slack_api(method, token, params=None):
    for attempt in range(4):
        req = urllib.request.Request(
            f"https://slack.com/api/{method}",
            data=urllib.parse.urlencode(params or {}).encode(),
            headers={"Authorization": f"Bearer {token}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                retry_after = int(exc.headers.get("Retry-After", "1"))
                time.sleep(max(1, retry_after))
                continue
            raise

        if payload.get("ok"):
            return payload
        raise RuntimeError(f"{method} failed: {payload}")

    raise RuntimeError(f"{method} failed after retries")


def _message_sender_name(message, resolve_user_name):
    if message.get("user"):
        return resolve_user_name(message.get("user"))
    if message.get("bot_profile", {}).get("name"):
        return _clean_text(message["bot_profile"]["name"])
    if message.get("username"):
        return _clean_text(message.get("username"))
    return ""


def _build_my_mentions(token, me):
    mentions = {f"<@{me}>"}
    try:
        profile = _slack_api("users.info", token, {"user": me}).get("user", {})
        pdata = profile.get("profile", {})
        for value in [profile.get("name"), pdata.get("display_name"), pdata.get("real_name")]:
            clean = _clean_text(value)
            if clean:
                mentions.add(f"@{clean}")
    except Exception:
        pass
    return mentions


def _looks_actionable(text):
    lowered = _clean_text(text).lower()
    return "?" in lowered or any(
        phrase in lowered
        for phrase in [
            "can you",
            "could you",
            "when you have a minute",
            "let me know",
            "need you",
            "where is",
            "what's the status",
            "whats the status",
            "follow up",
        ]
    )


def _classify_participation_item(text, responded):
    if responded:
        return "no-action", "responded", None
    if _looks_actionable(text):
        return "needs-action", "needs-response", None
    return "no-action", "fyi", None


def _mentions_me(text, my_mentions):
    lowered = _clean_text(text).lower()
    if not lowered:
        return False
    return any(_clean_text(marker).lower() in lowered for marker in my_mentions if _clean_text(marker))


def _has_broadcast_marker(text):
    lowered = _clean_text(text).lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in BROADCAST_MARKERS)


def _has_later_self_message(messages, me, message_ts, thread_ts=None):
    for candidate in messages:
        if candidate.get("user") != me:
            continue
        candidate_ts = float(candidate.get("ts", "0") or 0)
        if candidate_ts <= message_ts:
            continue
        if thread_ts is not None:
            candidate_thread_ts = candidate.get("thread_ts") or candidate.get("ts")
            if candidate_thread_ts != thread_ts:
                continue
        return True
    return False


def _candidate_priority(item):
    score = 0
    if item.get("section") == "needs-action":
        score += 4
    if item.get("responded"):
        score += 2
    if item.get("classification") == "responded":
        score += 2
    if item.get("draft_response"):
        score += 1
    if item.get("context_notes"):
        score += 1
    return score


def _fetch_all_conversations(token):
    conversations = []
    cursor = ""
    while True:
        params = {
            "types": "public_channel,private_channel,im,mpim",
            "limit": "200",
            **({"cursor": cursor} if cursor else {}),
        }
        try:
            payload = _slack_api("users.conversations", token, params)
        except Exception:
            payload = _slack_api("conversations.list", token, params)
        conversations.extend(payload.get("channels", []))
        cursor = payload.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.15)
    return conversations


def _fetch_conversation_history(token, channel_id, oldest):
    messages = []
    cursor = ""
    while True:
        payload = _slack_api(
            "conversations.history",
            token,
            {
                "channel": channel_id,
                "oldest": oldest,
                "limit": "200",
                "inclusive": "true",
                **({"cursor": cursor} if cursor else {}),
            },
        )
        batch = payload.get("messages", [])
        messages.extend(batch)
        cursor = payload.get("response_metadata", {}).get("next_cursor", "")
        if not cursor or not batch:
            break
        time.sleep(0.15)
    return messages


def _fetch_thread_replies(token, channel_id, thread_ts, oldest):
    replies = []
    cursor = ""
    while True:
        payload = _slack_api(
            "conversations.replies",
            token,
            {
                "channel": channel_id,
                "ts": thread_ts,
                "oldest": oldest,
                "limit": "200",
                "inclusive": "true",
                **({"cursor": cursor} if cursor else {}),
            },
        )
        batch = payload.get("messages", [])
        replies.extend(batch)
        cursor = payload.get("response_metadata", {}).get("next_cursor", "")
        if not cursor or not batch:
            break
        time.sleep(0.15)
    return replies


def _conversation_updated_seconds(conversation):
    raw_updated = conversation.get("updated")
    if raw_updated not in (None, ""):
        try:
            updated = float(raw_updated)
            if updated > 1_000_000_000_000:
                updated /= 1000.0
            return updated
        except (TypeError, ValueError):
            pass

    latest = conversation.get("latest") or {}
    latest_ts = latest.get("ts")
    if latest_ts:
        try:
            return float(latest_ts)
        except (TypeError, ValueError):
            pass

    try:
        return float(conversation.get("created") or 0)
    except (TypeError, ValueError):
        return 0.0


def _record_candidate(bucket, item):
    key = (item["channel_id"], item["thread_ts"], item["timestamp"], item["text"])
    existing = bucket.get(key)
    if (
        existing is None
        or item["timestamp"] > existing["timestamp"]
        or (
            item["timestamp"] == existing["timestamp"]
            and _candidate_priority(item) > _candidate_priority(existing)
        )
    ):
        bucket[key] = item


def fetch_recent_participation_items(days=LOOKBACK_DAYS):
    token, _team_id = _load_slack_token_config()
    if not token:
        return []

    try:
        me = _slack_api("auth.test", token).get("user_id", "")
        conversations = _fetch_all_conversations(token)
    except Exception as e:
        print(f"Slack direct retrieval unavailable: {e}")
        return []

    oldest = str(time.time() - days * 24 * 3600)
    oldest_float = float(oldest)
    my_mentions = _build_my_mentions(token, me)
    user_cache = {}
    items = {}

    def user_profile(user_id):
        if not user_id:
            return {}
        if user_id not in user_cache:
            user_cache[user_id] = _slack_api("users.info", token, {"user": user_id}).get("user", {})
            time.sleep(0.05)
        return user_cache[user_id]

    def user_name(user_id):
        profile = user_profile(user_id)
        pdata = profile.get("profile", {})
        return (
            pdata.get("real_name")
            or pdata.get("display_name")
            or profile.get("name")
            or user_id
        )

    def is_human_sender(message):
        if message.get("bot_id") or message.get("subtype") == "bot_message" or message.get("bot_profile"):
            return False
        user_id = message.get("user")
        if not user_id:
            return False
        profile = user_profile(user_id)
        return not profile.get("is_bot", False) and not profile.get("is_app_user", False)

    conversations.sort(key=_conversation_updated_seconds, reverse=True)
    recent_conversations = []
    for conv in conversations:
        label = _clean_text(conv.get("name"))
        if label.lower() in EXCLUDED_CHANNELS:
            continue
        if conv.get("is_im"):
            profile = user_profile(conv.get("user"))
            if profile.get("is_bot", False) or profile.get("is_app_user", False):
                continue
        elif not conv.get("is_mpim") and _conversation_updated_seconds(conv) < oldest_float:
            continue
        recent_conversations.append(conv)

    print(f"Scanning {len(recent_conversations)} joined Slack conversation(s) after exclusions...")

    for index, conv in enumerate(recent_conversations, start=1):
        if index % 25 == 0:
            print(f"Scanning Slack conversation {index}/{len(recent_conversations)}...")
        try:
            history = _fetch_conversation_history(token, conv["id"], oldest)
        except Exception as e:
            print(f"Slack history failed for {conv.get('id')}: {e}")
            continue

        history = [m for m in history if m.get("type") == "message" and _clean_text(m.get("text"))]
        if not history:
            continue

        history.sort(key=lambda m: float(m.get("ts", "0") or 0))
        channel_label = user_name(conv.get("user")) if conv.get("is_im") else (_clean_text(conv.get("name")) or conv.get("id"))

        if conv.get("is_im") or conv.get("is_mpim"):
            for message in history:
                message_ts = float(message.get("ts", "0") or 0)
                if message_ts < oldest_float or message.get("user") == me:
                    continue

                message_text = _clean_text(message.get("text"))
                if not message_text:
                    continue

                sender = _message_sender_name(message, user_name)
                if sender.lower() == "jira":
                    continue

                if not (
                    is_human_sender(message)
                    or _mentions_me(message_text, my_mentions)
                    or _has_later_self_message(history, me, message_ts)
                ):
                    continue

                responded = _has_later_self_message(history, me, message_ts)
                section, classification, draft_response = _classify_participation_item(message_text, responded)
                _record_candidate(
                    items,
                    {
                        "sender": sender,
                        "channel": channel_label,
                        "channel_id": conv["id"],
                        "text": message_text[:400],
                        "thread_ts": message.get("thread_ts") or message.get("ts"),
                        "timestamp": datetime.fromtimestamp(message_ts, timezone.utc).isoformat(),
                        "section": section,
                        "classification": classification,
                        "draft_response": draft_response,
                        "context_notes": "Recent direct message" if not responded else "Recent direct message you already responded to",
                        "responded": responded,
                    },
                )

        for message in history:
            if float(message.get("ts", "0") or 0) < oldest_float:
                continue
            if message.get("user") == me:
                continue

            message_text = _clean_text(message.get("text"))
            if not message_text:
                continue

            sender = _message_sender_name(message, user_name)
            if sender.lower() == "jira":
                continue

            mentions_me = _mentions_me(message_text, my_mentions)
            if mentions_me and not _has_broadcast_marker(message_text):
                section, classification, draft_response = _classify_participation_item(message_text, False)
                _record_candidate(
                    items,
                    {
                        "sender": sender,
                        "channel": channel_label,
                        "channel_id": conv["id"],
                        "text": message_text[:400],
                        "thread_ts": message.get("thread_ts") or message.get("ts"),
                        "timestamp": datetime.fromtimestamp(float(message["ts"]), timezone.utc).isoformat(),
                        "section": section,
                        "classification": classification,
                        "draft_response": draft_response,
                        "context_notes": "Recent mention in Slack",
                        "responded": False,
                    },
                )

            is_thread_root = message.get("reply_count") or message.get("thread_ts") == message.get("ts")
            if not is_thread_root:
                continue

            thread_ts = message.get("thread_ts") or message.get("ts")
            try:
                replies = _fetch_thread_replies(token, conv["id"], thread_ts, oldest)
            except Exception as e:
                print(f"Slack thread fetch failed for {conv.get('id')}:{thread_ts}: {e}")
                continue
            replies = [reply for reply in replies if reply.get("type") == "message" and _clean_text(reply.get("text"))]
            if not replies:
                continue
            replies.sort(key=lambda reply: float(reply.get("ts", "0") or 0))

            reply_users = {user for user in message.get("reply_users", []) if user}
            participated = message.get("user") == me or me in reply_users or any(reply.get("user") == me for reply in replies)
            if not participated:
                continue

            for reply in replies:
                reply_ts = float(reply.get("ts", "0") or 0)
                if reply_ts < oldest_float or reply.get("user") == me:
                    continue

                sender = _message_sender_name(reply, user_name)
                if sender.lower() == "jira":
                    continue

                responded = _has_later_self_message(replies, me, reply_ts, thread_ts=thread_ts)
                section, classification, draft_response = _classify_participation_item(reply.get("text"), responded)
                _record_candidate(
                    items,
                    {
                        "sender": sender,
                        "channel": channel_label,
                        "channel_id": conv["id"],
                        "text": _clean_text(reply.get("text"))[:400],
                        "thread_ts": thread_ts,
                        "timestamp": datetime.fromtimestamp(reply_ts, timezone.utc).isoformat(),
                        "section": section,
                        "classification": classification,
                        "draft_response": draft_response,
                        "context_notes": "Message in a thread you participated in",
                        "responded": responded,
                    },
                )

        # Slack's history API gets flaky if we hammer conversation reads too quickly.
        time.sleep(0.05)

    return sorted(items.values(), key=lambda item: item["timestamp"], reverse=True)

def write_to_inbox_db(item):
    """Write a classified Slack message card to inbox.db."""
    if not DB_PATH.exists():
        return False

    proposed_actions = json.dumps([{
        "type": "send_slack_reply",
        "channel_id": item.get("channel_id", ""),
        "thread_ts": item.get("thread_ts", ""),
        "draft": item.get("draft_response") or "",
        "source": "slack",
        "sender": item.get("sender", ""),
        "channel_label": item.get("channel", ""),
    }])

    try:
        conn = sqlite3.connect(DB_PATH)
        before = conn.total_changes
        cursor = conn.execute(
            """INSERT INTO cards
               (source, timestamp, summary, classification, status,
                proposed_actions, execution_status,
                section, draft_response, context_notes, responded)
               VALUES ('slack', ?, ?, ?, 'pending', ?, 'not_run', ?, ?, ?, ?)
               ON CONFLICT(source, summary) DO UPDATE SET
                   timestamp=excluded.timestamp,
                   classification=excluded.classification,
                   status='pending',
                   proposed_actions=excluded.proposed_actions,
                   execution_status='not_run',
                   section=excluded.section,
                   draft_response=excluded.draft_response,
                   context_notes=excluded.context_notes,
                   responded=excluded.responded
               WHERE cards.responded = 0 OR excluded.responded = 1
               RETURNING id""",
            (
                item.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                f"{item.get('sender') or 'Someone'} via {item.get('channel') or 'Slack'}: "
                f"{(item.get('text') or item.get('context_notes') or item.get('draft_response') or '(no preview)')[:200]}",
                item.get("classification", "fyi"),
                proposed_actions,
                item.get("section", "no-action"),
                item.get("draft_response"),
                item.get("context_notes"),
                1 if item.get("responded") else 0,
            ),
        )
        row = cursor.fetchone()
        card_id = row[0] if row else None
        changed = conn.total_changes > before
        conn.commit()

        # If this item was responded to, trigger cross-channel resolution
        if changed and item.get("responded") and card_id:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:7777/api/cards/{card_id}/resolve-related",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass  # non-fatal, dashboard may not be running

        conn.close()
        return changed
    except sqlite3.OperationalError as e:
        print(f"DB write error (non-fatal): {e}")
        return False


# ---------------------------------------------------------------------------
# Watched threads registry
# ---------------------------------------------------------------------------

def load_watched_threads():
    """Load watched threads from file. Returns list of dicts with channel_id, thread_ts, label."""
    if not WATCHED_THREADS_FILE.exists():
        return []
    try:
        return json.loads(WATCHED_THREADS_FILE.read_text())
    except Exception:
        return []


def save_watched_threads(threads):
    WATCHED_THREADS_FILE.write_text(json.dumps(threads, indent=2))


def register_watched_thread(channel_id, thread_ts, label=""):
    """Add a thread to the watch registry. Idempotent."""
    threads = load_watched_threads()
    for t in threads:
        if t.get("channel_id") == channel_id and t.get("thread_ts") == thread_ts:
            return  # already watching
    threads.append({
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "label": label,
        "added": datetime.now(timezone.utc).isoformat(),
    })
    save_watched_threads(threads)
    print(f"Watching thread {thread_ts} in {channel_id} ({label})")


def fetch_watched_thread_replies(days=LOOKBACK_DAYS):
    """
    Poll all watched threads directly via conversations.replies,
    regardless of channel membership. Returns normalized items.
    """
    watched = load_watched_threads()
    if not watched:
        return []

    token, _ = _load_slack_token_config()
    if not token:
        return []

    try:
        me = _slack_api("auth.test", token).get("user_id", "")
    except Exception as e:
        print(f"Watched thread auth failed: {e}")
        return []

    oldest = str(time.time() - days * 24 * 3600)
    oldest_float = float(oldest)
    user_cache = {}
    items = {}

    def user_name(user_id):
        if not user_id:
            return user_id
        if user_id not in user_cache:
            try:
                user_cache[user_id] = _slack_api("users.info", token, {"user": user_id}).get("user", {})
                time.sleep(0.05)
            except Exception:
                user_cache[user_id] = {}
        profile = user_cache[user_id]
        pdata = profile.get("profile", {})
        return pdata.get("real_name") or pdata.get("display_name") or profile.get("name") or user_id

    for watched_thread in watched:
        channel_id = watched_thread.get("channel_id", "")
        thread_ts = watched_thread.get("thread_ts", "")
        label = watched_thread.get("label", channel_id)
        if not channel_id or not thread_ts:
            continue

        try:
            replies = _fetch_thread_replies(token, channel_id, thread_ts, oldest)
        except Exception as e:
            print(f"Watched thread fetch failed for {channel_id}:{thread_ts}: {e}")
            continue

        replies = [r for r in replies if r.get("type") == "message" and _clean_text(r.get("text")) and r.get("user") != me]
        for reply in replies:
            reply_ts = float(reply.get("ts", "0") or 0)
            if reply_ts < oldest_float:
                continue
            sender = user_name(reply.get("user", ""))
            reply_text = _clean_text(reply.get("text", ""))[:400]
            responded = _has_later_self_message(replies, me, reply_ts, thread_ts=thread_ts)
            section, classification, draft_response = _classify_participation_item(reply_text, responded)
            _record_candidate(
                items,
                {
                    "sender": sender,
                    "channel": label,
                    "channel_id": channel_id,
                    "text": reply_text,
                    "thread_ts": thread_ts,
                    "timestamp": datetime.fromtimestamp(reply_ts, timezone.utc).isoformat(),
                    "section": section,
                    "classification": classification,
                    "draft_response": draft_response,
                    "context_notes": f"Reply in watched thread: {label}",
                    "responded": responded,
                },
            )

    return list(items.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        with single_instance("slack-poller"):
            state = load_state()
            now = datetime.now()

            print(f"[{now.strftime('%H:%M')}] Fetching Slack participation from the last {LOOKBACK_DAYS} day(s)...")
            messages = fetch_recent_participation_items(days=LOOKBACK_DAYS)

            watched_replies = fetch_watched_thread_replies(days=LOOKBACK_DAYS)
            if watched_replies:
                print(f"[{now.strftime('%H:%M')}] Found {len(watched_replies)} reply/replies in watched thread(s)")
                seen_keys = {(m.get("channel_id"), m.get("thread_ts"), m.get("timestamp"), m.get("text")) for m in messages}
                for item in watched_replies:
                    key = (item.get("channel_id"), item.get("thread_ts"), item.get("timestamp"), item.get("text"))
                    if key not in seen_keys:
                        messages.append(item)
                        seen_keys.add(key)

            if not messages:
                print(f"[{now.strftime('%H:%M')}] No new messages needing attention")
                state["last_check"] = str(now.timestamp())
                save_state(state)
                return

            print(f"[{now.strftime('%H:%M')}] Processing {len(messages)} message(s)...")

            needs_action_items = []
            dashboard_changed = False

            for item in messages:
                if write_to_inbox_db(item):
                    dashboard_changed = True
                if item.get("section") == "needs-action" and not item.get("responded"):
                    needs_action_items.append(item)

            print(f"[{now.strftime('%H:%M')}] Ingested {len(messages)} message(s) to inbox.db")

            for item in needs_action_items:
                preview = (item.get("text", ""))[:80]
                notify(
                    title=f"eng-buddy: {item.get('classification', 'message')} from {item.get('sender', '?')}",
                    message=f"{item.get('channel', '')}\n{preview}",
                )

            print(
                f"[{now.strftime('%H:%M')}] "
                f"{len(needs_action_items)} needs-action item(s) written to inbox.db"
            )

            state["last_check"] = str(now.timestamp())
            save_state(state)

            if dashboard_changed:
                invalidate_dashboard_cache("slack")
    except RuntimeError as exc:
        print(f"[{datetime.now().strftime('%H:%M')}] {exc}")


if __name__ == "__main__":
    main()
