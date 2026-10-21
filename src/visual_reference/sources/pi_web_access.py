"""Search adapter that reuses the pi-web-access MCP server over stdio.

The environment already ships a working, credential-owning search integration
(`pi-web-access`), so this project calls it instead of adding a search dependency or a new
API key. If it is missing, the adapter reports a clear error and the caller keeps going.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config import PiWebAccessConfig
from ..models import RawSearchResult
from .base import AdapterResult

# The provider name ends the marker phrase: whitespace past it is separator, not name.
PROVIDER_RE = re.compile(r"\*\*Provider:\*\*[ \t]*([A-Za-z0-9_,-]+)")
SOURCE_RE = re.compile(r"Source:\s*(?P<title>.*?)\s*\((?P<url>https?://[^)\s]+)\)")
NUMBERED_SOURCE_RE = re.compile(r"^\s*\d+\.\s+(?P<title>.+?)\s*$\n\s+(?P<url>https?://\S+)\s*$", re.MULTILINE)
SNIPPET_LIMIT = 420

CANDIDATE_SERVER_PATHS = (
    Path.home() / ".pi" / "agent" / "npm" / "node_modules" / "pi-web-access" / "dist" / "mcp-cli.js",
    Path.home() / ".pi" / "agent" / "install" / "current" / "node_modules" / "pi-web-access" / "dist" / "mcp-cli.js",
)


def resolve_server_path(config: PiWebAccessConfig) -> Path | None:
    configured = config.server_path or os.environ.get("VRE_PI_WEB_ACCESS_SERVER") or ""
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_file() else None
    for candidate in CANDIDATE_SERVER_PATHS:
        if candidate.is_file():
            return candidate
    return None


def _clean_snippet(text: str) -> str:
    cleaned = re.sub(r"[#*`>]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:SNIPPET_LIMIT]


def parse_search_text(text: str, query: str = "") -> tuple[list[RawSearchResult], str | None, list[str]]:
    """Parse the markdown-ish result of pi-web-access `web_search`.

    Returns (results, provider, warnings). Results are traceable: title + page URL only.
    """
    warnings: list[str] = []
    provider_match = PROVIDER_RE.search(text)
    provider = provider_match.group(1).strip() if provider_match else None

    snippets: dict[str, str] = {}
    spans = list(SOURCE_RE.finditer(text))
    for index, match in enumerate(spans):
        start = spans[index - 1].end() if index else 0
        snippet = _clean_snippet(text[start:match.start()])
        url = match.group("url").rstrip(".,;")
        if snippet:
            snippets[url] = snippet

    ordered: list[RawSearchResult] = []
    seen: set[str] = set()
    for match in NUMBERED_SOURCE_RE.finditer(text):
        url = match.group("url").rstrip(".,;")
        if url in seen:
            continue
        seen.add(url)
        ordered.append(
            RawSearchResult(
                title=_clean_snippet(match.group("title")) or url,
                page_url=url,
                snippet=snippets.get(url, ""),
                query=query,
            )
        )
    if not ordered:
        for match in spans:
            url = match.group("url").rstrip(".,;")
            if url in seen:
                continue
            seen.add(url)
            ordered.append(
                RawSearchResult(
                    title=_clean_snippet(match.group("title")) or url,
                    page_url=url,
                    snippet=snippets.get(url, ""),
                    query=query,
                )
            )
    if not ordered:
        warnings.append("The search backend returned no traceable results for this query.")
    return ordered, provider, warnings


class PiWebAccessAdapter:
    """Calls `web_search` on the pi-web-access MCP server through a short stdio session."""

    name = "pi_web_access"

    def __init__(self, config: PiWebAccessConfig) -> None:
        self.config = config

    def available(self) -> tuple[bool, str | None]:
        if not self.config.enabled:
            return False, "The pi_web_access source is disabled in configuration."
        path = resolve_server_path(self.config)
        if path is None:
            return False, (
                "pi-web-access MCP server not found. Install it (npm package `pi-web-access`) or set "
                "`sources.pi_web_access.server_path` / VRE_PI_WEB_ACCESS_SERVER to its dist/mcp-cli.js."
            )
        if shutil.which(self.config.command) is None:
            return False, f"Command `{self.config.command}` is not available on PATH."
        return True, None

    async def search(self, queries: list[str], per_query_limit: int) -> AdapterResult:
        ok, reason = self.available()
        if not ok:
            return AdapterResult(errors=[reason or "Search backend unavailable."])
        path = resolve_server_path(self.config)
        assert path is not None
        arguments: dict[str, Any] = {"numResults": max(1, min(per_query_limit, 20))}
        if len(queries) == 1:
            arguments["query"] = queries[0]
        else:
            arguments["queries"] = queries[:3]

        params = StdioServerParameters(command=self.config.command, args=[str(path)])
        result = AdapterResult()
        response = None
        for attempt in (1, 2):
            try:
                async with asyncio.timeout(self.config.timeout_seconds):
                    async with stdio_client(params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            response = await session.call_tool("web_search", arguments)
            except TimeoutError:
                result.errors.append(
                    f"The search backend did not answer within {self.config.timeout_seconds:.0f}s."
                )
                return result
            except Exception as exc:  # transport failure must not look like "no results"
                result.errors.append(f"Search backend failed: {type(exc).__name__}: {exc}")
                return result
            if not response.isError:
                break
            message = " ".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            ).strip()
            # The keyless provider this environment uses answers "no provider available" while it
            # cools down; one bounded retry turns that transient state into a real answer.
            transient = "no search provider available" in message.lower() or "rate limit" in message.lower()
            if attempt == 1 and transient:
                await asyncio.sleep(2.0)
                continue
            result.errors.append(f"Search backend returned an error: {message[:400] or 'no detail'}")
            return result
        assert response is not None

        text = "\n".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        if not text.strip():
            result.errors.append("Search backend returned an empty response.")
            return result

        combined_query = " | ".join(queries)
        ordered, provider, warnings = parse_search_text(text, combined_query)
        result.results = ordered
        result.warnings.extend(warnings)
        result.provider = provider
        return result
