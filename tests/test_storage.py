from pathlib import Path

import pytest

from website_analyzer.models import AssetRecord, PageRecord, RequestRecord
from website_analyzer.storage.database import AnalysisRepository


@pytest.mark.asyncio
async def test_repository_persists_core_records(tmp_path: Path) -> None:
    repository = AnalysisRepository(tmp_path / "analysis.sqlite3")
    try:
        await repository.save_page(PageRecord("https://example.com/", "https://example.com/", "Home", 200, 0))
        await repository.save_asset(AssetRecord("https://example.com/logo.png", "images/logo.png", "image/png", 12, "abc"))
        await repository.save_request(RequestRecord("https://example.com/api/products", "GET", "fetch", {}))
        assert (await repository.all_pages())[0]["title"] == "Home"
        assert (await repository.all_requests())[0]["method"] == "GET"
    finally:
        await repository.close()
