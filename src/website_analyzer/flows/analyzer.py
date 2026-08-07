"""Build readable navigation graph artifacts from crawl edges."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from website_analyzer.storage.database import AnalysisRepository
from website_analyzer.utils.files import write_json


class FlowAnalyzer:
    def __init__(self, repository: AnalysisRepository, output: Path) -> None:
        self._repository, self._output = repository, output

    async def generate(self) -> None:
        graph = nx.DiGraph()
        for row in await self._repository.all_edges():
            graph.add_edge(str(row["source"]), str(row["target"]), label=row.get("label"))
        data = nx.node_link_data(graph, edges="edges")
        write_json(self._output / "flows" / "flows.json", data)
        lines = ["# User flows", "", f"Nodes: {graph.number_of_nodes()} · Transitions: {graph.number_of_edges()}", ""]
        for source, target, value in graph.edges(data=True):
            label = f" — {value['label']}" if value.get("label") else ""
            lines.append(f"- `{source}` → `{target}`{label}")
        (self._output / "flows" / "flows.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
