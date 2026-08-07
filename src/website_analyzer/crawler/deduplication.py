"""Template and route-pattern deduplication for repeated catalog detail pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from website_analyzer.pages.profiler import PageProfile


@dataclass(frozen=True, slots=True)
class TemplateReference:
    snapshot_id: str
    topic: str
    route_pattern: str


class PageDeduplicator:
    """Keep a representative product detail page while retaining skipped-route evidence."""

    def __init__(self) -> None:
        self._templates: dict[str, TemplateReference] = {}
        self._route_patterns: dict[str, TemplateReference] = {}
        self.skipped_routes: list[dict[str, str]] = []
        self.sampled_card_links: list[dict[str, str]] = []
        self._card_samples: dict[str, str] = {}

    def duplicate_of(self, profile: PageProfile, has_ui_state: bool) -> TemplateReference | None:
        if has_ui_state:
            return None
        return self._templates.get(profile.template_fingerprint)

    def register(self, snapshot_id: str, url: str, profile: PageProfile) -> None:
        reference = TemplateReference(snapshot_id, profile.topic, self.route_pattern(url))
        self._templates.setdefault(profile.template_fingerprint, reference)
        self._route_patterns.setdefault(reference.route_pattern, reference)

    def known_route_duplicate(self, url: str) -> TemplateReference | None:
        return self._route_patterns.get(self.route_pattern(url))

    def note_skipped(self, url: str, reference: TemplateReference) -> None:
        self.skipped_routes.append({"url": url, "duplicate_of": reference.snapshot_id, "representative_topic": reference.topic, "route_pattern": reference.route_pattern})

    def retain_card_link(self, url: str) -> bool:
        """Keep one representative card target per URL shape, not every product card."""
        pattern = self.route_pattern(url)
        representative = self._card_samples.get(pattern)
        if representative:
            self.sampled_card_links.append({"url": url, "representative_url": representative, "route_pattern": pattern})
            return False
        self._card_samples[pattern] = url
        return True

    @staticmethod
    def route_pattern(url: str) -> str:
        parsed = urlparse(url)
        if parsed.query:
            query_params = parsed.query.split("&")
            normalized_params = []
            for param in query_params:
                if "=" in param:
                    key, val = param.split("=", 1)
                    if key.lower() in ("id", "sp", "product", "item", "p", "sku", "product_id", "pid") or val.isdigit():
                        normalized_params.append(f"{key}={{item}}")
                    else:
                        normalized_params.append(param)
                else:
                    normalized_params.append(param)
            query_str = "?" + "&".join(sorted(normalized_params))
        else:
            query_str = ""

        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            return "/" + query_str

        last = segments[-1]
        ext = ""
        m_ext = re.search(r"\.(html?|php|aspx?)$", last, flags=re.IGNORECASE)
        if m_ext:
            ext = m_ext.group(0)
            last_no_ext = last[:m_ext.start()]
        else:
            last_no_ext = last

        static_pages = {"login", "register", "about", "contact", "cart", "checkout", "search", "gio-hang", "thanh-toan", "lien-he", "dang-nhap", "dang-ky", "detail", "product", "item", "index"}
        if last_no_ext.lower() not in static_pages and (len(segments) > 1 or re.search(r"\d", last_no_ext) or len(last_no_ext) >= 5):
            segments[-1] = "{item}" + ext

        return "/" + "/".join(segments) + query_str
