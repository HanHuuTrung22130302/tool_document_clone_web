"""URL normalization and scope checks."""

from __future__ import annotations

from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlparse, urlunparse

TRACKING_PARAMETERS = {"gclid", "fbclid", "mc_cid", "mc_eid"}


def canonicalize(url: str, base: str | None = None) -> str:
    absolute = urljoin(base or url, url)
    clean, _ = urldefrag(absolute)
    parsed = urlparse(clean)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                            if not (k.startswith("utm_") or k in TRACKING_PARAMETERS)))
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", query, ""))


def same_origin(candidate: str, root: str) -> bool:
    source, target = urlparse(candidate), urlparse(root)
    return source.scheme in {"http", "https"} and source.netloc.lower() == target.netloc.lower()


def is_probably_document(url: str) -> bool:
    return urlparse(url).path.lower().rsplit(".", 1)[-1] not in {
        "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "pdf", "zip", "mp4", "webm", "css", "js",
        "woff", "woff2", "ttf", "eot",
    }
