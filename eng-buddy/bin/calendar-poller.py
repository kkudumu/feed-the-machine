#!/usr/bin/env python3
"""
eng-buddy Calendar Poller
Fetches weekly events directly from the Google Calendar API and writes them
to inbox.db without using Claude in the background.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from poller_runtime import single_instance

BASE_DIR = Path.home() / ".claude" / "eng-buddy"
DB_PATH = BASE_DIR / "inbox.db"
STATE_FILE = BASE_DIR / "calendar-poller-state.json"
TOKENS_FILE = Path.home() / ".config" / "google-calendar-mcp" / "tokens.json"
GOOGLE_OAUTH_FILE = Path.home() / ".claude" / "google-oauth-credentials.json"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def compute_fetch_window(today=None):
    today = today or date.today()
    if today.weekday() == 6:
        end_date = today + timedelta(days=7)
    else:
        end_date = today + timedelta(days=(6 - today.weekday()))
    return today, end_date


def _load_calendar_account() -> tuple[dict, dict]:
    tokens = json.loads(TOKENS_FILE.read_text())
    creds = json.loads(GOOGLE_OAUTH_FILE.read_text())
    account = tokens.get("primary") or {}
    return account, creds.get("installed") or {}


def _refresh_access_token(account: dict, client: dict) -> dict:
    payload = urllib.parse.urlencode(
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": account["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        refreshed = json.loads(response.read())

    account["access_token"] = refreshed["access_token"]
    account["expiry_date"] = int(time.time() * 1000) + refreshed.get("expires_in", 3600) * 1000
    tokens = json.loads(TOKENS_FILE.read_text())
    tokens["primary"] = account
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    return account


def _get_access_token() -> str:
    account, client = _load_calendar_account()
    expiry = int(account.get("expiry_date") or 0)
    if int(time.time() * 1000) >= expiry - 60_000:
        account = _refresh_access_token(account, client)
    return account["access_token"]


def _calendar_get(path: str, params: dict[str, str]) -> dict:
    token = _get_access_token()
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{CALENDAR_API}{path}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _extract_join_link(event: dict) -> str:
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    conference = event.get("conferenceData") or {}
    for entry in conference.get("entryPoints", []):
        uri = str(entry.get("uri") or "").strip()
        if uri:
            return uri
    return ""


def _event_context_notes(event: dict) -> str | None:
    notes = []
    attendee_count = len(event.get("attendees") or [])
    if attendee_count:
        notes.append(f"{attendee_count} attendee(s)")
    if event.get("location"):
        notes.append(f"Location: {event['location']}")
    if event.get("hangout_link"):
        notes.append("Has meeting link")
    return " | ".join(notes) if notes else None


def _event_prep_needed(event: dict) -> bool:
    title = str(event.get("summary") or "").lower()
    attendees = event.get("attendees") or []
    if "all day" in title:
        return False
    if any(keyword in title for keyword in ("interview", "planning", "review", "retro", "1:1", "sync")):
        return True
    return len(attendees) >= 2


def _event_priority(event: dict) -> str:
    if _event_prep_needed(event):
        title = str(event.get("summary") or "").lower()
        if any(keyword in title for keyword in ("interview", "planning", "review", "incident", "customer")):
            return "high"
        return "normal"
    return "low"


def _build_single_day_prompt(_target_date):
    return ""


def _fetch_events_for_date(target_date):
    start_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    payload = _calendar_get(
        "/calendars/primary/events",
        {
            "timeMin": start_dt.isoformat().replace("+00:00", "Z"),
            "timeMax": end_dt.isoformat().replace("+00:00", "Z"),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": "250",
        },
    )

    events = []
    for item in payload.get("items", []):
        start = (item.get("start") or {}).get("dateTime") or (item.get("start") or {}).get("date") or ""
        end = (item.get("end") or {}).get("dateTime") or (item.get("end") or {}).get("date") or ""
        description = str(item.get("description") or "").strip()
        attendees = []
        for attendee in item.get("attendees") or []:
            email = str(attendee.get("email") or "").strip()
            if email:
                attendees.append(email)

        event = {
            "id": item.get("id", ""),
            "summary": item.get("summary", ""),
            "start": start,
            "end": end,
            "location": item.get("location", ""),
            "hangout_link": _extract_join_link(item),
            "attendees": attendees,
            "description": description[:200],
        }
        event["prep_needed"] = _event_prep_needed(event)
        event["priority"] = _event_priority(event)
        event["context_notes"] = _event_context_notes(event)
        events.append(event)
    return events


def _dedupe_events(events):
    seen = set()
    deduped = []
    for event in events:
        key = (event.get("id"), event.get("start"), event.get("end"), event.get("summary"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def format_event_summary(event):
    raw_start = str(event.get("start", "")).strip()
    title = (event.get("summary") or "No title").strip()

    if raw_start:
        try:
            if "T" in raw_start:
                start_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
                label = start_dt.strftime("%a %m/%d %H:%M")
            else:
                start_day = datetime.strptime(raw_start, "%Y-%m-%d")
                label = f"{start_day.strftime('%a %m/%d')} ALL DAY"
            return f"{label} — {title}"
        except ValueError:
            pass

    return title


def fetch_events():
    start_date, end_date = compute_fetch_window()
    current_date = start_date
    events = []
    while current_date <= end_date:
        try:
            events.extend(_fetch_events_for_date(current_date))
        except Exception as exc:
            print(
                f"[{datetime.now().strftime('%H:%M')}] Calendar fetch failed for "
                f"{current_date.isoformat()}: {exc}"
            )
        current_date += timedelta(days=1)

    return _dedupe_events(events)


def enrich_events(events):
    return events


def write_to_db(events):
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM cards WHERE source = 'calendar'")
        for event in events:
            event_start = event.get("start") or datetime.now(timezone.utc).isoformat()
            summary = format_event_summary(event)
            section = "needs-action" if event.get("prep_needed") else "no-action"
            proposed = json.dumps(
                [
                    {
                        "type": "calendar_event",
                        "id": event.get("id", ""),
                        "summary": event.get("summary", ""),
                        "start": event.get("start", ""),
                        "end": event.get("end", ""),
                        "hangout_link": event.get("hangout_link", ""),
                        "attendees": event.get("attendees", []),
                    }
                ]
            )
            conn.execute(
                """INSERT OR IGNORE INTO cards
                   (source, timestamp, summary, classification, status,
                    proposed_actions, execution_status, section, context_notes)
                   VALUES ('calendar', ?, ?, ?, 'pending', ?, 'not_run', ?, ?)""",
                (
                    event_start,
                    summary,
                    event.get("priority", "normal"),
                    proposed,
                    section,
                    event.get("context_notes", ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def main():
    try:
        with single_instance("calendar-poller"):
            state = load_state()
            now = datetime.now()
            last_fetch = state.get("last_fetch", "")
            current_slot = now.strftime("%Y-%m-%d-%H") + ("-00" if now.minute < 30 else "-30")
            if last_fetch == current_slot:
                print(f"[{now.strftime('%H:%M')}] Already fetched this slot, skipping")
                return

            print(f"[{now.strftime('%H:%M')}] Fetching calendar events...")
            events = fetch_events()

            if events:
                write_to_db(events)
                print(f"[{now.strftime('%H:%M')}] Wrote {len(events)} calendar cards to inbox.db")
            else:
                print(f"[{now.strftime('%H:%M')}] No events found in the current weekly horizon")

            state["last_fetch"] = current_slot
            save_state(state)
    except RuntimeError as exc:
        print(f"[{datetime.now().strftime('%H:%M')}] {exc}")


if __name__ == "__main__":
    main()
