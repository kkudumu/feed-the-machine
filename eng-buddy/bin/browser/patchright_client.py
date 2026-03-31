"""
bin/browser/patchright_client.py

Async Patchright session manager for eng-buddy.

Singleton class that owns one persistent Chrome context for the lifetime of
the dashboard process.  All public methods are async and serialised behind a
single asyncio.Lock so FastAPI handlers can call them concurrently without
racing on the browser state.

Usage (from dashboard/server.py):
    from bin.browser.patchright_client import PatchrightClient
    client = PatchrightClient()          # lightweight – browser not launched yet
    await client.navigate("https://...")
    snap  = await client.snapshot()
    await client.click("e3")
    await client.close()
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from patchright.async_api import async_playwright, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

_USER_DATA_DIR = str(Path.home() / ".eng-buddy" / "browser-profile")


class PatchrightClient:
    """
    Singleton-friendly async wrapper around a Patchright persistent context.

    The browser is lazy-started: the Chrome process is only launched on the
    first call to any action method (or an explicit ``start()`` call).  After
    that every method reuses the same context/page.

    Thread-safety model
    -------------------
    All mutable state (``_context``, ``_page``, ``_ref_map``) is accessed only
    while holding ``_lock``.  FastAPI runs in a single event-loop thread so
    standard asyncio.Lock is sufficient; no threading.Lock is needed.
    """

    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        # Maps ref string (e.g. "e1") to element metadata from the last snapshot
        self._ref_map: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_started(self) -> None:
        """Launch browser if not already running. Called while _lock is held."""
        if self._context is not None:
            return

        logger.info("PatchrightClient: launching persistent Chrome context …")
        Path(_USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            no_viewport=True,
        )

        # Reuse the first tab if one already exists (persistent profile may
        # restore previous session), otherwise open a fresh page.
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        logger.info("PatchrightClient: browser ready.")

    async def _page_or_raise(self) -> Page:
        """Return the active page; raises RuntimeError if not started."""
        if self._page is None:
            raise RuntimeError("PatchrightClient: browser has not been started.")
        return self._page

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> dict[str, str]:
        """
        Idempotent – initialise the browser context if not already running.

        Returns ``{"status": "ok"}`` once the browser is ready.
        """
        async with self._lock:
            await self._ensure_started()
        return {"status": "ok"}

    async def navigate(self, url: str) -> dict[str, str]:
        """
        Navigate the active page to *url*.

        Returns ``{"status": "ok", "url": url}`` on success.
        """
        async with self._lock:
            await self._ensure_started()
            page = await self._page_or_raise()
            await page.goto(url, wait_until="domcontentloaded")
            self._ref_map.clear()
        return {"status": "ok", "url": url}

    async def snapshot(self) -> dict[str, Any]:
        """
        Capture the page accessibility tree and return structured element refs.

        Each element gets a stable ref string (``e1``, ``e2``, …) that can be
        passed to ``click()`` or ``fill()`` in subsequent calls.

        Returns::

            {
                "elements": [
                    {"ref": "e1", "role": "button", "name": "Submit", "text": "Submit"},
                    ...
                ]
            }
        """
        async with self._lock:
            await self._ensure_started()
            page = await self._page_or_raise()
            raw = await page.accessibility.snapshot()

        elements: list[dict[str, Any]] = []
        self._ref_map = {}

        if raw:
            counter = 1

            def _walk(node: dict[str, Any]) -> None:
                nonlocal counter
                role = node.get("role", "")
                name = node.get("name", "")
                value = node.get("value", "")
                text = value or name

                # Only surface interactive / meaningful nodes
                if role and (name or value):
                    ref = f"e{counter}"
                    counter += 1
                    entry: dict[str, Any] = {
                        "ref": ref,
                        "role": role,
                        "name": name,
                        "text": text,
                    }
                    elements.append(entry)
                    self._ref_map[ref] = entry

                for child in node.get("children", []):
                    _walk(child)

            _walk(raw)

        return {"elements": elements}

    async def click(self, ref: str) -> dict[str, str]:
        """
        Click the element identified by *ref* (from the last ``snapshot()``).

        Returns ``{"status": "ok", "ref": ref}`` on success.
        Raises ``KeyError`` if the ref is not found in the last snapshot.
        """
        async with self._lock:
            await self._ensure_started()
            page = await self._page_or_raise()

            if ref not in self._ref_map:
                raise KeyError(f"ref '{ref}' not found in last snapshot")

            info = self._ref_map[ref]
            role = info.get("role", "")
            name = info.get("name", "")

            if role and name:
                locator = page.get_by_role(role, name=name)  # type: ignore[arg-type]
            elif name:
                locator = page.get_by_text(name, exact=True)
            else:
                raise ValueError(f"Cannot locate element for ref '{ref}': no name")

            await locator.first.click()

        return {"status": "ok", "ref": ref}

    async def fill(self, ref: str, value: str) -> dict[str, str]:
        """
        Fill the element identified by *ref* with *value*.

        Returns ``{"status": "ok", "ref": ref, "value": value}`` on success.
        Raises ``KeyError`` if the ref is not in the last snapshot.
        """
        async with self._lock:
            await self._ensure_started()
            page = await self._page_or_raise()

            if ref not in self._ref_map:
                raise KeyError(f"ref '{ref}' not found in last snapshot")

            info = self._ref_map[ref]
            role = info.get("role", "")
            name = info.get("name", "")

            if role and name:
                locator = page.get_by_role(role, name=name)  # type: ignore[arg-type]
            elif name:
                locator = page.get_by_label(name)
            else:
                raise ValueError(f"Cannot locate element for ref '{ref}': no name")

            await locator.first.fill(value)

        return {"status": "ok", "ref": ref, "value": value}

    async def evaluate(self, js: str) -> dict[str, Any]:
        """
        Evaluate arbitrary JavaScript in the page context.

        Returns ``{"result": <return value>}`` where the result is whatever
        the JS expression evaluates to (JSON-serialisable types pass through
        unchanged; DOM objects are represented as ``None``).
        """
        async with self._lock:
            await self._ensure_started()
            page = await self._page_or_raise()
            result = await page.evaluate(js)

        return {"result": result}

    async def screenshot(self) -> dict[str, Any]:
        """
        Take a full-page screenshot.

        Saves the image to a temp file and returns::

            {"path": "/tmp/eng-buddy-screenshot-<ts>.png", "data": "<base64>"}
        """
        async with self._lock:
            await self._ensure_started()
            page = await self._page_or_raise()

            ts = int(time.time() * 1000)
            path = Path(tempfile.gettempdir()) / f"eng-buddy-screenshot-{ts}.png"
            await page.screenshot(path=str(path), full_page=True)

        data = base64.b64encode(path.read_bytes()).decode()
        return {"path": str(path), "data": data}

    async def close(self) -> None:
        """
        Cleanly tear down the browser context and Playwright instance.

        Idempotent — safe to call even if the browser was never started.
        """
        async with self._lock:
            if self._context is not None:
                try:
                    await self._context.close()
                except Exception:
                    logger.warning("PatchrightClient: error closing context", exc_info=True)
                finally:
                    self._context = None
                    self._page = None
                    self._ref_map = {}

            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    logger.warning("PatchrightClient: error stopping playwright", exc_info=True)
                finally:
                    self._playwright = None

        logger.info("PatchrightClient: browser closed.")
