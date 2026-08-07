"""Runtime configuration and output layout."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True, slots=True)
class OutputPaths:
    """Centralized, deterministic layout for one crawl dataset."""

    root: Path

    @property
    def database(self) -> Path:
        return self.root / "metadata.sqlite3"

    def directory(self, name: str) -> Path:
        return self.root / name

    def ensure(self) -> None:
        for name in (
            "pages", "screenshots", "html", "dom", "assets", "css", "js", "fonts",
            "images", "videos", "apis", "responses", "flows", "design", "markdown", "reports",
        ):
            self.directory(name).mkdir(parents=True, exist_ok=True)


class CrawlSettings(BaseSettings):
    """Settings accepted by the CLI and injectable into framework services."""

    model_config = SettingsConfigDict(env_prefix="WEBSITE_ANALYZER_", extra="ignore")

    url: AnyHttpUrl
    output: Path = Path("output")
    profile_dir: Path = Path("browser-profile")
    headless: bool = False
    max_depth: int = Field(default=4, ge=0)
    max_pages: int = Field(default=250, ge=1)
    max_ui_states_per_page: int = Field(default=24, ge=0, le=100)
    concurrency: int = Field(default=3, ge=1, le=10)
    timeout_ms: int = Field(default=30_000, ge=1_000)
    viewport_width: int = Field(default=1440, ge=320)
    viewport_height: int = Field(default=900, ge=320)
    login: bool = False

    @property
    def paths(self) -> OutputPaths:
        return OutputPaths(self.output.resolve())


@dataclass(slots=True)
class CrawlStatistics:
    queued: int = 0
    visited: int = 0
    failed: int = 0
    assets: int = 0
    requests: int = 0
    findings: list[str] = field(default_factory=list)
