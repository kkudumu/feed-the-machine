"""
Plan generator — invokes Claude CLI to produce a structured YAML execution plan.

The generator calls `claude -p <prompt> --output-format json`, parses the JSON
envelope to extract the text result, then extracts the embedded YAML block.

On timeout or any subprocess error the function returns a safe error dict so
callers can surface the failure without crashing.
"""

from __future__ import annotations

import json
import subprocess

import yaml


def generate_plan(task_data: dict, capabilities: dict | None = None) -> dict:
    """Invoke Claude CLI to generate a structured plan for a task.

    Returns a dict with keys:
      - steps: list[dict]  — parsed plan steps (empty on failure)
      - yaml_content: str  — raw YAML string
      - raw_response: str  — full text from Claude (useful for debugging)
      - error: str | None  — set only on failure
    """
    cap_note = ""
    if capabilities:
        available = ", ".join(
            k for k, v in capabilities.items() if v
        )
        if available:
            cap_note = f"\nAvailable integrations: {available}"

    prompt = f"""Generate a structured execution plan for this task.

Task: {task_data.get('title', '')}
Source: {task_data.get('source', '')}
Body: {task_data.get('body', '')}{cap_note}

Return a YAML object with this structure:
steps:
  - id: 1
    title: "Step description"
    target_system: "jira|freshservice|slack|gmail|local"
    method_primary: "tool or action"
    method_fallback: "alternative if primary unavailable"
    risk_level: "low|medium|high"
    approval_required: false
    rollback: "how to undo"

Only return the YAML, no other text."""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {"error": result.stderr or "Claude CLI returned non-zero exit", "steps": [], "yaml_content": "", "raw_response": ""}

        # Claude CLI JSON envelope: {"result": "<text>", ...}
        try:
            output = json.loads(result.stdout)
            text = output.get("result", result.stdout)
        except json.JSONDecodeError:
            text = result.stdout

        yaml_content = _extract_yaml(text)
        try:
            plan_data = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as exc:
            return {
                "error": f"YAML parse error: {exc}",
                "steps": [],
                "yaml_content": yaml_content,
                "raw_response": text,
            }

        raw_steps = plan_data.get("steps", [])
        # Normalise: ensure each step has all expected keys with safe defaults
        steps = [_normalise_step(i + 1, s) for i, s in enumerate(raw_steps)]

        return {
            "steps": steps,
            "yaml_content": yaml_content,
            "raw_response": text,
            "error": None,
        }

    except subprocess.TimeoutExpired:
        return {"error": "Plan generation timed out after 120s", "steps": [], "yaml_content": "", "raw_response": ""}
    except FileNotFoundError:
        return {"error": "Claude CLI not found — ensure 'claude' is on PATH", "steps": [], "yaml_content": "", "raw_response": ""}
    except Exception as exc:
        return {"error": str(exc), "steps": [], "yaml_content": "", "raw_response": ""}


def _extract_yaml(text: str) -> str:
    """Extract YAML content from Claude's response, handling optional code fences."""
    if "```yaml" in text:
        start = text.index("```yaml") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    return text.strip()


def _normalise_step(index: int, raw: dict) -> dict:
    """Ensure a raw step dict has all required keys."""
    return {
        "id": raw.get("id", index),
        "title": raw.get("title", f"Step {index}"),
        "target_system": raw.get("target_system", "local"),
        "method_primary": raw.get("method_primary", ""),
        "method_fallback": raw.get("method_fallback", ""),
        "risk_level": raw.get("risk_level", "low"),
        "approval_required": bool(raw.get("approval_required", False)),
        "rollback": raw.get("rollback", ""),
        "status": "pending",
    }
