"""Breadth-first same-origin crawl and safe client-side state exploration."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict
from typing import Any

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from website_analyzer.assets.downloader import AssetDownloader
from website_analyzer.browser.session import BrowserSession
from website_analyzer.config import CrawlSettings, CrawlStatistics
from website_analyzer.crawler.deduplication import PageDeduplicator
from website_analyzer.crawler.interactions import InteractionExplorer, UiState
from website_analyzer.design.analyzer import DesignAnalyzer
from website_analyzer.dom.analyzer import DomAnalyzer
from website_analyzer.models import PageRecord
from website_analyzer.network.recorder import NetworkRecorder
from website_analyzer.pages.capture import PageCapture
from website_analyzer.pages.profiler import PageProfile, PageProfiler
from website_analyzer.storage.database import AnalysisRepository
from website_analyzer.utils.files import stable_name, write_json
from website_analyzer.utils.urls import canonicalize, is_probably_document, same_origin


class CrawlEngine:
    """Coordinates browser evidence collection, route discovery, and UI-state capture."""

    def __init__(self, settings: CrawlSettings, repository: AnalysisRepository) -> None:
        self.settings, self.repository = settings, repository
        self.stats = CrawlStatistics()
        self._dom, self._design, self._interactions = DomAnalyzer(), DesignAnalyzer(), InteractionExplorer()
        self._profiler, self._deduplicator = PageProfiler(), PageDeduplicator()
        self._seen: set[str] = set()

    async def run(self) -> CrawlStatistics:
        paths = self.settings.paths
        paths.ensure()
        queue: deque[tuple[str, int]] = deque([(canonicalize(str(self.settings.url)), 0)])
        self._seen = await self.repository.page_urls()
        if self._seen:
            self.stats.findings.append(f"Resuming dataset with {len(self._seen)} existing snapshot(s).")
        capture = PageCapture(paths.directory("html"), paths.directory("screenshots"))
        assets = AssetDownloader(str(self.settings.url), paths.root, self.repository)
        await assets.initialize()
        self._html_hashes: dict[str, str] = {}
        async with BrowserSession(self.settings) as browser, httpx.AsyncClient(
            timeout=30, headers={"User-Agent": "WebsiteAnalyzer/0.1 authorized research"}
        ) as client:
            await self._authenticate_if_requested(browser)
            while queue and self.stats.visited < self.settings.max_pages:
                url, depth = queue.popleft()
                if url in self._seen or depth > self.settings.max_depth:
                    continue
                known_duplicate = self._deduplicator.known_route_duplicate(url)
                if known_duplicate:
                    self._seen.add(url)
                    self._deduplicator.note_skipped(url, known_duplicate)
                    continue
                self._seen.add(url)
                self.stats.queued += 1
                discovered = await self._visit(url, depth, browser, capture, assets, client)
                for target, label in discovered:
                    if target not in self._seen and len(self._seen) + len(queue) < self.settings.max_pages:
                        queue.append((target, depth + 1))
                        await self.repository.save_edge(url, target, label)
        write_json(paths.directory("reports") / "crawl_stats.json", asdict(self.stats))
        write_json(paths.directory("reports") / "deduplicated_routes.json", self._deduplicator.skipped_routes)
        write_json(paths.directory("reports") / "sampled_card_links.json", self._deduplicator.sampled_card_links)
        return self.stats

    async def _authenticate_if_requested(self, browser: BrowserSession) -> None:
        if not self.settings.login:
            return
        if self.settings.headless:
            raise ValueError("--login requires headed Chromium so the operator can authenticate manually")
        page = await browser.new_page()
        try:
            await page.goto(str(self.settings.url), wait_until="domcontentloaded")
            await browser.pause_for_manual_action(page, "sign in to the authorized account")
        finally:
            await page.close()

    async def _visit(self, url: str, depth: int, browser: BrowserSession, capture: PageCapture,
                     assets: AssetDownloader, client: httpx.AsyncClient) -> list[tuple[str, str | None]]:
        page = await browser.new_page()
        recorder = NetworkRecorder(str(self.settings.url), self.settings.paths.directory("responses"), self.repository)
        recorder.attach(page)
        try:
            response = await page.goto(url, wait_until="networkidle")
            await browser.detect_and_handle_challenge(page)
            actual_url = page.url
            analysis = await self._persist_snapshot(page, url, actual_url, depth, response.status if response else None, capture, assets, client)
            discovered = self._route_links(analysis, actual_url)
            original_fingerprint = await self._interactions.fingerprint(page)
            controls = await self._interactions.controls(page, self.settings.max_ui_states_per_page)
            for ordinal, control in enumerate(controls, start=1):
                if self.stats.visited >= self.settings.max_pages:
                    break
                state = await self._interactions.activate(page, actual_url, control, original_fingerprint, ordinal)
                if not state:
                    continue
                await browser.detect_and_handle_challenge(page)
                identity = f"{url}#ui-state={state.state_id}"
                if identity in self._seen:
                    continue
                self._seen.add(identity)
                state_analysis = await self._persist_snapshot(page, identity, state.actual_url, depth, None, capture, assets, client, state)
                await self.repository.save_edge(url, identity, state.label)
                discovered.extend(self._route_links(state_analysis, state.actual_url))
                if canonicalize(state.actual_url) != canonicalize(actual_url):
                    discovered.append((canonicalize(state.actual_url), state.label))
            return discovered
        except PlaywrightError as error:
            self.stats.failed += 1
            self.stats.findings.append(f"{url}: {error}")
            return []
        finally:
            recorder.detach(page)
            await recorder.drain()
            self.stats.requests += recorder.records_seen
            await page.close()

    async def _persist_snapshot(self, page: Page, identity: str, actual_url: str, depth: int, status: int | None,
                                capture: PageCapture, assets: AssetDownloader, client: httpx.AsyncClient,
                                state: UiState | None = None) -> dict[str, Any]:
        """Write one full evidence snapshot, including an in-page UI state if supplied."""
        html = await page.content()
        profile = self._profiler.profile(actual_url, html)
        analysis = self._dom.analyze(actual_url, html)
        for component in analysis["components"]:
            component.page_url = identity

        from website_analyzer.utils.files import sha256
        html_digest = sha256(html.encode("utf-8"))
        if html_digest in self._html_hashes:
            dup_ref = type("TemplateReference", (), {"snapshot_id": self._html_hashes[html_digest], "topic": profile.topic, "route_pattern": ""})()
            return await self._persist_duplicate(identity, actual_url, depth, profile, dup_ref, analysis, "identical HTML content")

        duplicate = self._deduplicator.duplicate_of(profile, state is not None)
        if duplicate:
            return await self._persist_duplicate(identity, actual_url, depth, profile, duplicate, analysis, "matching page template")

        self._html_hashes[html_digest] = identity
        html_path = await capture.save_html(html, identity, profile.output_folder)
        screenshots = await capture.screenshots(page, identity, profile.output_folder)
        design = await self._design.inspect(page)
        snapshot = {
            "snapshot_id": identity, "url": actual_url, "title": await page.title(), "depth": depth,
            "ui_state": asdict(state) if state else None, "dom": analysis["summary"], "design": design,
            "screenshots": screenshots, "html_path": html_path, "profile": asdict(profile),
        }
        name = stable_name(identity, ".json")
        write_json(self.settings.paths.directory("pages") / profile.output_folder / name, snapshot)
        write_json(self.settings.paths.directory("dom") / profile.output_folder / name, analysis["summary"])
        write_json(self.settings.paths.directory("design") / profile.output_folder / name, design)
        meta = self._meta(html)
        if state:
            meta["website_analyzer.ui_state"] = state.label
            meta["website_analyzer.ui_state_role"] = state.role
        meta["website_analyzer.page_type"] = profile.page_type
        meta["website_analyzer.topic"] = profile.topic
        meta["website_analyzer.template_fingerprint"] = profile.template_fingerprint
        record = PageRecord(
            url=identity, canonical_url=canonicalize(actual_url), title=await page.title(), status=status,
            depth=depth, language=await page.locator("html").get_attribute("lang"), meta=meta, html_path=html_path,
            screenshot_path=screenshots.get("desktop-full"),
        )
        await self.repository.save_page(record)
        await self.repository.save_components(analysis["components"])
        self._deduplicator.register(identity, actual_url, profile)
        self.stats.visited += 1
        asset_urls = self._dom.asset_urls(actual_url, BeautifulSoup(html, "lxml"))
        results = await asyncio.gather(*(assets.download(asset, client) for asset in asset_urls), return_exceptions=True)
        self.stats.assets += sum(result is not None and not isinstance(result, Exception) for result in results)
        return analysis

    async def _persist_duplicate(self, identity: str, actual_url: str, depth: int, profile: PageProfile,
                                 duplicate: Any, analysis: dict[str, Any], reason: str = "matching product-detail template") -> dict[str, Any]:
        """Keep route and DOM evidence but avoid duplicating identical screenshots and HTML."""
        snapshot = {
            "snapshot_id": identity, "url": actual_url, "title": profile.title, "depth": depth,
            "duplicate_of": duplicate.snapshot_id, "duplicate_reason": reason,
            "dom": analysis["summary"], "profile": asdict(profile), "screenshots": {}, "html_path": None,
        }
        name = stable_name(identity, ".json")
        write_json(self.settings.paths.directory("pages") / "duplicates" / profile.output_folder / name, snapshot)
        await self.repository.save_page(PageRecord(
            url=identity, canonical_url=canonicalize(actual_url), title=profile.title, status=None, depth=depth,
            meta={"website_analyzer.duplicate_of": duplicate.snapshot_id, "website_analyzer.page_type": profile.page_type,
                  "website_analyzer.topic": profile.topic, "website_analyzer.template_fingerprint": profile.template_fingerprint},
        ))
        self.stats.visited += 1
        return analysis

    def _route_links(self, analysis: dict[str, Any], base_url: str) -> list[tuple[str, str | None]]:
        routes: list[tuple[str, str | None]] = []
        for link in analysis["links"]:
            target = canonicalize(str(link["url"]), base_url)
            if not same_origin(target, str(self.settings.url)) or not is_probably_document(target):
                continue
            if link.get("card_context") and not self._deduplicator.retain_card_link(target):
                continue
            routes.append((target, str(link["label"]) or None))
        return routes

    @staticmethod
    def _meta(html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        return {
            str(tag.get("name") or tag.get("property")): str(tag.get("content"))
            for tag in soup.select("meta[content]")
            if tag.get("name") or tag.get("property")
        }
