"""Safe exploration of client-side navigation states."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from website_analyzer.utils.files import slug
from website_analyzer.utils.urls import same_origin


@dataclass(frozen=True, slots=True)
class InteractiveControl:
    """A rendered, non-destructive client-side navigation control."""

    index: int
    label: str
    role: str
    selector: str


@dataclass(frozen=True, slots=True)
class UiState:
    """A distinct UI state reached by a safe client-side interaction."""

    state_id: str
    label: str
    role: str
    actual_url: str


class InteractionExplorer:
    """Discovers tabs, menus, popovers and pagination without submitting data-bearing forms."""

    selector = "[role='tab'], [role='menuitem'], [aria-controls], [data-bs-toggle='tab'], [data-toggle='tab'], [data-tab], button[aria-expanded], summary"
    forbidden_words = ("logout", "sign out", "delete", "remove", "purchase", "buy", "pay", "checkout", "submit", "register", "sign up")

    async def controls(self, page: Page, maximum: int) -> list[InteractiveControl]:
        raw = await page.locator(self.selector).evaluate_all("""elements => elements.map((element, index) => ({
            index, tag: element.tagName.toLowerCase(), type: (element.getAttribute('type') || '').toLowerCase(),
            disabled: element.matches(':disabled') || element.getAttribute('aria-disabled') === 'true',
            label: (element.getAttribute('aria-label') || element.textContent || element.getAttribute('title') || element.id || '').trim(),
            role: element.getAttribute('role') || element.getAttribute('data-bs-toggle') || element.getAttribute('data-toggle') || element.tagName.toLowerCase()
        }))""")
        output: list[InteractiveControl] = []
        for item in raw:
            if self.is_safe(item):
                output.append(InteractiveControl(int(item["index"]), str(item["label"])[:160] or "unnamed-control", str(item["role"]), self.selector))
            if len(output) >= maximum:
                break
        return output

    @classmethod
    def is_safe(cls, item: dict[str, object]) -> bool:
        text = str(item.get("label") or "").lower()
        return not bool(item.get("disabled")) and item.get("type") != "submit" and not any(word in text for word in cls.forbidden_words)

    async def activate(self, page: Page, source_url: str, control: InteractiveControl, original_fingerprint: str, ordinal: int) -> UiState | None:
        """Reset to the source page, click one permitted control, and identify meaningful change."""
        await page.goto(source_url, wait_until="domcontentloaded")
        locator = page.locator(control.selector).nth(control.index)
        if await locator.count() == 0:
            return None
        try:
            await locator.click(timeout=5_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=4_000)
            except PlaywrightTimeoutError:
                pass
        except (PlaywrightError, PlaywrightTimeoutError):
            return None
        if not same_origin(page.url, source_url):
            return None
        fingerprint = await self.fingerprint(page)
        if fingerprint == original_fingerprint:
            return None
        return UiState(f"ui-{ordinal:02d}-{slug(control.label, 45)}", control.label, control.role, page.url)

    @staticmethod
    async def fingerprint(page: Page) -> str:
        return await page.locator("body").evaluate("body => `${location.href}|${body.innerHTML}`")
