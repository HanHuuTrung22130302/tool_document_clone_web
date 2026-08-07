"""Persistent Playwright session with explicit human-verification pauses."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Self

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from website_analyzer.config import CrawlSettings

ChallengeCallback = Callable[[str], Awaitable[None]]


class BrowserSession:
    """Owns a persistent Chromium context so authentication survives every page visit."""

    def __init__(self, settings: CrawlSettings, on_challenge: ChallengeCallback | None = None) -> None:
        self._settings = settings
        self._on_challenge = on_challenge
        self._playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    async def __aenter__(self) -> Self:
        self._settings.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self.context = await self._playwright.chromium.launch_persistent_context(
            str(self._settings.profile_dir.resolve()),
            headless=self._settings.headless,
            viewport={"width": self._settings.viewport_width, "height": self._settings.viewport_height},
            ignore_https_errors=False,
        )
        self.context.set_default_timeout(self._settings.timeout_ms)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.context:
            await self.context.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self.context:
            raise RuntimeError("BrowserSession is not started")
        return await self.context.new_page()

    async def pause_for_manual_action(self, page: Page, reason: str) -> None:
        """Pause only for a human; intentionally never solves or bypasses challenges."""
        if self._on_challenge:
            await self._on_challenge(reason)
            return
        await page.bring_to_front()
        await asyncio.to_thread(input, f"Manual action required ({reason}). Please complete verification then press ENTER: ")

    async def detect_and_handle_challenge(self, page: Page) -> bool:
        text = (await page.locator("body").inner_text(timeout=5_000)).lower()
        markers = ("captcha", "verify you are human", "checking your browser", "cloudflare", "sms verification", "email verification", "two-factor authentication", "2fa")
        if any(marker in text for marker in markers):
            await self.pause_for_manual_action(page, "verification or challenge page detected")
            return True
        return False
