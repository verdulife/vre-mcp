"""Bounded, SSRF-aware HTTP access.

Every outbound request goes through this module: scheme allow-list, DNS/IP checks on each
hop, manual redirect validation, time and size limits, and image sniffing. Remote text is
treated as data only.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .config import HttpConfig
from .urls import is_http_url

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}


class FetchError(Exception):
    """A fetch failed for a documented reason; the message is safe to show to the user."""


class BlockedURLError(FetchError):
    """The URL was refused by policy (scheme, host, address or redirect)."""


@dataclass
class FetchedResource:
    url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    truncated: bool = False


def _address_is_blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


async def assert_public_http_url(url: str) -> None:
    """Reject non-HTTP schemes, literal private addresses and names resolving to private IPs."""
    if not is_http_url(url):
        raise BlockedURLError(f"Refused URL (only http/https is allowed): {url}")
    parts = urlsplit(url)
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise BlockedURLError(f"Refused URL without host: {url}")
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise BlockedURLError(f"Refused URL pointing at a local host: {url}")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _address_is_blocked(literal):
            raise BlockedURLError(f"Refused URL pointing at a private address: {url}")
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"DNS lookup failed for {host}: {exc}") from exc
    for info in infos:
        raw = info[4][0]
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if _address_is_blocked(address):
            raise BlockedURLError(f"Refused URL resolving to a private address ({host} -> {raw})")


def describe_http_error(url: str, exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f"Timed out fetching {url}"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} fetching {url}"
    return f"Failed to fetch {url}: {type(exc).__name__}"


def _client(config: HttpConfig) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(config.timeout_seconds),
        headers={
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.5",
        },
    )


async def fetch_resource(
    url: str,
    config: HttpConfig,
    *,
    max_bytes: int | None = None,
    accept: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> FetchedResource:
    """Fetch one resource with redirect re-validation and a hard byte cap."""
    limit = max_bytes or config.max_response_bytes
    owns_client = client is None
    if owns_client:
        client = _client(config)
    assert client is not None
    current = url
    try:
        for _ in range(config.max_redirects + 1):
            await assert_public_http_url(current)
            async with client.stream("GET", current, headers={"Accept": accept} if accept else None) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError(f"Redirect without Location from {current}")
                    current = str(response.url.join(location))
                    continue
                if response.status_code >= 400:
                    raise FetchError(f"HTTP {response.status_code} fetching {current}")
                chunks: list[bytes] = []
                size = 0
                truncated = False
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= limit:
                        truncated = True
                        break
                content = b"".join(chunks)[:limit]
                return FetchedResource(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=(response.headers.get("content-type") or "").split(";")[0].strip().lower(),
                    content=content,
                    truncated=truncated,
                )
        raise FetchError(f"Too many redirects fetching {url}")
    finally:
        if owns_client:
            await client.aclose()


async def fetch_html(url: str, config: HttpConfig, *, client: httpx.AsyncClient | None = None) -> str:
    resource = await fetch_resource(
        url,
        config,
        accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        client=client,
    )
    if resource.content_type and not (
        resource.content_type.startswith("text/") or "html" in resource.content_type or resource.content_type == ""
    ):
        raise FetchError(f"Expected an HTML page at {url}, got {resource.content_type}")
    charset = "utf-8"
    return resource.content.decode(charset, errors="replace")


async def fetch_image_bytes(
    url: str,
    config: HttpConfig,
    *,
    max_bytes: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> FetchedResource:
    resource = await fetch_resource(url, config, max_bytes=max_bytes, accept="image/*", client=client)
    content_type = resource.content_type or ""
    if content_type and not content_type.startswith("image/"):
        raise FetchError(f"Expected an image at {url}, got {content_type}")
    if not resource.content:
        raise FetchError(f"Empty image response from {url}")
    return resource
