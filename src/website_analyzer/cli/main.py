"""Typer command-line entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from website_analyzer.apis.analyzer import ApiAnalyzer
from website_analyzer.config import CrawlSettings
from website_analyzer.crawler.engine import CrawlEngine
from website_analyzer.flows.analyzer import FlowAnalyzer
from website_analyzer.reports.generator import ReportGenerator
from website_analyzer.storage.database import AnalysisRepository

app = typer.Typer(help="Authorized-access website analysis and offline dataset capture.", no_args_is_help=True)
console = Console()


async def build_reports(output: Path) -> Path:
    repository = AnalysisRepository(output / "metadata.sqlite3")
    try:
        await FlowAnalyzer(repository, output).generate()
        await ApiAnalyzer(repository, output).generate()
        return await ReportGenerator(repository, output).generate()
    finally:
        await repository.close()


@app.command()
def crawl(
    url: str = typer.Argument(..., help="HTTP(S) URL for a site you are authorized to analyze."),
    output: Path = typer.Option(Path("output"), "--output", "-o"),
    headless: bool = typer.Option(False, help="Run Chromium without a visible window."),
    login: bool = typer.Option(False, help="Start with persisted profile; manually authenticate when prompted."),
    depth: str = typer.Option("4", help="Maximum link depth or 'unlimited'."),
    max_pages: int = typer.Option(250, min=1),
    ui_states: int = typer.Option(24, "--ui-states", min=0, max=100, help="Safe tab/menu/dropdown states to capture per page."),
) -> None:
    """Crawl a same-origin site and build an offline dataset."""
    max_depth = 10_000 if depth.lower() == "unlimited" else int(depth)
    settings = CrawlSettings(url=url, output=output, headless=headless, login=login, max_depth=max_depth, max_pages=max_pages, max_ui_states_per_page=ui_states)
    settings.paths.ensure()
    repository = AnalysisRepository(settings.paths.database)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Capturing authorized website data…", total=None)
        stats = asyncio.run(CrawlEngine(settings, repository).run())
    asyncio.run(repository.close())
    report = asyncio.run(build_reports(settings.paths.root))
    console.print(f"[green]Done.[/] Captured {stats.visited} pages, {stats.assets} assets, and {stats.requests} requests.")
    console.print(f"Report: {report}")


@app.command()
def analyze(output: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Regenerate derived flow and API artifacts from an existing dataset."""
    asyncio.run(build_reports(output))
    console.print("[green]Analysis artifacts regenerated.[/]")


@app.command()
def report(output: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Regenerate the aggregate Markdown and JSON report."""
    report_path = asyncio.run(build_reports(output))
    console.print(f"[green]Report written:[/] {report_path}")


if __name__ == "__main__":
    app()
