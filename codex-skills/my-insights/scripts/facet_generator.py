"""
facet_generator.py

Generates insight facets for Codex sessions by calling `codex exec`
in batches of 10. Caches results to ~/.codex/usage-data/facets/{session_id}.json.
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

FACETS_DIR = Path.home() / ".codex" / "usage-data" / "facets"
BATCH_SIZE = 10
FIRST_PROMPT_MAX_CHARS = 500

PROMPT_TEMPLATE = """\
You are analyzing Codex session metadata to generate insight facets. For each session below, produce a JSON facet object.

Inference guidelines:
- git_commits > 0 suggests goal was likely achieved
- High tool_errors suggests friction
- duration_minutes + user_message_count indicate session depth
- first_prompt reveals the user's intent
- tool_counts reveal what Codex was used for (Bash = CLI ops, Edit/Write = code changes, Read = exploration)
- lines_added/removed > 0 means code was modified
- If first_prompt is very short or generic, the session was likely a quick question or exploration

Return ONLY a JSON array of facet objects, one per session. No markdown, no explanation.

Sessions:
{sessions_json}

Required facet format per session:
{{
    "underlying_goal": "string",
    "goal_categories": {{"category": 1}},
    "outcome": "fully_achieved|mostly_achieved|partially_achieved|not_achieved|abandoned",
    "user_satisfaction_counts": {{"level": count}},
    "claude_helpfulness": "essential|very_helpful|somewhat_helpful|minimal|unhelpful",
    "session_type": "single_task|multi_task|iterative_refinement|exploration|quick_question",
    "friction_counts": {{"type": count}},
    "friction_detail": "string or empty",
    "primary_success": "string or empty",
    "brief_summary": "string",
    "session_id": "from session"
}}"""


def _ensure_facets_dir() -> None:
    """Create the facets cache directory if it doesn't exist."""
    FACETS_DIR.mkdir(parents=True, exist_ok=True)


def _load_cached_facet(session_id: str) -> Optional[dict]:
    """Return a cached facet dict if it exists, otherwise None."""
    path = FACETS_DIR / f"{session_id}.json"
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cached facet %s: %s", session_id, exc)
    return None


def _write_facet(facet: dict) -> None:
    """Persist a single facet to the cache directory."""
    session_id = facet.get("session_id", "unknown")
    path = FACETS_DIR / f"{session_id}.json"
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(facet, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error("Failed to write facet %s: %s", session_id, exc)


def _prepare_session_for_prompt(session: dict) -> dict:
    """Return a copy of the session with first_prompt truncated to save tokens."""
    prepared = dict(session)
    if isinstance(prepared.get("first_prompt"), str):
        prepared["first_prompt"] = prepared["first_prompt"][:FIRST_PROMPT_MAX_CHARS]
    return prepared


def _build_prompt(sessions: list[dict]) -> str:
    """Construct the prompt string for a batch of sessions."""
    prepared = [_prepare_session_for_prompt(s) for s in sessions]
    sessions_json = json.dumps(prepared, indent=2, ensure_ascii=False)
    return PROMPT_TEMPLATE.format(sessions_json=sessions_json)


def _call_cli_with_retry(prompt: str) -> Optional[str]:
    """Call codex exec once, retrying once on failure. Returns raw text or None."""
    for attempt in range(2):
        try:
            result = subprocess.run(
                ["codex", "exec", prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                msg = result.stderr.strip() or f"exit code {result.returncode}"
                if attempt == 0:
                    logger.warning("Codex CLI call failed (attempt 1), retrying: %s", msg)
                else:
                    logger.error("Codex CLI call failed (attempt 2), skipping batch: %s", msg)
        except subprocess.TimeoutExpired:
            if attempt == 0:
                logger.warning("Codex CLI call timed out (attempt 1), retrying")
            else:
                logger.error("Codex CLI call timed out (attempt 2), skipping batch")
        except Exception as exc:
            if attempt == 0:
                logger.warning("CLI call error (attempt 1), retrying: %s", exc)
            else:
                logger.error("CLI call error (attempt 2), skipping batch: %s", exc)
    return None


def _parse_facets_from_response(
    raw_text: str, expected_session_ids: list[str]
) -> tuple[list[dict], list[str]]:
    """
    Parse the JSON array from the CLI response text.

    Returns:
        (facets, missing_session_ids) where missing_session_ids are those the
        model did not return a facet for.
    """
    # Strip potential markdown code fences
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error from Codex CLI response: %s", exc)
        return [], expected_session_ids

    if not isinstance(parsed, list):
        logger.error("Expected JSON array from Codex CLI, got %s", type(parsed).__name__)
        return [], expected_session_ids

    returned_ids = {str(f.get("session_id", "")) for f in parsed if isinstance(f, dict)}
    missing = [sid for sid in expected_session_ids if sid not in returned_ids]

    if missing:
        logger.warning("CLI did not return facets for session_ids: %s", missing)

    valid_facets = [f for f in parsed if isinstance(f, dict) and f.get("session_id")]
    return valid_facets, missing


def generate_facets(
    sessions: list[dict],
    on_progress: Callable[[int, int, int, int], None] = None,
) -> dict:
    """
    Generate facets for sessions that don't already have cached facets.

    Uses `codex exec` for generation.

    Args:
        sessions: List of session-meta dicts.
        on_progress: Optional callback(generated_so_far, total_to_generate, wave, total_waves).

    Returns:
        {"generated": int, "cached": int, "failed": int, "facets": list[dict]}
    """
    _ensure_facets_dir()

    result_facets: list[dict] = []
    cached_count = 0
    generated_count = 0
    failed_count = 0

    # Separate sessions into cached vs needs-generation
    to_generate: list[dict] = []
    for session in sessions:
        session_id = str(session.get("session_id", ""))
        cached = _load_cached_facet(session_id)
        if cached is not None:
            result_facets.append(cached)
            cached_count += 1
        else:
            to_generate.append(session)

    total_to_generate = len(to_generate)
    total_waves = math.ceil(total_to_generate / BATCH_SIZE) if total_to_generate else 0

    if total_to_generate == 0:
        return {
            "generated": generated_count,
            "cached": cached_count,
            "failed": failed_count,
            "facets": result_facets,
        }

    for wave_index, batch_start in enumerate(range(0, total_to_generate, BATCH_SIZE)):
        wave_number = wave_index + 1
        batch = to_generate[batch_start : batch_start + BATCH_SIZE]
        expected_session_ids = [str(s.get("session_id", "")) for s in batch]

        prompt = _build_prompt(batch)
        raw_text = _call_cli_with_retry(prompt)

        if raw_text is None:
            failed_count += len(batch)
        else:
            facets, missing = _parse_facets_from_response(raw_text, expected_session_ids)
            failed_count += len(missing)

            for facet in facets:
                _write_facet(facet)
                result_facets.append(facet)
                generated_count += 1

        if on_progress is not None:
            on_progress(generated_count, total_to_generate, wave_number, total_waves)

    return {
        "generated": generated_count,
        "cached": cached_count,
        "failed": failed_count,
        "facets": result_facets,
    }
