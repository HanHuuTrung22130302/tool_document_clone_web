"""Infer a conservative OpenAPI-like report from observed network data."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from website_analyzer.storage.database import AnalysisRepository
from website_analyzer.utils.files import write_json


class ApiAnalyzer:
    def __init__(self, repository: AnalysisRepository, output: Path) -> None:
        self._repository, self._output = repository, output

    async def generate(self) -> None:
        groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for request in await self._repository.all_requests():
            resource = str(request["resource_type"])
            content_type = str(request.get("content_type") or "")
            if resource in {"xhr", "fetch"} or "json" in content_type:
                parsed = urlparse(str(request["url"]))
                groups[(str(request["method"]), parsed.path)].append(request)
        paths: dict[str, dict[str, object]] = {}
        markdown = ["# Observed APIs", "", "This is evidence-based documentation from browser traffic; it does not claim unobserved endpoints.", ""]
        for (method, path), rows in sorted(groups.items()):
            sample = rows[0]
            parameters = sorted(parse_qs(urlparse(str(sample["url"])).query).keys())
            schema = self._schema_from_response(sample.get("response_path"))
            operation = {"summary": "Observed browser request", "parameters": parameters, "responses": {str(sample.get("status")): {"content_type": sample.get("content_type"), "schema": schema}}}
            paths.setdefault(path, {})[method.lower()] = operation
            markdown += [f"## `{method} {path}`", "", f"- Observations: {len(rows)}", f"- Query parameters: {', '.join(parameters) or 'none'}", f"- Status: {sample.get('status')}", f"- Response schema: `{json.dumps(schema)}`", ""]
        write_json(self._output / "apis" / "openapi-observed.json", {"openapi": "3.1.0", "info": {"title": "Observed APIs", "version": "0.1.0"}, "paths": paths})
        (self._output / "apis" / "apis.md").write_text("\n".join(markdown), encoding="utf-8")

    @staticmethod
    def _schema_from_response(path: object) -> dict[str, object]:
        if not path:
            return {"type": "unknown"}
        try:
            payload = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {"type": "binary-or-non-json"}
        if isinstance(payload, dict): return {"type": "object", "properties": {key: {"type": type(value).__name__} for key, value in payload.items()}}
        if isinstance(payload, list): return {"type": "array", "items": {"type": type(payload[0]).__name__} if payload else {}}
        return {"type": type(payload).__name__}
