"""Safe file naming and atomic JSON serialization."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import orjson


def slug(value: str, limit: int = 90) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D"))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", ascii_value).strip("-._")
    return (clean[:limit] or "item").lower()


def stable_name(url: str, suffix: str = "") -> str:
    parsed = urlparse(url)
    seed = f"{parsed.netloc}{parsed.path}?{parsed.query}#{parsed.fragment}"
    readable = slug(f"{parsed.path.strip('/') or 'index'}-{parsed.fragment}" if parsed.fragment else (parsed.path.strip("/") or "index"), 55)
    digest = hashlib.sha256(seed.encode()).hexdigest()[:12]
    return f"{readable}-{digest}{suffix}"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
