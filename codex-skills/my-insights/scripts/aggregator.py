"""
aggregator.py

Aggregates session-meta dicts and facet dicts into a single report-ready
data structure for the report renderer.
"""

from __future__ import annotations

import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_label(snake: str) -> str:
    """Convert snake_case string to Title Case display label."""
    return " ".join(word.capitalize() for word in snake.replace("-", "_").split("_"))


def _counter_to_list(
    counter: Counter,
    limit: int | None = None,
    label_transform: bool = True,
) -> list[dict]:
    """
    Convert a Counter to a sorted list of {"label": str, "count": int} dicts.

    Args:
        counter: A collections.Counter instance.
        limit: If given, return only the top N items.
        label_transform: If True, apply snake_case → Title Case conversion.

    Returns:
        List sorted descending by count.
    """
    items = counter.most_common(limit)
    result = []
    for key, count in items:
        label = _to_label(str(key)) if label_transform else str(key)
        result.append({"label": label, "count": count})
    return result


def _parse_dt(raw: str) -> datetime | None:
    """Parse an ISO-8601 datetime string (with optional 'Z') into a datetime."""
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Project area helpers
# ---------------------------------------------------------------------------

def _normalize_project_path(path: str) -> str:
    """
    Normalise a project_path to a canonical project identifier.

    Strategy:
    - Strip trailing slashes.
    - If the last component looks like a branch name (contains '/' after the
      repo root, or matches typical worktree patterns), strip it.
    - Return the last 2 path components as the display name.

    We treat the last directory component as a potential branch/worktree name
    when it contains no file extension and the parent directory name itself
    looks like a project (i.e. the grandparent is not the home dir's direct
    parent structure).
    """
    path = path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    if not parts:
        return path

    # Heuristic: if the last component looks like a worktree slug
    # (contains hyphens like a branch name, e.g. "klaviyokio/enthusiastic-cadet")
    # keep it as-is because it IS the project context.
    # We just use the last 2-3 parts for grouping.
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return parts[-1]


def _build_project_areas(sessions: list[dict]) -> list[dict]:
    """
    Group sessions by project_path, count occurrences, and return the top 5.
    """
    path_sessions: dict[str, list[dict]] = defaultdict(list)

    for session in sessions:
        raw_path: str = session.get("project_path") or ""
        key = _normalize_project_path(raw_path) if raw_path else "Unknown"
        path_sessions[key].append(session)

    # Build area entries
    areas: list[dict] = []
    for name, sess_list in path_sessions.items():
        count = len(sess_list)

        # Collect tools and languages used in these sessions for description seed
        tool_counter: Counter = Counter()
        lang_counter: Counter = Counter()
        for s in sess_list:
            tool_counter.update(s.get("tool_counts") or {})
            lang_counter.update(s.get("languages") or {})

        top_tools = [t for t, _ in tool_counter.most_common(3)]
        top_langs = [l for l, _ in lang_counter.most_common(3)]

        parts = []
        if top_langs:
            parts.append(", ".join(top_langs))
        if top_tools:
            parts.append(f"tools: {', '.join(top_tools)}")

        if parts:
            description = f"{count} sessions across {'; '.join(parts)}"
        else:
            description = f"{count} sessions"

        areas.append({"name": name, "count": count, "description": description})

    # Sort descending by count, take top 5
    areas.sort(key=lambda a: a["count"], reverse=True)
    return areas[:5]


# ---------------------------------------------------------------------------
# Response time helpers
# ---------------------------------------------------------------------------

_RT_BUCKETS: list[tuple[str, float, float]] = [
    ("2-10s",  2.0,   10.0),
    ("10-30s", 10.0,  30.0),
    ("30s-1m", 30.0,  60.0),
    ("1-2m",   60.0,  120.0),
    ("2-5m",   120.0, 300.0),
    ("5-15m",  300.0, 900.0),
    (">15m",   900.0, float("inf")),
]


def _bucket_response_times(all_times: list[float]) -> list[dict]:
    """
    Bucket a flat list of response times (in seconds) into labelled bins.
    Filters out values < 2s (automated / near-instant).
    """
    filtered = [t for t in all_times if t >= 2.0]
    bucket_counts: dict[str, int] = {label: 0 for label, _, _ in _RT_BUCKETS}

    for t in filtered:
        for label, lo, hi in _RT_BUCKETS:
            if lo <= t < hi:
                bucket_counts[label] += 1
                break

    return [
        {"label": label, "count": bucket_counts[label]}
        for label, _, _ in _RT_BUCKETS
        if bucket_counts[label] > 0
    ]


# ---------------------------------------------------------------------------
# Multi-clauding helpers
# ---------------------------------------------------------------------------

def _compute_multi_clauding(sessions: list[dict], total_messages: int) -> dict:
    """
    Detect sessions that were running in parallel (multi-clauding).

    Returns:
        {
            "overlap_events": int,
            "sessions_involved": int,
            "pct_messages": float,
        }
    """
    if not sessions:
        return {"overlap_events": 0, "sessions_involved": 0, "pct_messages": 0.0}

    # Build (start_ts, end_ts, msg_count) tuples
    windows: list[tuple[float, float, int]] = []
    for s in sessions:
        start_dt = _parse_dt(s.get("start_time") or "")
        if start_dt is None:
            continue
        start_ts = start_dt.timestamp()
        duration_mins: float = float(s.get("duration_minutes") or 0)
        end_ts = start_ts + duration_mins * 60
        msg_count = (s.get("user_message_count") or 0) + (s.get("assistant_message_count") or 0)
        windows.append((start_ts, end_ts, msg_count))

    if not windows:
        return {"overlap_events": 0, "sessions_involved": 0, "pct_messages": 0.0}

    # Sort by start time
    windows.sort(key=lambda w: w[0])

    overlap_events = 0
    involved_indices: set[int] = set()
    overlapping_messages = 0

    for i in range(len(windows)):
        for j in range(i + 1, len(windows)):
            start_j, end_j, msgs_j = windows[j]
            start_i, end_i, msgs_i = windows[i]

            # j starts before i ends → overlap
            if start_j < end_i:
                overlap_events += 1
                involved_indices.add(i)
                involved_indices.add(j)
                overlapping_messages += msgs_j  # count the overlapping session's msgs
            else:
                # windows are sorted, no further j can overlap with i
                break

    sessions_involved = len(involved_indices)
    pct_messages = (
        (overlapping_messages / total_messages * 100.0) if total_messages > 0 else 0.0
    )

    return {
        "overlap_events": overlap_events,
        "sessions_involved": sessions_involved,
        "pct_messages": round(pct_messages, 1),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate(sessions: list[dict], facets: list[dict]) -> dict:
    """
    Aggregate session-meta and facets into report-ready data structure.

    Args:
        sessions: List of session-meta dicts (from session_reader).
        facets:   List of facet dicts (from facet_generator).

    Returns:
        dict with all data for the report renderer.
    """
    # ── Scalar aggregations from sessions ────────────────────────────────────
    total_messages = 0
    total_lines_added = 0
    total_lines_removed = 0
    total_files_modified = 0
    total_commits = 0

    unique_dates: set[str] = set()
    all_response_times: list[float] = []
    hour_counts: Counter = Counter()
    tool_counter: Counter = Counter()
    lang_counter: Counter = Counter()
    tool_error_counter: Counter = Counter()

    for s in sessions:
        user_msgs = int(s.get("user_message_count") or 0)
        asst_msgs = int(s.get("assistant_message_count") or 0)
        total_messages += user_msgs + asst_msgs
        total_lines_added   += int(s.get("lines_added") or 0)
        total_lines_removed += int(s.get("lines_removed") or 0)
        total_files_modified += int(s.get("files_modified") or 0)
        total_commits += int(s.get("git_commits") or 0)

        # Active days (unique dates from start_time)
        start_raw = s.get("start_time") or ""
        if start_raw:
            dt = _parse_dt(start_raw)
            if dt is not None:
                unique_dates.add(dt.date().isoformat())

        # Tool counts
        tool_counter.update(s.get("tool_counts") or {})

        # Languages
        lang_counter.update(s.get("languages") or {})

        # Response times
        rt_list = s.get("user_response_times") or []
        if isinstance(rt_list, list):
            all_response_times.extend(float(t) for t in rt_list if t is not None)

        # Tool error categories
        tool_error_counter.update(s.get("tool_error_categories") or {})

        # Hour counts — prefer message_hours list, fall back to start_time hour
        msg_hours = s.get("message_hours")
        if isinstance(msg_hours, list) and msg_hours:
            for h in msg_hours:
                try:
                    hour_counts[int(h)] += 1
                except (ValueError, TypeError):
                    pass
        elif start_raw:
            dt = _parse_dt(start_raw)
            if dt is not None:
                hour_counts[dt.hour] += 1

    active_days = len(unique_dates)
    msgs_per_day = (total_messages / active_days) if active_days > 0 else 0.0

    # ── Facet aggregations ────────────────────────────────────────────────────
    goal_counter: Counter = Counter()
    session_type_counter: Counter = Counter()
    friction_counter: Counter = Counter()
    satisfaction_counter: Counter = Counter()
    outcome_counter: Counter = Counter()
    primary_success_counter: Counter = Counter()
    helpfulness_counter: Counter = Counter()

    for f in facets:
        # goal_categories — dict like {"feature_implementation": 1}
        gc = f.get("goal_categories") or {}
        if isinstance(gc, dict):
            goal_counter.update(gc)

        # session_type — single string value
        st = f.get("session_type") or ""
        if st:
            session_type_counter[str(st)] += 1

        # friction_counts — dict
        fc = f.get("friction_counts") or {}
        if isinstance(fc, dict):
            friction_counter.update(fc)

        # user_satisfaction_counts — dict
        usc = f.get("user_satisfaction_counts") or {}
        if isinstance(usc, dict):
            satisfaction_counter.update(usc)

        # outcome — single string
        oc = f.get("outcome") or ""
        if oc:
            outcome_counter[str(oc)] += 1

        # primary_success — single string
        ps = f.get("primary_success") or ""
        if ps:
            primary_success_counter[str(ps)] += 1

        # claude_helpfulness — single string
        ch = f.get("claude_helpfulness") or ""
        if ch:
            helpfulness_counter[str(ch)] += 1

    # ── Response time stats ───────────────────────────────────────────────────
    filtered_rt = [t for t in all_response_times if t >= 2.0]
    response_time_median = (
        statistics.median(filtered_rt) if filtered_rt else 0.0
    )
    response_time_avg = (
        sum(filtered_rt) / len(filtered_rt) if filtered_rt else 0.0
    )

    # ── Hour counts dict {0..23} ──────────────────────────────────────────────
    hour_counts_dict: dict[int, int] = {h: 0 for h in range(24)}
    for h, cnt in hour_counts.items():
        try:
            hour_counts_dict[int(h)] = int(cnt)
        except (ValueError, TypeError):
            pass

    # ── Multi-clauding ────────────────────────────────────────────────────────
    multi_clauding = _compute_multi_clauding(sessions, total_messages)

    # ── Build and return final dict ───────────────────────────────────────────
    return {
        "total_sessions":      len(sessions),
        "total_messages":      total_messages,
        "total_lines_added":   total_lines_added,
        "total_lines_removed": total_lines_removed,
        "total_files_modified": total_files_modified,
        "active_days":         active_days,
        "msgs_per_day":        round(msgs_per_day, 1),
        "total_commits":       total_commits,

        "project_areas": _build_project_areas(sessions),

        "goal_categories": _counter_to_list(goal_counter),
        "top_tools":       _counter_to_list(tool_counter, limit=6, label_transform=False),
        "languages":       _counter_to_list(lang_counter, limit=6, label_transform=False),
        "session_types":   _counter_to_list(session_type_counter),
        "friction_types":  _counter_to_list(friction_counter),
        "satisfaction":    _counter_to_list(satisfaction_counter),
        "outcomes":        _counter_to_list(outcome_counter),
        "primary_success": _counter_to_list(primary_success_counter),
        "helpfulness":     _counter_to_list(helpfulness_counter),

        "response_times":        _bucket_response_times(all_response_times),
        "response_time_median":  round(response_time_median, 1),
        "response_time_avg":     round(response_time_avg, 1),

        "multi_clauding": multi_clauding,

        "hour_counts": hour_counts_dict,

        "tool_errors": _counter_to_list(tool_error_counter),
    }
