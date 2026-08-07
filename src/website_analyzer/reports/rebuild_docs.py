"""Generate a self-contained handoff package for an AI implementation agent."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from website_analyzer.utils.files import slug, write_json


class RebuildDocumentationGenerator:
    """Turn raw page evidence into route-by-route frontend reconstruction specifications."""

    def __init__(self, output: Path) -> None:
        self._output = output
        self._root = output / "markdown" / "ai-rebuild-handoff"

    def generate(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        snapshots = self._load_snapshots()
        manifest = self._manifest(snapshots)
        write_json(self._root / "implementation_manifest.json", manifest)
        self._write_overview(manifest)
        self._write_ui_descriptions(snapshots)
        for snapshot in snapshots:
            self._write_page_spec(snapshot)

    def _load_snapshots(self) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for path in sorted((self._output / "pages").rglob("*.json")):
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            snapshot.setdefault("snapshot_id", snapshot.get("url", path.stem))
            snapshot.setdefault("html_path", None)
            snapshots.append(snapshot)
        return snapshots

    def _manifest(self, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        components = Counter(component["kind"] for snapshot in snapshots for component in snapshot.get("dom", {}).get("components", []))
        routes = [{
            "snapshot_id": snapshot["snapshot_id"], "url": snapshot["url"], "title": snapshot.get("title"),
                "ui_state": snapshot.get("ui_state"), "spec": f"pages/{slug(snapshot['snapshot_id'])}.md",
            "screenshots": snapshot.get("screenshots", {}), "html_path": snapshot.get("html_path"),
            "profile": snapshot.get("profile", {}), "duplicate_of": snapshot.get("duplicate_of"),
        } for snapshot in snapshots]
        return {
            "purpose": "Evidence package for rebuilding the captured frontend.", "entrypoint": "README.md",
            "route_and_state_count": len(routes), "routes_and_states": routes,
            "shared_component_candidates": dict(components.most_common()), "global_design_reference": "../design_system.md",
            "navigation_reference": "../../flows/flows.md", "api_reference": "../../apis/apis.md", "asset_root": "../../",
        }

    def _write_overview(self, manifest: dict[str, Any]) -> None:
        lines = [
            "# AI frontend rebuild handoff", "",
            "This package is generated from rendered browser evidence. Use it as the build contract for a new frontend; do not invent pages, APIs, or flows absent from the evidence.", "",
            "## Recommended agent workflow", "",
            "1. Read `implementation_manifest.json` and every file in `pages/`.",
            "2. Build one route for each distinct URL and one visible state for each `ui_state` snapshot.",
            "3. Reuse candidates in Shared component candidates when they occur across snapshots.",
            "4. Use screenshots as visual acceptance criteria and `html_path` as structural evidence.",
            "5. Recreate typography, colors, spacing, radii, and shadows from `../design_system.md`.",
            "6. Implement forms from each page specification, preserving names, types, placeholders, requirements, and validation rules.",
            "7. Treat `../../apis/apis.md` as observed traffic documentation, not a complete backend contract.", "",
            "## Routes and captured UI states", "",
        ]
        for route in manifest["routes_and_states"]:
            state = route["ui_state"]
            suffix = f" (UI state: {state['label']})" if state else ""
            profile = route.get("profile", {})
            duplicate = f" - duplicate of `{route['duplicate_of']}`" if route.get("duplicate_of") else ""
            lines.append(f"- [{route['title'] or 'Untitled'}]({route['spec']}) - `{route['url']}` - {profile.get('page_type', 'unclassified')}{suffix}{duplicate}")
        lines += ["", "## Shared component candidates", ""]
        lines.extend(f"- `{kind}`: {count} detected instance(s)" for kind, count in manifest["shared_component_candidates"].items())
        lines += ["", "## Supporting evidence", "", "- [Design system](../design_system.md)", "- [Component tree](../component_tree.md)", "- [User flows](../../flows/flows.md)", "- [Observed APIs](../../apis/apis.md)", ""]
        (self._root / "README.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_ui_descriptions(self, snapshots: list[dict[str, Any]]) -> None:
        """Write a human-readable UI layout specification."""
        lines = [
            "# UI Layout Specification", "",
            "This document describes the observed visual structure, layout components, forms, and topic classification of every captured route and UI state.", "",
            "## Summary of Captured Pages", "",
        ]
        for snapshot in snapshots:
            profile = snapshot.get("profile", {})
            dom = snapshot.get("dom", {})
            components = [component["kind"] for component in dom.get("components", [])]
            element_counts = dom.get("elements", {})
            layout = " -> ".join(dict.fromkeys(components)) or "main document content"
            lines += [
                f"### {profile.get('topic') or snapshot.get('title') or 'Untitled page'}", "",
                f"- **URL:** `{snapshot['url']}`",
                f"- **Page Type:** `{profile.get('page_type', 'unclassified')}`",
                f"- **Topic Folder:** `{profile.get('output_folder', profile.get('topic', ''))}`",
                f"- **Heading:** {profile.get('primary_heading') or 'not detected'}",
                f"- **Layout Flow:** {layout}",
                f"- **Description:** {profile.get('description') or 'no meta description detected'}",
                f"- **UI Components:** {', '.join(f'{key}={value}' for key, value in element_counts.items()) or 'none'}",
            ]
            if snapshot.get("ui_state"):
                state = snapshot["ui_state"]
                lines.append(f"- **Visible State:** `{state['label']}` ({state['role']})")
            if snapshot.get("duplicate_of"):
                reason = snapshot.get("duplicate_reason", "matching template")
                lines.append(f"- **Template Duplicate:** Reuses layout structure of `{snapshot['duplicate_of']}` ({reason}).")
            lines.append("")

        content = "\n".join(lines)
        (self._output / "markdown" / "ui_descriptions.md").write_text(content, encoding="utf-8")
        (self._output / "markdown" / "UI_LAYOUT_SPEC.md").write_text(content, encoding="utf-8")
        (self._output / "UI_LAYOUT_SPEC.md").write_text(content, encoding="utf-8")
        self._write_output_readme(snapshots)

    def _write_output_readme(self, snapshots: list[dict[str, Any]]) -> None:
        lines = [
            "# Website Analyzer Dataset", "",
            "This folder contains the complete captured offline evidence and analysis dataset.", "",
            "## Quick Links to Documentation", "",
            "- 📋 [UI Layout Specification](UI_LAYOUT_SPEC.md)",
            "- 🤖 [AI Frontend Rebuild Package](markdown/ai-rebuild-handoff/README.md)",
            "- 🎨 [Design System Tokens](markdown/design_system.md)",
            "- 🧩 [Component Tree](markdown/component_tree.md)",
            "- 📊 [Detailed Crawl Report](reports/report.md)",
            "- 🔀 [User Flows](flows/flows.md)",
            "- 🔌 [Observed APIs](apis/apis.md)", "",
            "## Folder Structure", "",
            "```text",
            "output/",
            "  ├── UI_LAYOUT_SPEC.md               # Layout specifications & topic summary",
            "  ├── metadata.sqlite3                 # SQLite database with all pages, assets, requests",
            "  ├── sitemap.xml                      # Generated sitemap",
            "  ├── html/                            # Rendered HTML per topic",
            "  ├── screenshots/                     # Desktop, laptop, tablet, mobile screenshots",
            "  ├── pages/ dom/ design/              # Evidence snapshots and component trees",
            "  ├── images/ css/ js/ fonts/          # Saved assets (SHA-256 deduplicated)",
            "  └── markdown/                        # Human & AI readable specifications",
            "```",
        ]
        (self._output / "README.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_page_spec(self, snapshot: dict[str, Any]) -> None:
        page_dir = self._root / "pages"
        page_dir.mkdir(exist_ok=True)
        dom = snapshot.get("dom", {})
        profile = snapshot.get("profile", {})
        lines = [
            f"# {snapshot.get('title') or 'Untitled page'}", "", f"- Snapshot ID: `{snapshot['snapshot_id']}`",
            f"- Rendered URL: `{snapshot['url']}`", f"- Source HTML: `{snapshot.get('html_path')}`",
            f"- Viewport evidence: {', '.join(f'`{name}`' for name in snapshot.get('screenshots', {})) or 'none'}", "",
            "## Reconstruction instructions", "",
            "Implement this page at the rendered URL route. Match desktop, laptop, tablet, and mobile screenshots before changing visual decisions. Preserve the components, forms, and interaction state documented below.", "",
        ]
        if profile:
            lines += ["## Page classification", "", f"- Type: `{profile.get('page_type')}`", f"- Topic: `{profile.get('topic')}`", f"- Main heading: {profile.get('primary_heading') or 'not detected'}", f"- Description: {profile.get('description') or 'not detected'}", ""]
        if snapshot.get("duplicate_of"):
            lines += ["## Duplicate template", "", f"This route uses the same detected product-detail template as `{snapshot['duplicate_of']}`. Reuse that implementation and substitute route-specific product data.", ""]
        if snapshot.get("ui_state"):
            state = snapshot["ui_state"]
            lines += ["## UI state", "", f"- Control label: `{state['label']}`", f"- Control role: `{state['role']}`", f"- State identifier: `{state['state_id']}`", ""]
        lines += ["## Components", ""]
        for component in dom.get("components", []):
            label = f" - {component['label']}" if component.get("label") else ""
            lines.append(f"- **{component['kind']}** `{component['selector']}`{label}")
        if not dom.get("components"):
            lines.append("- No semantic component candidates were detected.")
        lines += ["", "## Forms", ""]
        for form in dom.get("forms", []):
            lines.append(f"### {form['category'].title()} form ({form['method']} {form.get('action') or ''})")
            for field in form.get("fields", []):
                rules = ", ".join(f"{key}={value}" for key, value in field.get("validation", {}).items()) or "none"
                lines.append(f"- `{field.get('name') or 'unnamed'}`: {field['field_type']}; placeholder={field.get('placeholder')!r}; required={field['required']}; validation={rules}")
        if not dom.get("forms"):
            lines.append("- No HTML forms detected.")
        lines += ["", "## Navigation and assets", ""]
        lines.extend(f"- Link: `{link['label'] or 'unlabeled'}` -> `{link['url']}`" for link in dom.get("links", []))
        lines += ["", "### Referenced assets", ""]
        lines.extend(f"- `{asset}`" for asset in dom.get("asset_references", []))
        if not dom.get("asset_references"):
            lines.append("- No directly referenced assets detected.")
        lines += ["", "## Visual token sample", ""]
        design = snapshot.get("design", {})
        groups = (("Text colors", design.get("colors", {}).get("text", [])), ("Background colors", design.get("colors", {}).get("background", [])), ("Font families", design.get("typography", {}).get("families", [])), ("Font sizes", design.get("typography", {}).get("sizes", [])))
        for family, values in groups:
            lines.append(f"### {family}")
            lines.extend(f"- `{item['value']}` ({item['count']} observations)" for item in values[:8])
            lines.append("")
        (page_dir / f"{slug(snapshot['snapshot_id'])}.md").write_text("\n".join(lines), encoding="utf-8")
