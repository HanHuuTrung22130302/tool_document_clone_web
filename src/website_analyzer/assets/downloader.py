"""Asynchronous asset downloader with content-addressed deduplication."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx

from website_analyzer.models import AssetRecord
from website_analyzer.storage.database import AnalysisRepository
from website_analyzer.utils.files import sha256, stable_name
from website_analyzer.utils.urls import same_origin


class AssetDownloader:
    def __init__(self, root_url: str, root: Path, repository: AnalysisRepository) -> None:
        self._root_url, self._root, self._repository = root_url, root, repository
        self._known_digests: dict[str, Path] = {}

    async def initialize(self) -> None:
        records = await self._repository.all_assets()
        for r in records:
            if r.get("sha256") and r.get("local_path"):
                p = Path(str(r["local_path"]))
                if p.exists():
                    self._known_digests[str(r["sha256"])] = p

    async def download(self, url: str, client: httpx.AsyncClient) -> AssetRecord | None:
        if not same_origin(url, self._root_url):
            return None
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        data, digest = response.content, sha256(response.content)
        content_type = response.headers.get("content-type")
        existing = self._known_digests.get(digest)
        if existing:
            local_path = existing
        else:
            kind = self._folder(content_type, url)
            local_path = self._destination(kind, url)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)
            self._known_digests[digest] = local_path
        record = AssetRecord(url=url, local_path=str(local_path), content_type=content_type, size=len(data), sha256=digest)
        await self._repository.save_asset(record)
        return record

    @staticmethod
    def _folder(content_type: str | None, url: str) -> str:
        value = (content_type or "").lower()
        if "image" in value or url.lower().endswith(".svg"):
            return "images"
        if "font" in value or any(url.lower().endswith(x) for x in (".woff", ".woff2", ".ttf", ".eot")):
            return "fonts"
        if "css" in value: return "css"
        if "javascript" in value: return "js"
        if "video" in value: return "videos"
        return "assets"

    def _destination(self, kind: str, url: str) -> Path:
        """Preserve a safe host/path hierarchy while disambiguating query variants."""
        parsed = urlparse(url)
        safe_parts = [part for part in parsed.path.split("/") if part not in {"", ".", ".."}]
        filename = safe_parts.pop() if safe_parts else "index"
        suffix = Path(filename).suffix[:10]
        if parsed.query:
            filename = stable_name(url, suffix)
        return self._root / kind / parsed.netloc / Path(*safe_parts) / filename
