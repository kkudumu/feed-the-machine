"""
StepRunner — executes a single plan step via Claude CLI.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

_STEP_TIMEOUT = 120  # seconds


class StepRunner:
    """Runs a single plan step by invoking Claude CLI."""

    @staticmethod
    async def run(step: dict, task_context: dict) -> dict[str, Any]:
        """
        Execute a plan step and return structured result.

        Returns:
            {"status": "completed"|"failed", "output": str, "error": str, "duration_ms": int}
        """
        prompt = (
            f"Execute this plan step:\n\n"
            f"Step: {step.get('title', '')}\n"
            f"Target system: {step.get('target_system', 'local')}\n"
            f"Method: {step.get('method_primary', '')}\n"
            f"Fallback: {step.get('method_fallback', '')}\n\n"
            f"Task context:\n"
            f"Title: {task_context.get('title', '')}\n"
            f"Source: {task_context.get('source', '')}\n"
            f"Body: {task_context.get('body', '')}\n\n"
            f"Execute the step and report what was done. "
            f"If the action cannot be performed, explain why."
        )

        start = time.monotonic()
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=_STEP_TIMEOUT,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            if result.returncode != 0:
                return {
                    "status": "failed",
                    "output": result.stdout,
                    "error": result.stderr or f"Exit code {result.returncode}",
                    "duration_ms": duration_ms,
                }

            # Parse Claude JSON output
            try:
                data = json.loads(result.stdout)
                text = data.get("result", result.stdout)
            except json.JSONDecodeError:
                text = result.stdout

            return {
                "status": "completed",
                "output": text,
                "error": "",
                "duration_ms": duration_ms,
            }

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "failed",
                "output": "",
                "error": f"Step timed out after {_STEP_TIMEOUT}s",
                "duration_ms": duration_ms,
            }
        except FileNotFoundError:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "failed",
                "output": "",
                "error": "Claude CLI not found on PATH",
                "duration_ms": duration_ms,
            }
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "failed",
                "output": "",
                "error": str(exc),
                "duration_ms": duration_ms,
            }
