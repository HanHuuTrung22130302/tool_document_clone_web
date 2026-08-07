"""Typed records exchanged between collection, analysis, and storage layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class PageRecord:
    url: str
    canonical_url: str
    title: str | None
    status: int | None
    depth: int
    language: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
    html_path: str | None = None
    screenshot_path: str | None = None
    discovered_at: str = field(default_factory=utc_now)

    def json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AssetRecord:
    url: str
    local_path: str
    content_type: str | None
    size: int
    sha256: str


@dataclass(slots=True)
class RequestRecord:
    url: str
    method: str
    resource_type: str
    request_headers: dict[str, str]
    request_body: str | None = None
    status: int | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    content_type: str | None = None
    response_size: int | None = None
    timing_ms: float | None = None
    response_path: str | None = None
    observed_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ComponentRecord:
    page_url: str
    kind: str
    selector: str
    label: str | None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class FormField:
    name: str | None
    field_type: str
    placeholder: str | None
    required: bool
    validation: dict[str, str]


@dataclass(slots=True)
class FormRecord:
    page_url: str
    action: str | None
    method: str
    category: str
    fields: list[FormField]
