"""Record browser responses without intercepting or modifying traffic."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from playwright.async_api import Page, Response

from website_analyzer.models import RequestRecord
from website_analyzer.storage.database import AnalysisRepository
from website_analyzer.utils.files import stable_name
from website_analyzer.utils.urls import same_origin


class NetworkRecorder:
    """Passive Playwright response observer that persists API evidence."""

    def __init__(self, root_url: str, response_dir: Path, repository: AnalysisRepository) -> None:
        self._root_url = root_url
        self._response_dir = response_dir
        self._repository = repository
        self._tasks: set[asyncio.Task[None]] = set()
        self.records_seen = 0

    def attach(self, page: Page) -> None:
        page.on("response", self._on_response)

    def detach(self, page: Page) -> None:
        page.remove_listener("response", self._on_response)

    def _on_response(self, response: Response) -> None:
        task = asyncio.create_task(self._capture(response))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _capture(self, response: Response) -> None:
        try:
            request = response.request
            if not same_origin(response.url, self._root_url):
                return
            started = time.perf_counter()
            content_type = response.headers.get("content-type")
            try:
                body = await response.body()
            except Exception:  # noqa: BLE001
                body = b""
            path: str | None = None
            if body and ("json" in (content_type or "") or request.resource_type in {"xhr", "fetch"}):
                suffix = ".json" if "json" in (content_type or "") else ".bin"
                target = self._response_dir / stable_name(response.url, suffix)
                target.write_bytes(body)
                path = str(target)
            post_data = request.post_data
            record = RequestRecord(
                url=response.url, method=request.method, resource_type=request.resource_type,
                request_headers=dict(request.headers), request_body=post_data, status=response.status,
                response_headers=dict(response.headers), content_type=content_type, response_size=len(body),
                timing_ms=(time.perf_counter() - started) * 1000, response_path=path,
            )
            await self._repository.save_request(record)
            self.records_seen += 1
        except Exception:  # noqa: BLE001, S110
            pass
