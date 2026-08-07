"""Generate the aggregate Markdown report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from website_analyzer.reports.rebuild_docs import RebuildDocumentationGenerator
from website_analyzer.storage.database import AnalysisRepository


class ReportGenerator:
    def __init__(self, repository: AnalysisRepository, output: Path) -> None:
        self._repository, self._output = repository, output

    async def generate(self) -> Path:
        (self._output / "markdown").mkdir(parents=True, exist_ok=True)
        (self._output / "reports").mkdir(parents=True, exist_ok=True)
        pages, requests, edges = await self._repository.all_pages(), await self._repository.all_requests(), await self._repository.all_edges()
        self._write_sitemap(pages)
        self._write_component_tree()
        self._write_design_system()
        RebuildDocumentationGenerator(self._output).generate()
        lines = [
            "# Website analysis report", "",
            "## Website overview", "",
            f"- Pages captured: {len(pages)}",
            f"- Browser requests recorded: {len(requests)}",
            f"- Navigation transitions: {len(edges)}", "",
            "## UI Layout & Documentation Specifications", "",
            "- 📋 [UI Layout Specification](../UI_LAYOUT_SPEC.md)",
            "- 📖 [UI Interface Descriptions](../markdown/ui_descriptions.md)",
            "- 🤖 [AI Frontend Rebuild Handoff Package](../markdown/ai-rebuild-handoff/README.md)",
            "- 🎨 [Design System Tokens](../markdown/design_system.md)",
            "- 🧩 [Component Tree](../markdown/component_tree.md)", "",
            "## Pages", "",
        ]
        for page in pages:
            title = page.get("title") or "Untitled"
            lines.append(f"- [{title}]({page['url']}) — status `{page.get('status')}`, depth `{page.get('depth')}`")
        lines += ["", "## Components, forms, and DOM", "", "See `dom/` and `pages/` for per-page structured evidence.", "", "## Design system", "", "See `design/` for computed-style token frequencies.", "", "## User flows", "", "See `flows/flows.md`.", "", "## Detected APIs", "", "See `apis/apis.md`; endpoints are limited to observed browser traffic.", "", "## Assets", "", "Downloaded same-origin assets are organized under images/, css/, js/, fonts/, videos/, and assets/.", ""]
        report = self._output / "reports" / "report.md"
        report.write_text("\n".join(lines), encoding="utf-8")
        summary = {"pages": pages, "request_count": len(requests), "navigation_edges": edges}
        (self._output / "reports" / "report.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        return report

    def _write_sitemap(self, pages: list[dict[str, object]]) -> None:
        root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        for page in pages:
            node = SubElement(root, "url")
            SubElement(node, "loc").text = str(page["canonical_url"])
        ElementTree(root).write(self._output / "sitemap.xml", encoding="utf-8", xml_declaration=True)

    def _write_component_tree(self) -> None:
        lines = ["# Component tree", ""]
        for path in sorted((self._output / "dom").rglob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            lines.extend([f"## `{path.stem}`", ""])
            for component in data.get("components", []):
                label = f" — {component['label']}" if component.get("label") else ""
                lines.append(f"- **{component['kind']}**: `{component['selector']}`{label}")
            if not data.get("components"):
                lines.append("- No named semantic component candidates detected.")
            lines.append("")
        (self._output / "markdown" / "component_tree.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_design_system(self) -> None:
        values: dict[str, Counter[str]] = {"colors": Counter(), "fonts": Counter(), "sizes": Counter(), "radii": Counter(), "shadows": Counter()}
        for path in (self._output / "design").rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data.get("colors", {}).get("text", []) + data.get("colors", {}).get("background", []): values["colors"][item["value"]] += int(item["count"])
            for item in data.get("typography", {}).get("families", []): values["fonts"][item["value"]] += int(item["count"])
            for item in data.get("typography", {}).get("sizes", []): values["sizes"][item["value"]] += int(item["count"])
            for item in data.get("shape", {}).get("radii", []): values["radii"][item["value"]] += int(item["count"])
            for item in data.get("shape", {}).get("shadows", []): values["shadows"][item["value"]] += int(item["count"])
        lines = ["# Inferred design system", "", "Values are frequency-ranked samples from computed rendered styles.", ""]
        for heading, counter in values.items():
            lines.extend([f"## {heading.title()}", ""])
            lines.extend(f"- `{value}` — {count} observations" for value, count in counter.most_common(15))
            lines.append("")
        (self._output / "markdown" / "design_system.md").write_text("\n".join(lines), encoding="utf-8")
