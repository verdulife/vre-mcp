"""URL normalization, provenance helpers and hosting filters.

External text is data, never instructions: nothing here interprets page content.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref_src", "ref_url")
TRACKING_PARAMS = {"ref", "referrer", "source", "spm", "yclid", "msclkid", "_hsenc", "_hsmi"}

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")


def is_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def normalize_url(url: str, *, keep_query: bool = True) -> str:
    """Normalize for deduplication: scheme/host casing, default ports, tracking params."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        return url.strip()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    query = ""
    if keep_query and parts.query:
        pairs = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith(TRACKING_PREFIXES) and key.lower() not in TRACKING_PARAMS
        ]
        query = urlencode(sorted(pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def dedupe_key(url: str) -> str:
    return normalize_url(url)


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def absolute_url(base: str, maybe_relative: str) -> str | None:
    value = (maybe_relative or "").strip()
    if not value or value.startswith("data:"):
        return None
    try:
        resolved = urljoin(base, value)
    except ValueError:
        return None
    return resolved if is_http_url(resolved) else None


def domain_allowed(host: str, allowed: list[str] | None, excluded: list[str] | None) -> bool:
    if not host:
        return False
    if excluded and any(host == item or host.endswith("." + item) for item in excluded):
        return False
    if allowed:
        return any(host == item or host.endswith("." + item) for item in allowed)
    return True


def looks_like_image_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.endswith(IMAGE_EXTENSIONS)
