"""Classify page intent, derive a readable topic, and fingerprint its UI template."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from website_analyzer.utils.files import slug


@dataclass(frozen=True, slots=True)
class PageProfile:
    """Compact semantic identity used for storage, documentation, and deduplication."""

    page_type: str
    topic: str
    title: str
    primary_heading: str | None
    description: str | None
    template_fingerprint: str

    @property
    def output_folder(self) -> str:
        return f"{self.page_type}/{slug(self.topic, 60)}"


class PageProfiler:
    """Rule-based page profiling that remains deterministic and offline."""

    def profile(self, url: str, html: str) -> PageProfile:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled page"
        heading = self._text(soup.select_one("h1"))
        description_tag = soup.select_one("meta[name='description']")
        description = str(description_tag.get("content")) if description_tag and description_tag.get("content") else None
        og_title_tag = soup.select_one("meta[property='og:title'], meta[name='og:title']")
        og_title = str(og_title_tag.get("content")).strip() if og_title_tag and og_title_tag.get("content") else None
        breadcrumb = self._breadcrumb_topic(soup)
        text = " ".join(soup.stripped_strings).lower()
        page_type = self._type(url, soup, text)
        topic = self._topic(url, heading, title, og_title, breadcrumb)
        return PageProfile(page_type, topic, title, heading, description, self._fingerprint(soup))

    @staticmethod
    def _text(element: Tag | None) -> str | None:
        return element.get_text(" ", strip=True)[:180] if element else None

    @staticmethod
    def _breadcrumb_topic(soup: BeautifulSoup) -> str | None:
        nodes = soup.select("nav[aria-label*='breadcrumb' i] li, .breadcrumb li, [class*='breadcrumb' i] li, .breadcrumb a, [class*='breadcrumb' i] a")
        texts = [n.get_text(" ", strip=True) for n in nodes if n.get_text(" ", strip=True)]
        if len(texts) >= 2:
            return texts[-1]
        return None

    def _type(self, url: str, soup: BeautifulSoup, text: str) -> str:
        path = urlparse(url).path.lower()
        product_schema = any("product" in str(tag.get("type", "")).lower() for tag in soup.select("script[type='application/ld+json']"))
        product_signals = (
            "add to cart", "add to bag", "buy now", "in stock", "sku", "price",
            "mua ngay", "them vao gio", "thêm vào giỏ", "thêm vào giỏ hàng", "đặt mua",
            "đặt hàng", "giá bán", "giá khuyến mãi", "thông số kỹ thuật", "tình trạng",
            "bảo hành", "mã sp", "chi tiết sản phẩm", "cho vào giỏ", "liên hệ mua hàng"
        )
        has_signal = any(signal in text for signal in product_signals)
        is_product_path = any(p in path for p in ("/product/", "/p/", "/item/", "/san-pham/", "/chitiet/", "/detail/"))
        if product_schema or (has_signal and len(soup.select("h1")) >= 1) or (is_product_path and has_signal):
            return "product-detail"
        if any(word in path for word in ("category", "catalog", "collection", "products", "search", "danh-muc", "thiet-bi")) or len(soup.select("article, [class*='card' i], [class*='item' i], [class*='product' i]")) >= 6:
            return "product-listing"
        if any(word in path for word in ("login", "sign-in", "register", "account", "dang-nhap", "dang-ky")):
            return "account"
        if any(word in path for word in ("checkout", "cart", "payment", "gio-hang", "thanh-toan")):
            return "commerce-flow"
        if any(word in path for word in ("blog", "news", "article", "tin-tuc", "bai-viet")) or soup.select_one("article"):
            return "article"
        if soup.select_one("form") and any(word in text for word in ("contact", "lien he", "liên hệ", "message")):
            return "contact"
        return "landing-page"

    @staticmethod
    def _topic(url: str, heading: str | None, title: str, og_title: str | None = None, breadcrumb: str | None = None) -> str:
        candidates = [breadcrumb, heading, og_title, title]
        chosen = None
        for cand in candidates:
            if cand and cand.strip():
                clean = re.split(r"\s+[|\-–—:]\s+", cand.strip(), maxsplit=1)[0].strip()
                if clean.lower() not in {"home", "homepage", "trang chủ", "trang chu", "untitled page", "index"}:
                    chosen = clean
                    break
        if not chosen:
            path = urlparse(url).path.strip("/")
            if path:
                segments = [s for s in path.split("/") if s]
                last = segments[-1]
                last = re.sub(r"\.(html?|php|aspx?)$", "", last, flags=re.IGNORECASE)
                chosen = last.replace("-", " ").replace("_", " ")
            else:
                chosen = "home"
        return chosen[:100].strip() or "page"

    @staticmethod
    def _fingerprint(soup: BeautifulSoup) -> str:
        """Use semantic structure, not content, to recognize repeating page templates."""
        parts: list[str] = []
        for element in soup.select("body *"):
            if not isinstance(element, Tag) or element.name in {"script", "style", "noscript"}:
                continue
            role = element.get("role", "")
            field_type = element.get("type", "") if element.name in {"input", "button"} else ""
            state = "hidden" if element.has_attr("hidden") else ""
            parts.append(f"{element.name}:{role}:{field_type}:{state}")
            if len(parts) >= 700:
                break
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]

