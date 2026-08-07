"""Extract semantic page structure, controls, forms and logical components."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from website_analyzer.models import ComponentRecord, FormField, FormRecord


class DomAnalyzer:
    """Deterministic DOM analyzer that favors semantic HTML and accessible labels."""

    COMPONENT_SELECTORS: ClassVar[dict[str, str]] = {
        "Navbar": "nav, header [role=navigation]",
        "Sidebar": "aside, [role=complementary]",
        "Hero": "[class*=hero i], [data-component*=hero i]",
        "Card": "[class*=card i], article",
        "Modal": "dialog, [role=dialog]",
        "Footer": "footer, [role=contentinfo]",
        "Table": "table, [role=table]",
        "Pagination": "[class*=pagination i], nav[aria-label*=pagination i]",
    }

    def analyze(self, page_url: str, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        components = self.components(page_url, soup)
        forms = self.forms(page_url, soup)
        links = self.links(page_url, soup)
        assets = sorted(self.asset_urls(page_url, soup))
        summary = {
            "forms": [self._form_json(form) for form in forms],
            "elements": {name: len(soup.select(selector)) for name, selector in {
                "buttons": "button, input[type=button], input[type=submit]", "tables": "table",
                "images": "img", "videos": "video", "canvas": "canvas", "svg": "svg", "iframes": "iframe",
            }.items()},
            "components": [asdict(component) for component in components],
            "links": links,
            "asset_references": assets,
        }
        return {"components": components, "forms": forms, "links": links, "summary": summary}

    def components(self, page_url: str, soup: BeautifulSoup) -> list[ComponentRecord]:
        records: list[ComponentRecord] = []
        for kind, selector in self.COMPONENT_SELECTORS.items():
            for index, element in enumerate(soup.select(selector), start=1):
                records.append(ComponentRecord(page_url, kind, self._selector(element, index), self._label(element),
                                               {str(k): " ".join(v) if isinstance(v, list) else str(v) for k, v in element.attrs.items()}))
        return records

    def forms(self, page_url: str, soup: BeautifulSoup) -> list[FormRecord]:
        results: list[FormRecord] = []
        for form in soup.select("form"):
            fields: list[FormField] = []
            for field in form.select("input, select, textarea"):
                field_type = str(field.get("type") or field.name)
                validation = {key: str(field.get(key)) for key in ("minlength", "maxlength", "pattern", "min", "max") if field.get(key) is not None}
                fields.append(FormField(field.get("name") or field.get("id"), field_type, field.get("placeholder"), field.has_attr("required"), validation))
            action = form.get("action")
            results.append(FormRecord(page_url, urljoin(page_url, action) if action else None,
                                      str(form.get("method") or "GET").upper(), self._form_category(form, fields), fields))
        return results

    @staticmethod
    def links(page_url: str, soup: BeautifulSoup) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        card_keywords = (
            "card", "product", "article", "item", "sanpham", "san-pham", "pro-", "p-item",
            "goods", "box-product", "product-box", "product-item", "grid-item", "col-product"
        )
        for anchor in soup.select("a[href]"):
            href = str(anchor["href"])
            card = anchor.find_parent(
                lambda tag: isinstance(tag, Tag) and (
                    tag.name == "article" or
                    any(kw in " ".join(tag.get("class", [])).lower() for kw in card_keywords)
                )
            )
            output.append({"url": urljoin(page_url, href), "label": anchor.get_text(" ", strip=True)[:200], "card_context": bool(card)})
        return output

    @staticmethod
    def asset_urls(page_url: str, soup: BeautifulSoup) -> set[str]:
        urls: set[str] = set()
        for element in soup.select("img[src], script[src], link[href], source[src], video[src], audio[src], iframe[src]"):
            value = element.get("src") or element.get("href")
            if value:
                urls.add(urljoin(page_url, str(value)))
        return urls

    @staticmethod
    def _label(element: Tag) -> str | None:
        return element.get("aria-label") or element.get("id") or element.get_text(" ", strip=True)[:150] or None

    @staticmethod
    def _selector(element: Tag, index: int) -> str:
        identifier = element.get("id")
        if identifier:
            return f"#{identifier}"
        classes = ".".join(element.get("class", [])[:2])
        return f"{element.name}{'.' + classes if classes else ''}:nth-match({index})"

    @staticmethod
    def _form_category(form: Tag, fields: list[FormField]) -> str:
        corpus = " ".join([str(form.get("id", "")), str(form.get("class", ""))] + [str(f.name or "") for f in fields]).lower()
        for category, keywords in {"login": ("login", "sign-in", "password"), "register": ("register", "sign-up", "signup"), "search": ("search", "query"), "checkout": ("checkout", "payment", "card"), "contact": ("contact", "message")}.items():
            if any(word in corpus for word in keywords): return category
        return "form"

    @staticmethod
    def _form_json(form: FormRecord) -> dict[str, Any]:
        return {"page_url": form.page_url, "action": form.action, "method": form.method, "category": form.category,
                "fields": [asdict(field) for field in form.fields]}
