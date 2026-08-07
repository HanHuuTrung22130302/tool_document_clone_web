"""Capture a rendered page and its responsive screenshots."""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page

from website_analyzer.utils.files import stable_name


class PageCapture:
    def __init__(self, html_dir: Path, screenshot_dir: Path) -> None:
        self._html_dir, self._screenshot_dir = html_dir, screenshot_dir

    async def save_html(self, rendered: str, identity: str, folder: str) -> str:
        destination = self._html_dir / folder / stable_name(identity, ".html")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
        return str(destination)

    async def screenshots(self, page: Page, identity: str, folder: str) -> dict[str, str]:
        original = page.viewport_size or {"width": 1440, "height": 900}
        output: dict[str, str] = {}
        for device, width, height in (("desktop", 1440, 900), ("laptop", 1280, 800), ("tablet", 768, 1024), ("mobile", 390, 844)):
            await page.set_viewport_size({"width": width, "height": height})
            for mode in ("full", "viewport"):
                name = f"{device}-{mode}"
                path = self._screenshot_dir / folder / stable_name(identity, f"-{name}.png")
                path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(path), full_page=mode == "full")
                output[name] = str(path)
        await page.set_viewport_size(original)
        return output
