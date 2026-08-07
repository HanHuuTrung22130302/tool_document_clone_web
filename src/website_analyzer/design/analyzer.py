"""Infer design tokens from computed CSS properties in browser snapshots."""

from __future__ import annotations

from collections import Counter
from typing import Any

from playwright.async_api import Page


class DesignAnalyzer:
    """Collect a bounded, representative sample of rendered style properties."""

    async def inspect(self, page: Page) -> dict[str, Any]:
        styles = await page.locator("body").evaluate("""body => {
          const targets = [...document.querySelectorAll('body, button, input, textarea, select, a, h1, h2, h3, p, article, section, [class*=card i]')].slice(0, 600);
          return targets.map((el) => { const s = getComputedStyle(el); return {
            tag: el.tagName.toLowerCase(), color: s.color, background: s.backgroundColor,
            fontFamily: s.fontFamily, fontSize: s.fontSize, fontWeight: s.fontWeight,
            borderRadius: s.borderRadius, boxShadow: s.boxShadow,
            padding: s.padding, margin: s.margin
          }; });
        }""")
        def frequent(key: str, limit: int = 12) -> list[dict[str, object]]:
            counts = Counter(item[key] for item in styles if item.get(key) and item[key] not in {"none", "0px", "rgba(0, 0, 0, 0)"})
            return [{"value": value, "count": count} for value, count in counts.most_common(limit)]
        return {"colors": {"text": frequent("color"), "background": frequent("background")}, "typography": {"families": frequent("fontFamily"), "sizes": frequent("fontSize"), "weights": frequent("fontWeight")}, "shape": {"radii": frequent("borderRadius"), "shadows": frequent("boxShadow")}, "spacing": {"padding": frequent("padding"), "margin": frequent("margin")}}
