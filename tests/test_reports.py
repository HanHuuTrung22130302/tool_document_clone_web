import tempfile
from pathlib import Path

import pytest

from website_analyzer.reports.generator import ReportGenerator
from website_analyzer.storage.database import AnalysisRepository


@pytest.mark.asyncio
async def test_report_generator_creates_ui_layout_spec_and_readme() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir)
        db_path = output / "metadata.sqlite3"
        repo = AnalysisRepository(db_path)
        try:
            (output / "pages" / "test").mkdir(parents=True, exist_ok=True)
            snapshot = {
                "snapshot_id": "https://example.com/test",
                "url": "https://example.com/test",
                "title": "Test Page",
                "dom": {"components": [], "elements": {"buttons": 2}, "forms": []},
                "profile": {"page_type": "landing-page", "topic": "Test Page", "output_folder": "landing-page/test-page"},
            }
            import json
            (output / "pages" / "test" / "test.json").write_text(json.dumps(snapshot), encoding="utf-8")

            generator = ReportGenerator(repo, output)
            report_path = await generator.generate()

            assert report_path.exists()
            assert (output / "UI_LAYOUT_SPEC.md").exists()
            assert (output / "README.md").exists()
            assert (output / "markdown" / "ui_descriptions.md").exists()
            
            spec_content = (output / "UI_LAYOUT_SPEC.md").read_text(encoding="utf-8")
            assert "UI Layout Specification" in spec_content
            assert "Test Page" in spec_content
        finally:
            await repo.close()
